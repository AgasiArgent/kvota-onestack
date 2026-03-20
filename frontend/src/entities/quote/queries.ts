import { createClient } from "@/shared/lib/supabase/server";
import type { QuoteListItem, QuotesFilterParams, QuotesListResult } from "./types";
import { getStatusesForGroup } from "./types";

const DEFAULT_PAGE_SIZE = 20;

const SALES_ROLES = ["sales", "head_of_sales"];

function isSalesOnly(roles: string[]): boolean {
  return (
    roles.some((r) => SALES_ROLES.includes(r)) &&
    !roles.some((r) =>
      [
        "admin",
        "top_manager",
        "procurement",
        "logistics",
        "customs",
        "quote_controller",
        "spec_controller",
        "finance",
        "head_of_procurement",
        "head_of_logistics",
      ].includes(r)
    )
  );
}

export async function fetchQuotesList(
  params: QuotesFilterParams,
  user: { id: string; roles: string[]; org_id: string }
): Promise<QuotesListResult> {
  const supabase = await createClient();
  const page = params.page ?? 1;
  const pageSize = params.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // Build base query — select scalar columns only (FK joins resolved separately)
  let query = supabase
    .from("quotes")
    .select(
      "id, idn_quote, created_at, workflow_status, total_amount_quote, total_profit_usd, currency, customer_id, created_by, version_count, current_version",
      { count: "exact" }
    )
    .eq("organization_id", user.org_id)
    .is("deleted_at", null)
    .order("created_at", { ascending: false });

  // Role-based filtering: sales users see only their own quotes + quotes for their assigned customers
  if (isSalesOnly(user.roles)) {
    const { data: assignedCustomers } = await supabase
      .from("customers")
      .select("id")
      .eq("organization_id", user.org_id)
      .eq("manager_id", user.id);

    const customerIds = (assignedCustomers ?? []).map((c) => c.id);

    if (customerIds.length > 0) {
      query = query.or(
        `created_by.eq.${user.id},customer_id.in.(${customerIds.join(",")})`
      );
    } else {
      query = query.eq("created_by", user.id);
    }
  }

  // Apply optional filters
  if (params.status) {
    const statuses = getStatusesForGroup(params.status);
    if (statuses.length > 0) {
      query = query.in("workflow_status", statuses);
    } else {
      // Treat as individual status value
      query = query.eq("workflow_status", params.status);
    }
  }

  if (params.customer) {
    query = query.eq("customer_id", params.customer);
  }

  if (params.manager) {
    query = query.eq("created_by", params.manager);
  }

  // Apply pagination
  query = query.range(offset, offset + pageSize - 1);

  const { data, count, error } = await query;
  if (error) throw error;

  const rows = data ?? [];

  // Batch-resolve customer names and manager names
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

  const [customersResult, managersResult] = await Promise.all([
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
  ]);

  if (customersResult.error)
    console.error("Failed to fetch customers:", customersResult.error);
  if (managersResult.error)
    console.error("Failed to fetch managers:", managersResult.error);

  const customers = customersResult.data ?? [];
  const managers = managersResult.data ?? [];

  const customerMap = new Map(
    customers.map((c) => [c.id, { id: c.id, name: c.name }])
  );
  const managerMap = new Map(
    managers.map((m) => [
      m.user_id,
      { id: m.user_id, full_name: m.full_name ?? "" },
    ])
  );

  const items: QuoteListItem[] = rows.map((row) => ({
    id: row.id,
    idn_quote: row.idn_quote,
    created_at: row.created_at ?? "",
    workflow_status: row.workflow_status ?? "draft",
    total_amount_quote: row.total_amount_quote,
    total_profit_usd: row.total_profit_usd,
    currency: row.currency,
    customer: row.customer_id ? customerMap.get(row.customer_id) ?? null : null,
    manager: row.created_by ? managerMap.get(row.created_by) ?? null : null,
    version_count: row.version_count ?? 0,
    current_version: row.current_version ?? 1,
  }));

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
          .select("id, name, phone, email")
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
    .order("created_at", { ascending: true });

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

  // Batch-resolve supplier + buyer FKs
  const supplierIds = [
    ...new Set(invoices.map((i) => i.supplier_id).filter(Boolean)),
  ] as string[];
  const buyerIds = [
    ...new Set(invoices.map((i) => i.buyer_company_id).filter(Boolean)),
  ] as string[];

  const [suppliersRes, buyersRes] = await Promise.all([
    supplierIds.length
      ? supabase.from("suppliers").select("id, name").in("id", supplierIds)
      : null,
    buyerIds.length
      ? supabase
          .from("buyer_companies")
          .select("id, name, company_code")
          .in("id", buyerIds)
      : null,
  ]);

  const supplierMap = new Map(
    (suppliersRes?.data ?? []).map((s) => [s.id, s])
  );
  const buyerMap = new Map((buyersRes?.data ?? []).map((b) => [b.id, b]));

  return invoices.map((inv) => ({
    ...inv,
    supplier:
      (inv.supplier_id && supplierMap.get(inv.supplier_id)) || null,
    buyer_company:
      (inv.buyer_company_id && buyerMap.get(inv.buyer_company_id)) || null,
  }));
}

export async function fetchQuoteComments(quoteId: string) {
  const supabase = await createClient();

  const { data: comments } = await supabase
    .from("quote_comments")
    .select("*")
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: true });

  if (!comments?.length) return [];

  // Batch-resolve user profiles + role slugs
  const userIds = [...new Set(comments.map((c) => c.user_id))];

  const [profilesRes, membersRes] = await Promise.all([
    supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", userIds),
    supabase
      .from("organization_members")
      .select("user_id, roles!inner(slug)")
      .in("user_id", userIds),
  ]);

  const profileMap = new Map(
    (profilesRes.data ?? []).map((p) => [p.user_id, p])
  );
  const roleMap = new Map(
    (membersRes.data ?? []).map((m) => [
      m.user_id,
      (m.roles as unknown as { slug: string })?.slug ?? "unknown",
    ])
  );

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
    };
  });
}

export async function fetchFilterOptions(
  orgId: string,
  user?: { id: string; roles: string[] }
): Promise<{
  customers: { id: string; name: string }[];
  managers: { id: string; full_name: string }[];
}> {
  const supabase = await createClient();

  // First, fetch distinct customer_ids and created_by from quotes the user can see
  let quotesQuery = supabase
    .from("quotes")
    .select("customer_id, created_by")
    .eq("organization_id", orgId)
    .is("deleted_at", null);

  // Apply same sales role scoping as fetchQuotesList
  if (user && isSalesOnly(user.roles)) {
    const { data: assignedCustomers } = await supabase
      .from("customers")
      .select("id")
      .eq("organization_id", orgId)
      .eq("manager_id", user.id);

    const assignedIds = (assignedCustomers ?? []).map((c) => c.id);

    if (assignedIds.length > 0) {
      quotesQuery = quotesQuery.or(
        `created_by.eq.${user.id},customer_id.in.(${assignedIds.join(",")})`
      );
    } else {
      quotesQuery = quotesQuery.eq("created_by", user.id);
    }
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

  return { customers, managers };
}
