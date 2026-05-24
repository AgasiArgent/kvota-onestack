import { createClient } from "@/shared/lib/supabase/server";
import {
  isSalesOnly,
  isAssignedItemsOnly,
  isProcurementSeniorOnly,
  isCustomsOnly,
} from "@/shared/lib/roles";
import { getAssignedCustomerIds, getAssignedQuoteIds } from "@/shared/lib/access";
import { getWorkflowStatusFilterOptions } from "@/shared/lib/workflow-statuses";
import type { QuoteListItem, QuotesFilterParams, QuotesListResult } from "./types";

const DEFAULT_PAGE_SIZE = 20;

type QuoteAccessUser = {
  id: string;
  roles: string[];
  orgId: string;
  salesGroupId?: string | null;
};

export async function fetchQuotesList(
  params: QuotesFilterParams,
  user: QuoteAccessUser
): Promise<QuotesListResult> {
  const supabase = await createClient();
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // Build base query — select scalar columns only (FK joins resolved separately).
  // `total_quote_currency` is the canonical column written by
  // api/quotes.calculate_quote (see line ~347). The legacy duplicate
  // `total_amount_quote` was dropped in migration 318.
  let query = supabase
    .from("quotes")
    .select(
      "id, idn_quote, created_at, workflow_status, total_quote_currency, total_profit_usd, currency, customer_id, created_by, version_count, current_version, assigned_logistics_user, assigned_customs_user",
      { count: "exact" }
    )
    .eq("organization_id", user.orgId)
    .is("deleted_at", null);

  // Apply sorting — supported keys map to DB columns
  const sortField = params.sort?.replace(/^-/, "") ?? "created_at";
  const sortAsc = params.sort ? !params.sort.startsWith("-") : false;
  const sortColumn =
    sortField === "amount" ? "total_quote_currency" : "created_at";
  query = query.order(sortColumn, { ascending: sortAsc });

  // Role-based filtering per .kiro/steering/access-control.md:
  if (isCustomsOnly(user.roles)) {
    query = query.in("workflow_status", [
      "pending_customs",
      "pending_logistics_and_customs",
    ]);
  } else if (isAssignedItemsOnly(user.roles)) {
    const assignedQuoteIds = await getAssignedQuoteIds(supabase, user);
    if (assignedQuoteIds.length > 0) {
      query = query.in("id", assignedQuoteIds);
    } else {
      query = query.eq("id", "00000000-0000-0000-0000-000000000000");
    }
  } else if (isSalesOnly(user.roles)) {
    const assignedCustomerIds = await getAssignedCustomerIds(supabase, user);
    if (assignedCustomerIds.length > 0) {
      query = query.or(
        `created_by.eq.${user.id},customer_id.in.(${assignedCustomerIds.join(",")})`
      );
    } else {
      query = query.eq("created_by", user.id);
    }
  } else if (isProcurementSeniorOnly(user.roles)) {
    query = query.eq("workflow_status", "pending_procurement");
  }

  // Status filter — multi-value IN; default excludes cancelled
  if (params.status && params.status.length > 0) {
    query = query.in("workflow_status", params.status as string[]);
  } else {
    query = query.neq("workflow_status", "cancelled");
  }

  // Customer filter — multi-value IN
  if (params.customer && params.customer.length > 0) {
    query = query.in("customer_id", params.customer as string[]);
  }

  // Sales manager filter — multi-value IN
  if (params.manager && params.manager.length > 0) {
    query = query.in("created_by", params.manager as string[]);
  }

  // Amount range filter — uses the populated `total_quote_currency` column
  // (see SELECT alias above).
  if (params.amount_min !== undefined) {
    query = query.gte("total_quote_currency", params.amount_min);
  }
  if (params.amount_max !== undefined) {
    query = query.lte("total_quote_currency", params.amount_max);
  }

  // Brand filter — resolve to quote IDs via quote_items pre-query
  if (params.brand && params.brand.length > 0) {
    const { data: brandItems } = await supabase
      .from("quote_items")
      .select("quote_id")
      .in("brand", params.brand as string[]);
    const brandQuoteIds = Array.from(
      new Set((brandItems ?? []).map((i) => i.quote_id))
    );
    if (brandQuoteIds.length > 0) {
      query = query.in("id", brandQuoteIds);
    } else {
      query = query.eq("id", "00000000-0000-0000-0000-000000000000");
    }
  }

  // Procurement manager filter — resolve via quote_items
  if (params.procurement_manager && params.procurement_manager.length > 0) {
    const { data: pmItems } = await supabase
      .from("quote_items")
      .select("quote_id")
      .in("assigned_procurement_user", params.procurement_manager as string[]);
    const pmQuoteIds = Array.from(
      new Set((pmItems ?? []).map((i) => i.quote_id))
    );
    if (pmQuoteIds.length > 0) {
      query = query.in("id", pmQuoteIds);
    } else {
      query = query.eq("id", "00000000-0000-0000-0000-000000000000");
    }
  }

  // Participants composite filter (combined МОП/МОЗ/МОЛ/МОТ)
  if (params.participants && params.participants.length > 0) {
    const byRole: Record<string, string[]> = {
      sales: [],
      procurement: [],
      logistics: [],
      customs: [],
    };
    for (const composite of params.participants) {
      const [role, userId] = composite.split(":");
      if (role && userId && byRole[role]) {
        byRole[role].push(userId);
      }
    }

    // For each role with selections, compute the set of quote IDs that match.
    // Then combine with OR (union) or AND (intersection) depending on logic.
    const roleQuoteIdSets: Set<string>[] = [];

    if (byRole.sales.length > 0) {
      const { data } = await supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", user.orgId)
        .is("deleted_at", null)
        .in("created_by", byRole.sales);
      roleQuoteIdSets.push(new Set((data ?? []).map((r) => r.id)));
    }

    if (byRole.procurement.length > 0) {
      const { data } = await supabase
        .from("quote_items")
        .select("quote_id")
        .in("assigned_procurement_user", byRole.procurement);
      roleQuoteIdSets.push(new Set((data ?? []).map((r) => r.quote_id)));
    }

    if (byRole.logistics.length > 0) {
      const { data } = await supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", user.orgId)
        .is("deleted_at", null)
        .in("assigned_logistics_user", byRole.logistics);
      roleQuoteIdSets.push(new Set((data ?? []).map((r) => r.id)));
    }

    if (byRole.customs.length > 0) {
      const { data } = await supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", user.orgId)
        .is("deleted_at", null)
        .in("assigned_customs_user", byRole.customs);
      roleQuoteIdSets.push(new Set((data ?? []).map((r) => r.id)));
    }

    if (roleQuoteIdSets.length > 0) {
      const logic = params.participants_logic === "and" ? "and" : "or";
      let resultIds: Set<string>;
      if (logic === "and") {
        // Intersection: a quote must be in every set
        resultIds = new Set(roleQuoteIdSets[0]);
        for (let i = 1; i < roleQuoteIdSets.length; i++) {
          for (const id of [...resultIds]) {
            if (!roleQuoteIdSets[i].has(id)) resultIds.delete(id);
          }
        }
      } else {
        // Union: a quote is included if it appears in any set
        resultIds = new Set();
        for (const set of roleQuoteIdSets) {
          for (const id of set) resultIds.add(id);
        }
      }

      if (resultIds.size > 0) {
        query = query.in("id", Array.from(resultIds));
      } else {
        query = query.eq("id", "00000000-0000-0000-0000-000000000000");
      }
    }
  }

  // Global search — idn_quote, customer name, or brand name
  if (params.search) {
    const term = params.search.trim();
    if (term.length > 0) {
      // Find matching customer IDs
      const { data: matchingCustomers } = await supabase
        .from("customers")
        .select("id")
        .eq("organization_id", user.orgId)
        .ilike("name", `%${term}%`);
      const matchingCustomerIds = (matchingCustomers ?? []).map((c) => c.id);

      // Find quote IDs with matching brands
      const { data: matchingBrandItems } = await supabase
        .from("quote_items")
        .select("quote_id")
        .ilike("brand", `%${term}%`);
      const matchingBrandQuoteIds = Array.from(
        new Set((matchingBrandItems ?? []).map((i) => i.quote_id))
      );

      const orParts: string[] = [`idn_quote.ilike.%${term}%`];
      if (matchingCustomerIds.length > 0) {
        orParts.push(`customer_id.in.(${matchingCustomerIds.join(",")})`);
      }
      if (matchingBrandQuoteIds.length > 0) {
        orParts.push(`id.in.(${matchingBrandQuoteIds.join(",")})`);
      }
      query = query.or(orParts.join(","));
    }
  }

  // Apply pagination
  query = query.range(offset, offset + pageSize - 1);

  const { data, count, error } = await query;
  if (error) throw error;

  const rows = data ?? [];

  // Batch-resolve customer names, manager names, and quote_items aggregations
  const customerIds = Array.from(
    new Set(
      rows.map((r) => r.customer_id).filter((id): id is string => id !== null)
    )
  );
  const managerIds = Array.from(
    new Set(
      rows.map((r) => r.created_by).filter((id): id is string => id !== null)
    )
  );
  const quoteIds = rows.map((r) => r.id);

  const [customersResult, managersResult, itemsResult] = await Promise.all([
    customerIds.length > 0
      ? supabase.from("customers").select("id, name").in("id", customerIds)
      : Promise.resolve({ data: [] as { id: string; name: string }[], error: null }),
    managerIds.length > 0
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", managerIds)
      : Promise.resolve({
          data: [] as { user_id: string; full_name: string | null }[],
          error: null,
        }),
    quoteIds.length > 0
      ? supabase
          .from("quote_items")
          .select("quote_id, brand, assigned_procurement_user")
          .in("quote_id", quoteIds)
      : Promise.resolve({
          data: [] as { quote_id: string; brand: string | null; assigned_procurement_user: string | null }[],
          error: null,
        }),
  ]);

  if (customersResult.error)
    console.error("Failed to fetch customers:", customersResult.error);
  if (managersResult.error)
    console.error("Failed to fetch managers:", managersResult.error);

  // Build brands + procurement user aggregation maps
  const brandsByQuote = new Map<string, Set<string>>();
  const procUsersByQuote = new Map<string, Set<string>>();
  const allProcUserIds = new Set<string>();
  for (const item of (itemsResult.data ?? []) as Array<{
    quote_id: string;
    brand: string | null;
    assigned_procurement_user: string | null;
  }>) {
    if (item.brand) {
      if (!brandsByQuote.has(item.quote_id)) brandsByQuote.set(item.quote_id, new Set());
      brandsByQuote.get(item.quote_id)!.add(item.brand);
    }
    if (item.assigned_procurement_user) {
      if (!procUsersByQuote.has(item.quote_id)) procUsersByQuote.set(item.quote_id, new Set());
      procUsersByQuote.get(item.quote_id)!.add(item.assigned_procurement_user);
      allProcUserIds.add(item.assigned_procurement_user);
    }
  }

  // Collect logistics + customs user IDs from quote rows
  const logisticsUserIds = new Set<string>();
  const customsUserIds = new Set<string>();
  for (const row of rows as unknown as Array<{
    assigned_logistics_user: string | null;
    assigned_customs_user: string | null;
  }>) {
    if (row.assigned_logistics_user) logisticsUserIds.add(row.assigned_logistics_user);
    if (row.assigned_customs_user) customsUserIds.add(row.assigned_customs_user);
  }

  // Second round: resolve procurement + logistics + customs user names together
  const secondRoundUserIds = new Set<string>([
    ...allProcUserIds,
    ...logisticsUserIds,
    ...customsUserIds,
  ]);

  const extraUsersResult = secondRoundUserIds.size > 0
    ? await supabase
        .from("user_profiles")
        .select("user_id, full_name")
        .in("user_id", Array.from(secondRoundUserIds))
    : { data: [] as { user_id: string; full_name: string | null }[], error: null };

  const customers = customersResult.data ?? [];
  const managers = managersResult.data ?? [];
  const extraUsers = extraUsersResult.data ?? [];

  const customerMap = new Map(
    customers.map((c) => [c.id, { id: c.id, name: c.name }])
  );
  const managerMap = new Map(
    managers.map((m) => [
      m.user_id,
      { id: m.user_id, full_name: m.full_name ?? "" },
    ])
  );
  // extraUsers contains procurement + logistics + customs users (batched together)
  const extraUserMap = new Map(
    extraUsers.map((m) => [
      m.user_id,
      { id: m.user_id, full_name: m.full_name ?? "" },
    ])
  );

  const items: QuoteListItem[] = rows.map((row) => {
    const procIds = Array.from(procUsersByQuote.get(row.id) ?? []);
    const rawRow = row as unknown as {
      assigned_logistics_user: string | null;
      assigned_customs_user: string | null;
    };
    return {
      id: row.id,
      idn_quote: row.idn_quote,
      created_at: row.created_at ?? "",
      workflow_status: row.workflow_status ?? "draft",
      total_quote_currency: row.total_quote_currency,
      total_profit_usd: row.total_profit_usd,
      currency: row.currency,
      customer: row.customer_id ? customerMap.get(row.customer_id) ?? null : null,
      manager: row.created_by ? managerMap.get(row.created_by) ?? null : null,
      version_count: row.version_count ?? 0,
      current_version: row.current_version ?? 1,
      brands: Array.from(brandsByQuote.get(row.id) ?? []),
      procurement_managers: procIds
        .map((uid) => extraUserMap.get(uid))
        .filter((m): m is { id: string; full_name: string } => m != null),
      logistics_user: rawRow.assigned_logistics_user
        ? extraUserMap.get(rawRow.assigned_logistics_user) ?? null
        : null,
      customs_user: rawRow.assigned_customs_user
        ? extraUserMap.get(rawRow.assigned_customs_user) ?? null
        : null,
    };
  });

  return {
    data: items,
    total: count ?? 0,
    page,
    pageSize,
  };
}

// ---------------------------------------------------------------------------
// Quote Detail queries (for quote detail page migration)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Inferred return types for query functions (derived from actual DB schema)
// ---------------------------------------------------------------------------

export type QuoteDetailRow = NonNullable<
  Awaited<ReturnType<typeof fetchQuoteDetail>>
>;
export type QuoteItemRow = Awaited<
  ReturnType<typeof fetchQuoteItems>
>[number];
export type QuoteInvoiceRow = Awaited<
  ReturnType<typeof fetchQuoteInvoices>
>[number];

export async function fetchQuoteDetail(quoteId: string) {
  const supabase = await createClient();

  const { data: quote, error } = await supabase
    .from("quotes")
    .select("*")
    .eq("id", quoteId)
    .is("deleted_at", null)
    .single();

  if (error || !quote) return null;

  // Resolve FKs in parallel (same pattern as customer detail)
  const [customerRes, contactRes, sellerRes, creatorRes] = await Promise.all([
    quote.customer_id
      ? supabase
          .from("customers")
          .select("id, name, inn")
          .eq("id", quote.customer_id)
          .single()
      : null,
    quote.contact_person_id
      ? supabase
          .from("customer_contacts")
          .select("id, name, last_name, patronymic, phone, email")
          .eq("id", quote.contact_person_id)
          .single()
      : null,
    quote.seller_company_id
      ? supabase
          .from("buyer_companies")
          .select("id, name, company_code")
          .eq("id", quote.seller_company_id)
          .single()
      : null,
    quote.created_by
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .eq("user_id", quote.created_by)
          .single()
      : null,
  ]);

  return {
    ...quote,
    customer: customerRes?.data ?? null,
    contact_person: contactRes?.data ?? null,
    seller_company: sellerRes?.data ?? null,
    created_by_profile: creatorRes?.data
      ? { id: creatorRes.data.user_id, full_name: creatorRes.data.full_name ?? "" }
      : null,
  };
}

export async function fetchQuoteItems(quoteId: string) {
  const supabase = await createClient();

  const { data } = await supabase
    .from("quote_items")
    .select("*")
    .eq("quote_id", quoteId)
    .order("position", { ascending: true });

  return data ?? [];
}

export async function fetchQuoteInvoices(quoteId: string) {
  const supabase = await createClient();

  const { data: invoices } = await supabase
    .from("invoices")
    .select("*")
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: true });

  if (!invoices?.length) return [];

  // Batch-resolve supplier + buyer + supplier_contact FKs
  const supplierIds = [
    ...new Set(invoices.map((i) => i.supplier_id).filter(Boolean)),
  ] as string[];
  const buyerIds = [
    ...new Set(invoices.map((i) => i.buyer_company_id).filter(Boolean)),
  ] as string[];
  // Testing 2 row 21: supplier_contact_id (migration 315) joined here so the
  // КПП card and downstream consumers can show the named contact + реквизиты
  // without an extra round-trip per invoice.
  const supplierContactIds = [
    ...new Set(invoices.map((i) => i.supplier_contact_id).filter(Boolean)),
  ] as string[];

  // Testing 2 row 14 v4: per-invoice cargo places are entered by procurement
  // in invoice-create-modal and live in kvota.invoice_cargo_places. The
  // invoice-level length_m/width_m/height_m triple is almost never filled,
  // but boxes always are. We batch-fetch them here so logistics + customs
  // can render «Мест: N» + per-box dimensions in InvoiceCargoSummary.
  const invoiceIds = invoices.map((i) => i.id);

  // Testing 2 row 71: customs cargo info needs 4 totals from the supplier
  // КП — Валюта КПП / Стоимость / Кол-во / Ед.изм. Currency is invoice-level
  // already. The other three are aggregates over invoice_items joined with
  // quote_items (for `unit`). We batch one extra round-trip here and roll
  // it up per-invoice in JS — Supabase REST has no SUM/GROUP BY syntax
  // exposed to the client.
  //
  // The cast is the same `any`-hop pattern used in mutations.ts for
  // invoice_items + invoice_item_coverage — migrations 281/282 added them
  // but database.types.ts has not been regenerated yet (verified 2026-05-23).
  const invoiceItemsRes = invoiceIds.length
    ? // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ((await (supabase as any)
        .from("invoice_items")
        .select(
          "invoice_id, quantity, purchase_price_original, purchase_currency, invoice_item_coverage!inner(quote_items!inner(unit))"
        )
        .in("invoice_id", invoiceIds)) as {
        data:
          | Array<{
              invoice_id: string;
              quantity: number | null;
              purchase_price_original: number | null;
              purchase_currency: string | null;
              invoice_item_coverage: Array<{
                quote_items: { unit: string | null } | null;
              }>;
            }>
          | null;
      })
    : { data: [] };

  const [suppliersRes, buyersRes, supplierContactsRes, cargoPlacesRes] =
    await Promise.all([
      supplierIds.length
        ? supabase.from("suppliers").select("id, name").in("id", supplierIds)
        : null,
      buyerIds.length
        ? supabase
            .from("buyer_companies")
            .select("id, name, company_code")
            .in("id", buyerIds)
        : null,
      supplierContactIds.length
        ? supabase
            .from("supplier_contacts")
            .select("id, name, position, email, phone")
            .in("id", supplierContactIds)
        : null,
      supabase
        .from("invoice_cargo_places")
        .select(
          "id, invoice_id, position, weight_kg, length_mm, width_mm, height_mm"
        )
        .in("invoice_id", invoiceIds)
        .order("position", { ascending: true }),
    ]);

  const supplierMap = new Map(
    (suppliersRes?.data ?? []).map((s) => [s.id, s])
  );
  const buyerMap = new Map((buyersRes?.data ?? []).map((b) => [b.id, b]));
  const supplierContactMap = new Map(
    (supplierContactsRes?.data ?? []).map((c) => [c.id, c])
  );
  const cargoPlacesByInvoice = new Map<string, CargoPlace[]>();
  for (const place of cargoPlacesRes?.data ?? []) {
    const list = cargoPlacesByInvoice.get(place.invoice_id) ?? [];
    list.push(place);
    cargoPlacesByInvoice.set(place.invoice_id, list);
  }

  // Roll up invoice_items into a per-invoice aggregate that the cargo
  // summary panel reads as a single struct. We keep nulls when no row
  // contributes a value so the UI can show "—" instead of "0" and the
  // user can tell "no data" apart from "explicitly zero".
  const aggregatesByInvoice = new Map<string, InvoiceItemsAggregate>();
  for (const row of invoiceItemsRes.data ?? []) {
    const prev = aggregatesByInvoice.get(row.invoice_id) ?? {
      total_quantity: null,
      total_amount_original: null,
      currency: null,
      units: new Set<string>(),
    };
    if (row.quantity != null) {
      prev.total_quantity = (prev.total_quantity ?? 0) + row.quantity;
    }
    if (row.purchase_price_original != null && row.quantity != null) {
      prev.total_amount_original =
        (prev.total_amount_original ?? 0) +
        row.purchase_price_original * row.quantity;
    }
    // Use the first non-null purchase_currency we see; mixed-currency КПП
    // are rare and the supplier's amount in their own currency is what
    // matters for the cargo panel.
    if (!prev.currency && row.purchase_currency) {
      prev.currency = row.purchase_currency;
    }
    for (const cov of row.invoice_item_coverage ?? []) {
      const unit = cov.quote_items?.unit?.trim();
      if (unit) prev.units.add(unit);
    }
    aggregatesByInvoice.set(row.invoice_id, prev);
  }

  return invoices.map((inv) => {
    const agg = aggregatesByInvoice.get(inv.id);
    return {
      ...inv,
      supplier:
        (inv.supplier_id && supplierMap.get(inv.supplier_id)) || null,
      buyer_company:
        (inv.buyer_company_id && buyerMap.get(inv.buyer_company_id)) || null,
      supplier_contact:
        (inv.supplier_contact_id && supplierContactMap.get(inv.supplier_contact_id)) || null,
      cargo_places: cargoPlacesByInvoice.get(inv.id) ?? [],
      items_aggregate: agg
        ? ({
            total_quantity: agg.total_quantity,
            total_amount_original: agg.total_amount_original,
            // Prefer the invoice's own currency (set at КПП creation) over
            // the per-item purchase_currency when both are present. The
            // per-item value is the fallback for legacy КП whose top-level
            // currency was left null.
            currency: inv.currency ?? agg.currency ?? null,
            units: Array.from(agg.units).sort(),
          } satisfies InvoiceItemsAggregateExport)
        : null,
    };
  });
}

/**
 * Per-invoice rollup of `kvota.invoice_items` used by the cargo info panel
 * on the logistics + customs steps (Testing 2 row 71). Surfaces the four
 * fields the tester flagged as «Данных нет»:
 *   - currency (Валюта КПП)
 *   - total_amount_original (Стоимость, in `currency`)
 *   - total_quantity (Кол-во)
 *   - units (Ед.изм., aggregated across covered quote_items)
 *
 * `total_quantity` / `total_amount_original` are nullable so the UI can
 * distinguish "no data yet" from "explicit zero". `units` is empty when
 * none of the covered quote_items have a unit string set.
 */
export interface InvoiceItemsAggregateExport {
  total_quantity: number | null;
  total_amount_original: number | null;
  currency: string | null;
  units: string[];
}

// Internal staging shape — mutates a Set while rolling up.
interface InvoiceItemsAggregate {
  total_quantity: number | null;
  total_amount_original: number | null;
  currency: string | null;
  units: Set<string>;
}

/**
 * Cargo place row from kvota.invoice_cargo_places, exposed alongside the
 * invoice row so logistics + customs can render «Мест: N» and per-box
 * dimensions in InvoiceCargoSummary (Testing 2 row 14 v4).
 */
export interface CargoPlace {
  id: string;
  invoice_id: string;
  position: number;
  weight_kg: number | null;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
}

export type CalcVariablesRow = Awaited<
  ReturnType<typeof fetchQuoteCalcVariables>
>;

export async function fetchQuoteCalcVariables(quoteId: string) {
  const supabase = await createClient();

  const { data } = await supabase
    .from("quote_calculation_variables")
    .select("variables")
    .eq("quote_id", quoteId)
    .maybeSingle();

  return (data?.variables ?? null) as Record<string, unknown> | null;
}

export async function fetchQuoteComments(quoteId: string) {
  const supabase = await createClient();

  const { data: comments } = await supabase
    .from("quote_comments")
    .select("*")
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: true });

  if (!comments?.length) return [];

  const commentIds = comments.map((c) => c.id);

  // Batch-resolve user profiles + role slugs + attachments in parallel
  const userIds = [...new Set(comments.map((c) => c.user_id))];

  const [profilesRes, rolesRes, attachmentsRes] = await Promise.all([
    supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", userIds),
    // NOTE: role info lives in user_roles after migration 255 dropped
    // organization_members.role_id. A user may have multiple roles —
    // first one wins for display purposes.
    supabase
      .from("user_roles")
      .select("user_id, roles!inner(slug)")
      .in("user_id", userIds),
    supabase
      .from("documents")
      .select(
        "id, comment_id, original_filename, storage_path, mime_type, file_size_bytes"
      )
      .in("comment_id", commentIds),
  ]);

  const profileMap = new Map(
    (profilesRes.data ?? []).map((p) => [p.user_id, p])
  );
  const roleMap = new Map<string, string>();
  for (const row of rolesRes.data ?? []) {
    if (!roleMap.has(row.user_id)) {
      roleMap.set(
        row.user_id,
        (row.roles as unknown as { slug: string })?.slug ?? "unknown"
      );
    }
  }

  // Group attachments by comment_id
  const attachmentsByComment = new Map<
    string,
    Array<{
      id: string;
      original_filename: string;
      storage_path: string;
      mime_type: string | null;
      file_size_bytes: number | null;
    }>
  >();
  for (const att of attachmentsRes.data ?? []) {
    if (!att.comment_id) continue;
    const list = attachmentsByComment.get(att.comment_id) ?? [];
    list.push({
      id: att.id,
      original_filename: att.original_filename,
      storage_path: att.storage_path,
      mime_type: att.mime_type,
      file_size_bytes: att.file_size_bytes,
    });
    attachmentsByComment.set(att.comment_id, list);
  }

  return comments.map((c) => {
    const profile = profileMap.get(c.user_id);
    return {
      ...c,
      mentions: (c.mentions ?? null) as string[] | null,
      user_profile: profile
        ? {
            id: profile.user_id,
            full_name: profile.full_name ?? "",
            role_slug: roleMap.get(c.user_id) ?? "unknown",
          }
        : null,
      attachments: attachmentsByComment.get(c.id) ?? [],
    };
  });
}

// ---------------------------------------------------------------------------
// Stage deadline for a specific workflow status (for timer badge)
// ---------------------------------------------------------------------------

export interface StageDeadlineData {
  deadlineHours: number | null;
  stageEnteredAt: string | null;
  overrideHours: number | null;
}

const TERMINAL_STATUSES = new Set(["draft", "deal", "rejected", "cancelled"]);

/**
 * Fetch stage deadline data for the timer badge.
 *
 * `stage_entered_at`, `stage_deadline_override_hours` (on quotes) and
 * `stage_deadlines` table were added in migrations 238-240. The generated
 * types don't include them yet -- we cast through Record<string, unknown>
 * for the new columns until `npm run db:types` is re-run.
 */
export async function fetchStageDeadline(
  quoteId: string,
  orgId: string,
  workflowStatus: string
): Promise<StageDeadlineData> {
  if (TERMINAL_STATUSES.has(workflowStatus)) {
    return { deadlineHours: null, stageEnteredAt: null, overrideHours: null };
  }

  const supabase = await createClient();

  // quotes.select("*") returns all columns including the new ones,
  // but the TS type doesn't know about them yet.
  const quoteRes = await supabase
    .from("quotes")
    .select("*")
    .eq("id", quoteId)
    .is("deleted_at", null)
    .single();

  const quoteRow = quoteRes.data as Record<string, unknown> | null;

  // stage_deadlines table isn't in generated types yet.
  // PostgREST still serves it -- use the client with a type assertion.
  let deadlineHours: number | null = null;
  try {
    const fromFn = supabase.from.bind(supabase) as (
      table: string
    ) => ReturnType<typeof supabase.from>;
    const { data } = await fromFn("stage_deadlines")
      .select("deadline_hours")
      .eq("organization_id", orgId)
      .eq("stage", workflowStatus)
      .maybeSingle();
    deadlineHours = (data as Record<string, unknown> | null)?.deadline_hours as number ?? null;
  } catch (err) {
    console.error("[quote-queries] fetch stage deadline failed:", err);
    deadlineHours = null;
  }

  return {
    deadlineHours,
    stageEnteredAt: (quoteRow?.stage_entered_at as string) ?? null,
    overrideHours: (quoteRow?.stage_deadline_override_hours as number) ?? null,
  };
}

/**
 * Resolve the deal ID for a quote by traversing quotes -> specifications -> deals.
 * Returns null if the quote has no specification or the specification has no deal.
 */
export async function fetchDealIdForQuote(
  quoteId: string
): Promise<string | null> {
  const supabase = await createClient();

  // Find specification linked to this quote
  const { data: spec } = await supabase
    .from("specifications")
    .select("id")
    .eq("quote_id", quoteId)
    .is("deleted_at", null)
    .maybeSingle();

  if (!spec) return null;

  // Find deal linked to this specification
  const { data: deal } = await supabase
    .from("deals")
    .select("id")
    .eq("specification_id", spec.id)
    .is("deleted_at", null)
    .maybeSingle();

  return deal?.id ?? null;
}

/**
 * Checks if a user is allowed to view a specific quote.
 * Applies per-tier access checks:
 * - ASSIGNED_ITEMS: quote must have items assigned to user
 * - OWN/GROUP (sales): user must be creator or assigned to customer
 * - PROCUREMENT_STAGE_ONLY: quote must be in procurement stage
 * - All other roles: always allowed
 */
export async function canAccessQuote(
  quoteId: string,
  user: QuoteAccessUser
): Promise<boolean> {
  const supabase = await createClient();

  if (isCustomsOnly(user.roles)) {
    const { data } = await supabase
      .from("quotes")
      .select("workflow_status")
      .eq("id", quoteId)
      .eq("organization_id", user.orgId)
      .is("deleted_at", null)
      .maybeSingle();
    return (
      data?.workflow_status === "pending_customs" ||
      data?.workflow_status === "pending_logistics_and_customs"
    );
  }

  if (isAssignedItemsOnly(user.roles)) {
    const assignedQuoteIds = await getAssignedQuoteIds(supabase, user);
    return assignedQuoteIds.includes(quoteId);
  }

  if (isSalesOnly(user.roles)) {
    const { data } = await supabase
      .from("quotes")
      .select("created_by, customer_id")
      .eq("id", quoteId)
      .eq("organization_id", user.orgId)
      .is("deleted_at", null)
      .maybeSingle();

    if (!data) return false;
    if (data.created_by === user.id) return true;
    if (!data.customer_id) return false;

    const assignedCustomerIds = await getAssignedCustomerIds(supabase, user);
    return assignedCustomerIds.includes(data.customer_id);
  }

  if (isProcurementSeniorOnly(user.roles)) {
    const { data } = await supabase
      .from("quotes")
      .select("workflow_status")
      .eq("id", quoteId)
      .eq("organization_id", user.orgId)
      .is("deleted_at", null)
      .maybeSingle();
    return data?.workflow_status === "pending_procurement";
  }

  return true;
}

export interface ParticipantsOptions {
  sales: { id: string; full_name: string }[];
  procurement: { id: string; full_name: string }[];
  logistics: { id: string; full_name: string }[];
  customs: { id: string; full_name: string }[];
}

export async function fetchFilterOptions(
  orgId: string,
  user?: QuoteAccessUser
): Promise<{
  customers: { id: string; name: string }[];
  managers: { id: string; full_name: string }[];
  procurementManagers: { id: string; full_name: string }[];
  brands: string[];
  statuses: { value: string; label: string }[];
  participants: ParticipantsOptions;
}> {
  const supabase = await createClient();

  // First, fetch distinct customer_ids and created_by + quote IDs from quotes the user can see
  let quotesQuery = supabase
    .from("quotes")
    .select("id, customer_id, created_by")
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  // Apply same role scoping as fetchQuotesList
  if (user && isCustomsOnly(user.roles)) {
    quotesQuery = quotesQuery.in("workflow_status", [
      "pending_customs",
      "pending_logistics_and_customs",
    ]);
  } else if (user && isAssignedItemsOnly(user.roles)) {
    const assignedQuoteIds = await getAssignedQuoteIds(supabase, user);
    if (assignedQuoteIds.length > 0) {
      quotesQuery = quotesQuery.in("id", assignedQuoteIds);
    } else {
      quotesQuery = quotesQuery.eq("id", "00000000-0000-0000-0000-000000000000");
    }
  } else if (user && isSalesOnly(user.roles)) {
    const assignedIds = await getAssignedCustomerIds(supabase, user);
    if (assignedIds.length > 0) {
      quotesQuery = quotesQuery.or(
        `created_by.eq.${user.id},customer_id.in.(${assignedIds.join(",")})`
      );
    } else {
      quotesQuery = quotesQuery.eq("created_by", user.id);
    }
  } else if (user && isProcurementSeniorOnly(user.roles)) {
    quotesQuery = quotesQuery.eq("workflow_status", "pending_procurement");
  }

  const { data: quotesData, error: quotesError } = await quotesQuery;
  if (quotesError)
    console.error("Failed to fetch quote filter data:", quotesError);

  const quoteRows = quotesData ?? [];
  const customerIds = Array.from(
    new Set(
      quoteRows
        .map((r) => r.customer_id)
        .filter((id): id is string => id !== null)
    )
  );
  const managerIds = Array.from(
    new Set(
      quoteRows
        .map((r) => r.created_by)
        .filter((id): id is string => id !== null)
    )
  );

  // Batch-fetch customer names and manager names only for IDs that appear in quotes
  const [customersResult, managersResult] = await Promise.all([
    customerIds.length > 0
      ? supabase
          .from("customers")
          .select("id, name")
          .in("id", customerIds)
          .order("name")
      : Promise.resolve({ data: [] as { id: string; name: string }[], error: null }),
    managerIds.length > 0
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", managerIds)
          .order("full_name")
      : Promise.resolve({
          data: [] as { user_id: string; full_name: string | null }[],
          error: null,
        }),
  ]);

  if (customersResult.error)
    console.error("Failed to fetch filter customers:", customersResult.error);
  if (managersResult.error)
    console.error("Failed to fetch filter managers:", managersResult.error);

  const customers = (customersResult.data ?? []).map((c) => ({
    id: c.id,
    name: c.name,
  }));

  const managers = (managersResult.data ?? []).map((m) => ({
    id: m.user_id,
    full_name: m.full_name ?? "",
  }));

  // Fetch distinct brands and procurement user IDs from quote_items scoped to visible quotes
  const visibleQuoteIds = quoteRows.map((r) => r.id);
  let brands: string[] = [];
  let procurementManagers: { id: string; full_name: string }[] = [];

  if (visibleQuoteIds.length > 0) {
    const { data: itemsData } = await supabase
      .from("quote_items")
      .select("brand, assigned_procurement_user")
      .in("quote_id", visibleQuoteIds);

    const brandSet = new Set<string>();
    const procUserIds = new Set<string>();
    for (const item of (itemsData ?? []) as Array<{
      brand: string | null;
      assigned_procurement_user: string | null;
    }>) {
      if (item.brand) brandSet.add(item.brand);
      if (item.assigned_procurement_user)
        procUserIds.add(item.assigned_procurement_user);
    }
    brands = Array.from(brandSet).sort();

    if (procUserIds.size > 0) {
      const { data: procProfiles } = await supabase
        .from("user_profiles")
        .select("user_id, full_name")
        .in("user_id", Array.from(procUserIds))
        .order("full_name");
      procurementManagers = (procProfiles ?? []).map((p) => ({
        id: p.user_id,
        full_name: p.full_name ?? "",
      }));
    }
  }

  // Workflow status filter options come from a shared map so the table cell,
  // the dropdown, and any other surface stay in lockstep — see
  // `shared/lib/workflow-statuses.ts` for the single source of truth.
  const statuses = getWorkflowStatusFilterOptions();

  // Fetch all organization users grouped by role for the Participants filter.
  // This is deliberately broad — show every eligible user, not just those
  // already assigned to a quote.
  // head_of_logistics ↔ head_of_customs: dual-hat in this org (PR #105). Both
  // leads participate in both functions, so each appears in both groups.
  const ROLE_GROUPS: Record<keyof ParticipantsOptions, string[]> = {
    sales: ["sales", "head_of_sales"],
    procurement: ["procurement", "procurement_senior", "head_of_procurement"],
    logistics: ["logistics", "head_of_logistics", "head_of_customs"],
    customs: ["customs", "head_of_customs", "head_of_logistics"],
  };

  async function fetchUsersByRoleSlugs(slugs: string[]): Promise<{ id: string; full_name: string }[]> {
    const { data, error } = await supabase
      .from("user_roles")
      .select("user_id, roles!inner(slug)")
      .eq("organization_id", orgId)
      .in("roles.slug", slugs);
    if (error || !data) {
      console.error(`Failed to fetch users for roles ${slugs.join(",")}:`, error);
      return [];
    }
    const userIds = Array.from(
      new Set(data.map((r) => r.user_id))
    );
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

  const [salesUsers, procurementUsers, logisticsUsers, customsUsers] =
    await Promise.all([
      fetchUsersByRoleSlugs(ROLE_GROUPS.sales),
      fetchUsersByRoleSlugs(ROLE_GROUPS.procurement),
      fetchUsersByRoleSlugs(ROLE_GROUPS.logistics),
      fetchUsersByRoleSlugs(ROLE_GROUPS.customs),
    ]);

  const participants: ParticipantsOptions = {
    sales: salesUsers,
    procurement: procurementUsers,
    logistics: logisticsUsers,
    customs: customsUsers,
  };

  return { customers, managers, procurementManagers, brands, statuses, participants };
}
