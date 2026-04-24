import { createAdminClient, createClient } from "@/shared/lib/supabase/server";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";
import { isProcurementOnly } from "@/shared/lib/roles";
import { getAssignedSupplierIds } from "@/shared/lib/access";
import type {
  SupplierListItem,
  SupplierDetail,
  SupplierContact,
  BrandAssignment,
  SupplierAssignee,
  SupplierQuoteItem,
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

interface ContactRow {
  supplier_id: string;
  name: string;
  email: string | null;
}

async function fetchPrimaryContactsForSuppliers(
  supplierIds: string[]
): Promise<ContactRow[]> {
  if (supplierIds.length === 0) return [];
  const untyped = getUntypedClient();
  const { data } = await untyped
    .from("supplier_contacts")
    .select("supplier_id, name, email")
    .in("supplier_id", supplierIds)
    .eq("is_primary", true);
  return (data ?? []) as ContactRow[];
}

export async function fetchSuppliersList(
  orgId: string,
  params: {
    search?: string;
    country?: string;
    status?: string;
    page?: number;
  },
  user?: { id: string; roles: string[] }
): Promise<{ data: SupplierListItem[]; total: number; activeCount: number; inactiveCount: number }> {
  const supabase = createAdminClient();
  const { search = "", country = "", status = "", page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  // Resolve assigned IDs once for procurement-only users (used for both list + counts)
  let assignedIds: string[] | null = null;
  if (user && isProcurementOnly(user.roles)) {
    const supabaseAuth = await createClient();
    assignedIds = await getAssignedSupplierIds(supabaseAuth, user.id);
  }

  let query = supabase
    .from("suppliers")
    .select("id, name, supplier_code, country, city, is_active", {
      count: "exact",
    })
    .eq("organization_id", orgId)
    .order("name")
    .range(from, to);

  // Role-based filtering via supplier_assignees junction table.
  if (assignedIds !== null) {
    query = query.in("id", assignedIds.length > 0 ? assignedIds : [EMPTY_RESULT_UUID]);
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

  // Fetch primary contacts and active/inactive counts in parallel
  // Counts query uses same visibility filter as main query
  let countsQuery = supabase
    .from("suppliers")
    .select("is_active")
    .eq("organization_id", orgId);
  if (assignedIds !== null) {
    countsQuery = countsQuery.in("id", assignedIds.length > 0 ? assignedIds : [EMPTY_RESULT_UUID]);
  }

  const [contactsResult, allStatuses] = await Promise.all([
    fetchPrimaryContactsForSuppliers(supplierIds),
    countsQuery,
  ]);

  const contactMap = new Map(
    contactsResult.map((c: ContactRow) => [c.supplier_id, { name: c.name, email: c.email }])
  );

  const allList = allStatuses.data ?? [];
  const activeCount = allList.filter((s) => s.is_active !== false).length;
  const inactiveCount = allList.filter((s) => s.is_active === false).length;

  const items: SupplierListItem[] = rows.map((row) => {
    const contact = contactMap.get(row.id);
    return {
      id: row.id,
      name: row.name,
      supplier_code: row.supplier_code,
      country: row.country,
      city: row.city,
      registration_number: null,
      is_active: row.is_active !== false,
      primary_contact_name: contact?.name ?? null,
      primary_contact_email: contact?.email ?? null,
    };
  });

  return { data: items, total: count ?? 0, activeCount, inactiveCount };
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

  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", userIds)
    .order("full_name");

  return (profiles ?? []).map((p) => ({
    id: p.user_id,
    full_name: p.full_name ?? "",
  }));
}
