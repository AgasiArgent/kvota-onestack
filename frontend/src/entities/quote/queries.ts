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
