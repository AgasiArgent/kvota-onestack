import { createAdminClient, createClient } from "@/shared/lib/supabase/server";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";
import { isProcurementOnly } from "@/shared/lib/roles";
import { getAssignedSupplierIds } from "@/shared/lib/access";
import { fetchActiveAuthUserIds } from "@/entities/user";
import { intersectSupplierIdConstraints } from "./lib/filter-supplier-ids";
import {
  buildHistoricalRateMap,
  sumInvoiceLinesInUsd,
  type FxRateRow,
  type InvoiceLineForUsd,
} from "./lib/historical-fx";
import type {
  SupplierListItem,
  SupplierDetail,
  SupplierContact,
  BrandAssignment,
  SupplierAssignee,
  SupplierQuoteItem,
  SupplierFilterOptions,
} from "./types";

const PAGE_SIZE = 50;

// Sentinel UUID used to force a query to return zero rows when a procurement-only
// user has no supplier assignments. Postgres .in() with an empty array is
// a no-op (no filter applied), which would leak rows.
const EMPTY_RESULT_UUID = "00000000-0000-0000-0000-000000000000";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

/**
 * supplier_contacts and supplier_assignees tables are not in generated DB types yet.
 * Use untyped client for queries to those tables.
 */
function getUntypedClient(): UntypedClient {
  return createAdminClient() as unknown as UntypedClient;
}

interface AssigneeRow {
  supplier_id: string;
  user_id: string;
  created_at: string;
}

/**
 * Fetch one МОЗ per supplier (earliest-assigned user). Returns map
 * `supplier_id → full_name`. Empty map if no supplier_ids passed.
 */
async function fetchPrimaryAssignees(
  supplierIds: string[]
): Promise<Map<string, string>> {
  if (supplierIds.length === 0) return new Map();
  const untyped = getUntypedClient();
  const supabase = createAdminClient();

  const { data } = await untyped
    .from("supplier_assignees")
    .select("supplier_id, user_id, created_at")
    .in("supplier_id", supplierIds)
    .order("created_at", { ascending: true });

  const rows = (data ?? []) as AssigneeRow[];

  // Keep the earliest-assigned МОЗ per supplier (deterministic display).
  const firstPerSupplier = new Map<string, string>();
  for (const row of rows) {
    if (!firstPerSupplier.has(row.supplier_id)) {
      firstPerSupplier.set(row.supplier_id, row.user_id);
    }
  }

  const userIds = [...new Set(firstPerSupplier.values())];
  if (userIds.length === 0) return new Map();

  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", userIds);

  const nameById = new Map(
    (profiles ?? []).map((p) => [p.user_id, p.full_name ?? ""])
  );

  const result = new Map<string, string>();
  for (const [supplierId, userId] of firstPerSupplier) {
    const name = nameById.get(userId);
    if (name) result.set(supplierId, name);
  }
  return result;
}

interface InvoiceAggregateRow {
  supplier_id: string;
  created_at: string | null;
  invoice_items: Array<{
    quantity: number | null;
    purchase_price_original: number | null;
    purchase_currency: string | null;
  }> | null;
}

/**
 * Per-supplier aggregate used by the /suppliers table:
 *   - last_invoice_at: MAX(invoices.created_at)
 *   - invoice_total_usd: SUM(quantity * purchase_price_original) converted to
 *     USD per-КПП via kvota.exchange_rates looked up by `invoices.created_at`,
 *     rounded to integer USD. Null when nothing convertible exists.
 *
 * Historical FX conversion: each КПП may be in RUB/USD/EUR/CNY/etc.; a
 * naïve sum would mix currencies. Each invoice's lines are converted to
 * USD using the FX rate effective on the invoice's `created_at` date
 * (most recent rate with `fetched_at <= created_at`, falling back to the
 * earliest available rate). See `lib/historical-fx.ts` for the helpers.
 */
async function fetchInvoiceAggregatesForSuppliers(
  supplierIds: string[],
): Promise<
  Map<
    string,
    { last_invoice_at: string | null; invoice_total_usd: number | null }
  >
> {
  if (supplierIds.length === 0) return new Map();
  const supabase = createAdminClient();

  // exchange_rates is org-agnostic (CBR cache, see services/currency_service.py).
  // We pull ALL `* → RUB` rows once and look up by date in memory. This avoids
  // an N-queries-per-invoice round trip and stays correct regardless of insert
  // order because buildHistoricalRateMap sorts each bucket by fetched_at DESC.
  const [invoicesResult, ratesResult] = await Promise.all([
    supabase
      .from("invoices")
      .select(
        "supplier_id, created_at, invoice_items(quantity, purchase_price_original, purchase_currency)",
      )
      .in("supplier_id", supplierIds),
    supabase
      .from("exchange_rates")
      .select("from_currency, rate, fetched_at")
      .eq("to_currency", "RUB"),
  ]);

  const rows = (invoicesResult.data ?? []) as unknown as InvoiceAggregateRow[];
  const rateRows = (ratesResult.data ?? []) as unknown as FxRateRow[];
  const rates = buildHistoricalRateMap(rateRows);

  // Group lines by supplier with per-line asOf so historical-fx can look up
  // the rate effective on each КПП's creation date.
  const perSupplier = new Map<
    string,
    {
      last_invoice_at: string | null;
      lines: InvoiceLineForUsd[];
    }
  >();

  for (const inv of rows) {
    const bucket = perSupplier.get(inv.supplier_id) ?? {
      last_invoice_at: null,
      lines: [] as InvoiceLineForUsd[],
    };

    if (inv.created_at) {
      if (!bucket.last_invoice_at || inv.created_at > bucket.last_invoice_at) {
        bucket.last_invoice_at = inv.created_at;
      }
    }

    // Use the invoice's created_at as the as-of date for FX. If absent,
    // fall back to "now" so the line still contributes (rather than being
    // silently dropped) — pickRateOnOrBefore will return the latest rate.
    const asOf = inv.created_at ?? new Date().toISOString();

    for (const item of inv.invoice_items ?? []) {
      const qty = Number(item.quantity ?? 0);
      const price = Number(item.purchase_price_original ?? 0);
      const currency = (item.purchase_currency ?? "").trim().toUpperCase();
      if (!currency || !Number.isFinite(qty) || !Number.isFinite(price)) continue;
      const amount = qty * price;
      if (amount === 0) continue;
      bucket.lines.push({ amount, currency, asOf });
    }

    perSupplier.set(inv.supplier_id, bucket);
  }

  const result = new Map<
    string,
    { last_invoice_at: string | null; invoice_total_usd: number | null }
  >();
  for (const [supplierId, bucket] of perSupplier) {
    const { totalUsd, missing } = sumInvoiceLinesInUsd(bucket.lines, rates);
    if (missing.length > 0) {
      // Surface missing-rate cases so ops can investigate without breaking
      // the table render. We never throw — the supplier just shows a smaller
      // total or "—" when nothing could be converted.
      console.warn(
        `[suppliers] FX rate missing for supplier ${supplierId}: currencies=${missing.join(",")}`,
      );
    }
    const hasLines = bucket.lines.length > 0;
    const everythingMissing = hasLines && totalUsd === 0 && missing.length > 0;
    result.set(supplierId, {
      last_invoice_at: bucket.last_invoice_at,
      invoice_total_usd:
        !hasLines || everythingMissing ? null : Math.round(totalUsd),
    });
  }
  return result;
}

/**
 * Resolve the supplier IDs that have a brand assignment for `brand`.
 * Used by the /suppliers Бренд filter (Testing 2 row 92). Returns a
 * (possibly empty) array — an empty array forces a zero-row query.
 */
async function fetchSupplierIdsByBrand(
  orgId: string,
  brand: string
): Promise<string[]> {
  const supabase = createAdminClient();
  // brand_supplier_assignments carries its own organization_id (migration 105),
  // so filter on it directly — no join through suppliers needed.
  const { data } = await supabase
    .from("brand_supplier_assignments")
    .select("supplier_id")
    .eq("organization_id", orgId)
    .eq("brand", brand);

  return [
    ...new Set(
      (data ?? [])
        .map((r) => r.supplier_id)
        .filter((id): id is string => id !== null)
    ),
  ];
}

/**
 * Resolve the supplier IDs that have `userId` as an assignee (МОЗ).
 * Used by the /suppliers МОЗ filter (Testing 2 row 92). Returns a
 * (possibly empty) array — an empty array forces a zero-row query.
 */
async function fetchSupplierIdsByAssignee(userId: string): Promise<string[]> {
  const untyped = getUntypedClient();
  const { data } = await untyped
    .from("supplier_assignees")
    .select("supplier_id")
    .eq("user_id", userId);

  return [
    ...new Set(
      ((data ?? []) as Array<{ supplier_id: string }>)
        .map((r) => r.supplier_id)
        .filter((id): id is string => Boolean(id))
    ),
  ];
}

export async function fetchSuppliersList(
  orgId: string,
  params: {
    search?: string;
    country?: string;
    status?: string;
    assignee?: string;
    brand?: string;
    page?: number;
  },
  user?: { id: string; roles: string[] }
): Promise<{ data: SupplierListItem[]; total: number; activeCount: number; inactiveCount: number }> {
  const supabase = createAdminClient();
  const {
    search = "",
    country = "",
    status = "",
    assignee = "",
    brand = "",
    page = 1,
  } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  // Resolve assigned IDs once for procurement-only users (used for both list + counts)
  let assignedIds: string[] | null = null;
  if (user && isProcurementOnly(user.roles)) {
    const supabaseAuth = await createClient();
    assignedIds = await getAssignedSupplierIds(supabaseAuth, user.id);
  }

  // МОЗ + Бренд filters operate over junction tables, so resolve each to a set
  // of supplier IDs and intersect them (AND) with the role-based visibility
  // scope. Страна stays an inline column filter below.
  const [brandIds, assigneeIds] = await Promise.all([
    brand ? fetchSupplierIdsByBrand(orgId, brand) : Promise.resolve(null),
    assignee ? fetchSupplierIdsByAssignee(assignee) : Promise.resolve(null),
  ]);

  // null = "no constraint"; [] = "matched nothing" → must yield zero rows.
  const idConstraint = intersectSupplierIdConstraints([
    assignedIds,
    brandIds,
    assigneeIds,
  ]);

  let query = supabase
    .from("suppliers")
    .select("id, name, country, is_active", {
      count: "exact",
    })
    .eq("organization_id", orgId)
    .order("name")
    .range(from, to);

  // Combined role + Бренд + МОЗ id constraint (empty → sentinel zero-row UUID).
  if (idConstraint !== null) {
    query = query.in(
      "id",
      idConstraint.length > 0 ? idConstraint : [EMPTY_RESULT_UUID]
    );
  }

  if (search) {
    const escaped = escapePostgrestFilter(search);
    query = query.or(`name.ilike.%${escaped}%,supplier_code.ilike.%${escaped}%`);
  }
  if (country) {
    query = query.eq("country", country);
  }
  if (status === "active") query = query.eq("is_active", true);
  if (status === "inactive") query = query.eq("is_active", false);

  const { data, count, error } = await query;
  if (error) throw error;

  const rows = data ?? [];
  const supplierIds = rows.map((s) => s.id);

  // Active/inactive counts use the same visibility + Страна/МОЗ/Бренд scope as
  // the main query (but ignore status — these counts ARE the status breakdown —
  // and ignore search/pagination, since they describe the filtered universe).
  let countsQuery = supabase
    .from("suppliers")
    .select("is_active")
    .eq("organization_id", orgId);
  if (idConstraint !== null) {
    countsQuery = countsQuery.in(
      "id",
      idConstraint.length > 0 ? idConstraint : [EMPTY_RESULT_UUID]
    );
  }
  if (search) {
    const escaped = escapePostgrestFilter(search);
    countsQuery = countsQuery.or(
      `name.ilike.%${escaped}%,supplier_code.ilike.%${escaped}%`
    );
  }
  if (country) {
    countsQuery = countsQuery.eq("country", country);
  }

  const [assigneeMap, invoiceAggregates, allStatuses] = await Promise.all([
    fetchPrimaryAssignees(supplierIds),
    fetchInvoiceAggregatesForSuppliers(supplierIds),
    countsQuery,
  ]);

  const allList = allStatuses.data ?? [];
  const activeCount = allList.filter((s) => s.is_active !== false).length;
  const inactiveCount = allList.filter((s) => s.is_active === false).length;

  const items: SupplierListItem[] = rows.map((row) => {
    const aggregate = invoiceAggregates.get(row.id);
    return {
      id: row.id,
      name: row.name,
      country: row.country,
      is_active: row.is_active !== false,
      assignee_name: assigneeMap.get(row.id) ?? null,
      last_invoice_at: aggregate?.last_invoice_at ?? null,
      invoice_total_usd: aggregate?.invoice_total_usd ?? null,
    };
  });

  return { data: items, total: count ?? 0, activeCount, inactiveCount };
}

/**
 * Filter-bar option lists for /suppliers (Testing 2 row 92): distinct Страна,
 * МОЗ (assignees), and Бренд values within the user's visible supplier scope.
 *
 * All three are scoped to the same role-based visibility as the list itself,
 * so a procurement-only user only sees countries/МОЗ/brands of suppliers they
 * are assigned to. Options are derived from the full visible universe (NOT the
 * current page), so picking a filter never hides the option that produced it.
 */
export async function fetchSupplierFilterOptions(
  orgId: string,
  user?: { id: string; roles: string[] }
): Promise<SupplierFilterOptions> {
  const supabase = createAdminClient();
  const untyped = getUntypedClient();

  // Role-based visibility scope (procurement-only users see only their own).
  let visibleIds: string[] | null = null;
  if (user && isProcurementOnly(user.roles)) {
    const supabaseAuth = await createClient();
    visibleIds = await getAssignedSupplierIds(supabaseAuth, user.id);
    if (visibleIds.length === 0) {
      return { countries: [], assignees: [], brands: [] };
    }
  }

  let suppliersQuery = supabase
    .from("suppliers")
    .select("id, country")
    .eq("organization_id", orgId);
  if (visibleIds !== null) {
    suppliersQuery = suppliersQuery.in("id", visibleIds);
  }

  const { data: supplierRows } = await suppliersQuery;
  const rows = supplierRows ?? [];
  const scopeIds = rows.map((r) => r.id);

  // Страна — distinct non-empty countries, RU-collated.
  const countries = [
    ...new Set(
      rows
        .map((r) => (r.country ?? "").trim())
        .filter((c) => c.length > 0)
    ),
  ].sort((a, b) => a.localeCompare(b, "ru"));

  if (scopeIds.length === 0) {
    return { countries, assignees: [], brands: [] };
  }

  // МОЗ + Бренд — both junction-table reads, scoped to the visible suppliers.
  const [assigneeRowsRes, brandRowsRes] = await Promise.all([
    untyped
      .from("supplier_assignees")
      .select("user_id")
      .in("supplier_id", scopeIds),
    supabase
      .from("brand_supplier_assignments")
      .select("brand")
      .in("supplier_id", scopeIds),
  ]);

  const assigneeUserIds = [
    ...new Set(
      ((assigneeRowsRes.data ?? []) as Array<{ user_id: string }>)
        .map((r) => r.user_id)
        .filter((id): id is string => Boolean(id))
    ),
  ];

  let assignees: { id: string; full_name: string }[] = [];
  if (assigneeUserIds.length > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", assigneeUserIds);
    assignees = (profiles ?? [])
      .map((p) => ({ id: p.user_id, full_name: p.full_name ?? "" }))
      .filter((p) => p.full_name.length > 0)
      .sort((a, b) => a.full_name.localeCompare(b.full_name, "ru"));
  }

  const brands = [
    ...new Set(
      ((brandRowsRes.data ?? []) as Array<{ brand: string | null }>)
        .map((r) => (r.brand ?? "").trim())
        .filter((b) => b.length > 0)
    ),
  ].sort((a, b) => a.localeCompare(b, "ru"));

  return { countries, assignees, brands };
}

/**
 * Checks if a procurement-only user is allowed to view a specific supplier.
 * Non-procurement-only roles always return true (visibility handled elsewhere).
 */
export async function canAccessSupplier(
  supplierId: string,
  user: { id: string; roles: string[] }
): Promise<boolean> {
  if (!isProcurementOnly(user.roles)) return true;

  const supabase = await createClient();
  const assignedIds = await getAssignedSupplierIds(supabase, user.id);
  return assignedIds.includes(supplierId);
}

export async function fetchSupplierDetail(
  id: string
): Promise<SupplierDetail | null> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("suppliers")
    .select("*")
    .eq("id", id)
    .single();
  if (error) return null;

  return {
    id: data.id,
    organization_id: data.organization_id,
    name: data.name,
    supplier_code: data.supplier_code,
    country: data.country,
    // country_code added in migration 295, not yet in generated types
    country_code:
      (data as unknown as Record<string, unknown>).country_code as string | null ?? null,
    city: data.city,
    // registration_number added in migration 217, not yet in generated types
    registration_number: (data as unknown as Record<string, unknown>).registration_number as string | null ?? null,
    default_payment_terms: data.default_payment_terms,
    notes: (data as unknown as Record<string, unknown>).notes as string | null ?? null,
    is_active: data.is_active !== false,
    created_at: data.created_at ?? "",
    updated_at: data.updated_at,
  } as SupplierDetail;
}

export async function fetchSupplierContacts(
  supplierId: string
): Promise<SupplierContact[]> {
  const untyped = getUntypedClient();
  const { data, error } = await untyped
    .from("supplier_contacts")
    .select("*")
    .eq("supplier_id", supplierId)
    .order("is_primary", { ascending: false })
    .order("name");
  if (error) throw error;
  return (data ?? []) as SupplierContact[];
}

export async function fetchBrandAssignments(
  supplierId: string
): Promise<BrandAssignment[]> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("brand_supplier_assignments")
    .select("id, brand, supplier_id, is_primary, notes, created_at")
    .eq("supplier_id", supplierId)
    .order("brand");
  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    brand: row.brand,
    supplier_id: row.supplier_id,
    is_primary: row.is_primary ?? false,
    notes: row.notes,
    created_at: row.created_at,
  }));
}

export async function fetchSupplierAssignees(
  supplierId: string
): Promise<SupplierAssignee[]> {
  const untyped = getUntypedClient();
  const supabase = createAdminClient();

  const { data, error } = await untyped
    .from("supplier_assignees")
    .select("supplier_id, user_id, created_at")
    .eq("supplier_id", supplierId);
  if (error) throw error;

  const rows = (data ?? []) as Array<{ supplier_id: string; user_id: string; created_at: string }>;
  if (rows.length === 0) return [];

  // Resolve user names
  const userIds = rows.map((r) => r.user_id);
  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", userIds);

  const nameMap = new Map(
    (profiles ?? []).map((p) => [p.user_id, p.full_name ?? ""])
  );

  return rows.map((row) => ({
    user_id: row.user_id,
    full_name: nameMap.get(row.user_id) ?? "",
    created_at: row.created_at,
  }));
}

export async function fetchSupplierQuoteItems(
  supplierId: string
): Promise<SupplierQuoteItem[]> {
  const supabase = createAdminClient();
  // Phase 5d Pattern C (design.md §2.3.2): read composed price data via
  // invoice_item_coverage → invoice_items. A supplier's positions are
  // the quote_items currently composed from that supplier's invoices
  // (i.e., quote_item.composition_selected_invoice_id equals an invoice
  // owned by this supplier). Legacy quote_items.supplier_id +
  // purchase_price_original / purchase_currency /
  // procurement_completed_at columns are dropped in migration 284.
  const { data, error } = await supabase
    .from("invoices")
    .select(
      "id, supplier_id, procurement_completed_at, " +
        "invoice_items!inner(" +
        "id, invoice_id, purchase_price_original, purchase_currency, " +
        "coverage:invoice_item_coverage!invoice_item_id(" +
        "quote_items!inner(" +
        "id, product_name, brand, supplier_sku, idn_sku, quantity, " +
        "composition_selected_invoice_id, created_at, " +
        "quotes!inner(idn_quote)" +
        ")" +
        ")" +
        ")"
    )
    .eq("supplier_id", supplierId)
    .order("created_at", { ascending: false })
    .limit(100);
  if (error) throw error;

  type QuoteItemRow = {
    id: string;
    product_name: string | null;
    brand: string | null;
    supplier_sku: string | null;
    idn_sku: string | null;
    quantity: number | null;
    composition_selected_invoice_id: string | null;
    created_at: string | null;
    quotes: { idn_quote: string } | null;
  };
  type CoverageRow = { quote_items: QuoteItemRow | null };
  type InvoiceItemRow = {
    id: string;
    invoice_id: string;
    purchase_price_original: number | null;
    purchase_currency: string | null;
    coverage: CoverageRow[] | null;
  };
  type InvoiceRow = {
    id: string;
    supplier_id: string;
    procurement_completed_at: string | null;
    invoice_items: InvoiceItemRow[] | null;
  };

  const rows: SupplierQuoteItem[] = [];
  for (const invoice of (data ?? []) as unknown as InvoiceRow[]) {
    for (const ii of invoice.invoice_items ?? []) {
      for (const cov of ii.coverage ?? []) {
        const qi = cov.quote_items;
        if (!qi) continue;
        // Only include quote_items whose composition pointer selects this
        // invoice — otherwise the quote_item is currently "sourced from"
        // a different supplier.
        if (qi.composition_selected_invoice_id !== invoice.id) continue;
        rows.push({
          id: qi.id,
          product_name: qi.product_name,
          brand: qi.brand,
          sku: qi.supplier_sku,
          idn_sku: qi.idn_sku,
          quantity: qi.quantity,
          purchase_price: ii.purchase_price_original,
          purchase_currency: ii.purchase_currency,
          procurement_date: invoice.procurement_completed_at,
          quote_idn: qi.quotes?.idn_quote ?? "—",
        });
      }
    }
  }
  return rows;
}

/**
 * Fetch procurement users in the org (for assignee management dropdown).
 */
export async function fetchProcurementUsers(
  orgId: string
): Promise<{ id: string; full_name: string }[]> {
  const supabase = createAdminClient();

  // Get user IDs with procurement roles
  const { data: roleUsers } = await supabase
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId)
    .in("roles.slug", ["procurement", "procurement_senior", "head_of_procurement"]);

  const userIds = [...new Set((roleUsers ?? []).map((r) => r.user_id))];
  if (userIds.length === 0) return [];

  // Drop fired/deleted users (banned_until in the future or deleted_at set in
  // auth.users) so РОЗ cannot assign suppliers to уволенных закупщиков.
  const activeIds = await fetchActiveAuthUserIds(supabase, userIds);
  const filteredIds = userIds.filter((id) => activeIds.has(id));
  if (filteredIds.length === 0) return [];

  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", filteredIds)
    .order("full_name");

  return (profiles ?? []).map((p) => ({
    id: p.user_id,
    full_name: p.full_name ?? "",
  }));
}
