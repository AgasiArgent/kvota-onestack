import { createClient } from "@/shared/lib/supabase/server";
import { isSalesOnly, isAssignedItemsOnly, isProcurementSeniorOnly } from "@/shared/lib/roles";
import { getAssignedCustomerIds, getAssignedQuoteIds } from "@/shared/lib/access";
import type { QuoteListItem, QuotesFilterParams, QuotesListResult } from "./types";
import { getStatusesForGroup } from "./types";

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

  // Build base query — select scalar columns only (FK joins resolved separately)
  let query = supabase
    .from("quotes")
    .select(
      "id, idn_quote, created_at, workflow_status, total_amount_quote, total_profit_usd, currency, customer_id, created_by, version_count, current_version",
      { count: "exact" }
    )
    .eq("organization_id", user.orgId)
    .is("deleted_at", null)
    .order("created_at", { ascending: false });

  // Role-based filtering per .kiro/steering/access-control.md:
  if (isAssignedItemsOnly(user.roles)) {
    // ASSIGNED_ITEMS tier: procurement/logistics/customs see only quotes with items assigned to them
    const assignedQuoteIds = await getAssignedQuoteIds(supabase, user);
    if (assignedQuoteIds.length > 0) {
      query = query.in("id", assignedQuoteIds);
    } else {
      // No assignments → empty result (use impossible filter)
      query = query.eq("id", "00000000-0000-0000-0000-000000000000");
    }
  } else if (isSalesOnly(user.roles)) {
    // OWN/GROUP tier: sales/head_of_sales see own quotes + quotes for assigned customers
    const assignedCustomerIds = await getAssignedCustomerIds(supabase, user);
    if (assignedCustomerIds.length > 0) {
      query = query.or(
        `created_by.eq.${user.id},customer_id.in.(${assignedCustomerIds.join(",")})`
      );
    } else {
      query = query.eq("created_by", user.id);
    }
  } else if (isProcurementSeniorOnly(user.roles)) {
    // PROCUREMENT_STAGE_ONLY tier: procurement_senior sees only procurement-stage quotes
    query = query.eq("workflow_status", "pending_procurement");
  }
  // All other roles (admin, top_manager, controllers, finance, head_of_procurement, head_of_logistics)
  // → no additional filter, they see all org quotes

  // Apply optional filters
  if (params.status) {
    const statuses = getStatusesForGroup(params.status);
    if (statuses.length > 0) {
      query = query.in("workflow_status", statuses);
    } else {
      // Treat as individual status value
      query = query.eq("workflow_status", params.status);
    }
  } else {
    // Default view: hide cancelled quotes (user must explicitly filter to see them)
    query = query.neq("workflow_status", "cancelled");
  }

  if (params.customer) {
    query = query.eq("customer_id", params.customer);
  }

  if (params.manager) {
    query = query.eq("created_by", params.manager);
  }

  if (params.search) {
    query = query.ilike("idn_quote", `%${params.search}%`);
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
  } catch {
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
    .maybeSingle();

  if (!spec) return null;

  // Find deal linked to this specification
  const { data: deal } = await supabase
    .from("deals")
    .select("id")
    .eq("specification_id", spec.id)
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
      .maybeSingle();
    return data?.workflow_status === "pending_procurement";
  }

  return true;
}

export async function fetchFilterOptions(
  orgId: string,
  user?: QuoteAccessUser
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

  // Apply same role scoping as fetchQuotesList
  if (user && isAssignedItemsOnly(user.roles)) {
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

  return { customers, managers };
}
