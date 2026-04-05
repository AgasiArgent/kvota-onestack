import { createClient } from "@/shared/lib/supabase/server";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";
import { isSalesOnly } from "@/shared/lib/roles";
import { getAssignedCustomerIds } from "@/shared/lib/access";
import type {
  CustomerListItem,
  CustomerFinancials,
  Customer,
  CustomerContact,
  CustomerContract,
  CustomerStats,
  PhoneEntry,
} from "./types";

const PAGE_SIZE = 50;

// Sentinel UUID used to force a query to return zero rows when a sales-only
// user has no customer assignments. Postgres .in() with an empty array is
// a no-op (no filter applied), which would leak rows; using a dummy ID
// guarantees empty results.
const EMPTY_RESULT_UUID = "00000000-0000-0000-0000-000000000000";

export async function fetchCustomersList(
  params: {
    search?: string;
    status?: string;
    page?: number;
  },
  user?: { id: string; roles: string[]; salesGroupId?: string | null; orgId?: string }
): Promise<{ data: CustomerListItem[]; total: number }> {
  const supabase = await createClient();
  const { search = "", status = "", page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("customers")
    .select("id, name, inn, status, manager_id, created_at", { count: "exact" })
    .order("created_at", { ascending: false })
    .range(from, to);

  // Role-based filtering via customer_assignees junction table.
  // Per .kiro/steering/access-control.md:
  // - sales (regular): customers they are assigned to
  // - head_of_sales: customers any group member is assigned to
  // Other roles see all customers in their org (filtered by RLS/org scope above).
  if (user && isSalesOnly(user.roles) && user.orgId) {
    const assignedIds = await getAssignedCustomerIds(supabase, {
      id: user.id,
      roles: user.roles,
      salesGroupId: user.salesGroupId,
      orgId: user.orgId,
    });
    query = query.in("id", assignedIds.length > 0 ? assignedIds : [EMPTY_RESULT_UUID]);
  }

  if (search) {
    const escaped = escapePostgrestFilter(search);
    query = query.or(`name.ilike.%${escaped}%,inn.ilike.%${escaped}%`);
  }
  if (status === "active") query = query.eq("status", "active");
  if (status === "inactive") query = query.neq("status", "active");

  const { data, count, error } = await query;
  if (error) throw error;

  const rows = data ?? [];
  const customerIds = rows.map((c) => c.id);
  const managerIds = rows
    .map((c) => c.manager_id)
    .filter((id): id is string => id !== null);

  // Fetch manager names and quote counts in parallel
  const [quoteCounts, managers] = await Promise.all([
    (supabase as unknown as { rpc: (fn: string, params: Record<string, unknown>) => Promise<{ data: { customer_id: string; cnt: number; last_date: string | null }[] | null }> })
      .rpc("get_customers_quote_counts", { customer_ids: customerIds })
      .then((r) => r.data),
    managerIds.length > 0
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", managerIds)
          .then((r) => r.data)
      : Promise.resolve([] as { user_id: string; full_name: string | null }[]),
  ]);

  const countsMap = new Map(
    (quoteCounts ?? []).map((r) => [
      r.customer_id,
      { count: r.cnt, lastDate: r.last_date },
    ])
  );

  const managerMap = new Map(
    (managers ?? []).map((m) => [m.user_id, m.full_name ?? ""])
  );

  const items: CustomerListItem[] = rows.map((row) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
    status: row.status ?? "active",
    created_at: row.created_at ?? "",
    manager:
      row.manager_id && managerMap.has(row.manager_id)
        ? { full_name: managerMap.get(row.manager_id)! }
        : null,
    quotes_count: countsMap.get(row.id)?.count ?? 0,
    last_quote_date: countsMap.get(row.id)?.lastDate ?? null,
  }));

  return { data: items, total: count ?? 0 };
}

/**
 * Checks if a sales-only user is allowed to view a specific customer.
 * Non-sales roles always return true (visibility handled elsewhere).
 * Sales users must have the customer in their assigned set (directly or,
 * for head_of_sales, via any group member).
 */
export async function canAccessCustomer(
  customerId: string,
  user: { id: string; roles: string[]; orgId: string; salesGroupId?: string | null }
): Promise<boolean> {
  if (!isSalesOnly(user.roles)) return true;

  const supabase = await createClient();
  const assignedIds = await getAssignedCustomerIds(supabase, {
    id: user.id,
    roles: user.roles,
    salesGroupId: user.salesGroupId,
    orgId: user.orgId,
  });
  return assignedIds.includes(customerId);
}

export async function fetchCustomerDetail(
  id: string,
  orgId: string
): Promise<Customer | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customers")
    .select("*")
    .eq("id", id)
    .eq("organization_id", orgId)
    .single();
  if (error) {
    // "no rows found" → not found; anything else → rethrow
    if (error.code === "PGRST116") return null;
    throw error;
  }

  // Resolve manager name separately (no FK relationship)
  let manager: { full_name: string } | null = null;
  if (data.manager_id) {
    const { data: profile } = await supabase
      .from("user_profiles")
      .select("full_name")
      .eq("user_id", data.manager_id)
      .single();
    if (profile?.full_name) manager = { full_name: profile.full_name };
  }

  return { ...data, manager } as Customer;
}

export async function fetchCustomerStats(
  customerId: string
): Promise<CustomerStats> {
  const supabase = await createClient();

  const { data: quotes } = await supabase
    .from("quotes")
    .select("id, status")
    .eq("customer_id", customerId);

  const quotesList = quotes ?? [];
  const inReview = quotesList.filter((q) => q.status === "in_review").length;
  const inProgress = quotesList.filter((q) =>
    ["draft", "calculating", "calculated"].includes(q.status ?? "")
  ).length;

  // Specs have no customer_id — join through quote_id
  const { data: specs } = await supabase
    .from("specifications")
    .select("id, status, quotes!inner(customer_id)")
    .eq("quotes.customer_id", customerId);

  const specsList = specs ?? [];
  const active = specsList.filter(
    (s) => s.status !== "signed" && s.status !== "cancelled"
  ).length;
  const signed = specsList.filter((s) => s.status === "signed").length;

  return {
    quotes_in_review: inReview,
    quotes_in_progress: inProgress,
    quotes_total: quotesList.length,
    specs_active: active,
    specs_signed: signed,
    specs_total: specsList.length,
    total_debt: 0,
    overdue_count: 0,
    last_payment_date: null,
  };
}

export async function fetchCustomerContacts(
  customerId: string
): Promise<CustomerContact[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customer_contacts")
    .select("*")
    .eq("customer_id", customerId)
    .order("is_primary", { ascending: false })
    .order("name");
  if (error) throw error;
  return (data ?? []).map((row) => {
    const rawPhones = Array.isArray(row.phones) ? row.phones : [];
    type RawPhone = { number?: unknown; ext?: unknown; label?: unknown };
    const phones: PhoneEntry[] = rawPhones.map((p) => {
      const phone = p as RawPhone;
      return {
        number: String(phone.number ?? ""),
        ext: phone.ext != null ? String(phone.ext) : null,
        label: String(phone.label ?? ""),
      };
    });
    return {
      ...row,
      is_signatory: row.is_signatory ?? false,
      is_primary: row.is_primary ?? false,
      is_lpr: row.is_lpr ?? false,
      phones,
      created_at: row.created_at ?? "",
      updated_at: row.updated_at ?? "",
    };
  }) as CustomerContact[];
}

export async function fetchCustomerAddresses(
  customerId: string
): Promise<Array<{ id: string; name: string | null; address: string; is_default: boolean }>> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customer_delivery_addresses")
    .select("id, name, address, is_default")
    .eq("customer_id", customerId)
    .order("is_default", { ascending: false })
    .order("name");
  if (error) throw error;
  return (data ?? []) as Array<{ id: string; name: string | null; address: string; is_default: boolean }>;
}

export async function fetchCustomerQuotes(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quotes")
    .select(
      "id, idn_quote, total_amount, profit_quote_currency, created_at, status"
    )
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false });

  return (data ?? []).map((row) => ({
    id: row.id,
    idn: row.idn_quote,
    total_amount: row.total_amount,
    profit_amount: row.profit_quote_currency,
    created_at: row.created_at,
    status: row.status,
  }));
}

export async function fetchCustomerSpecs(customerId: string) {
  const supabase = await createClient();
  // Specs have no customer_id — join through quote_id
  const { data } = await supabase
    .from("specifications")
    .select(
      "id, specification_number, status, created_at, quotes!inner(customer_id)"
    )
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false });

  return (data ?? []).map((row) => ({
    id: row.id,
    idn: row.specification_number,
    total_amount: null,
    profit_amount: null,
    created_at: row.created_at,
    status: row.status,
  }));
}

export async function fetchCustomerCalls(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("calls")
    .select(
      "id, call_type, call_category, scheduled_date, comment, customer_needs, meeting_notes, user_id, assigned_to, created_at, customer_contacts!calls_contact_person_id_fkey(name, phone, email)"
    )
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(50);

  const rows = data ?? [];

  // Collect all user IDs (creators + assigned) for batch resolution
  const allUserIds = [
    ...new Set(
      rows
        .flatMap((r) => [r.user_id, r.assigned_to])
        .filter((id): id is string => id !== null && id !== undefined)
    ),
  ];

  let userMap: Record<string, string> = {};
  if (allUserIds.length > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", allUserIds);
    userMap = Object.fromEntries(
      (profiles ?? []).map((p) => [p.user_id, p.full_name ?? ""])
    );
  }

  return rows.map((row) => {
    const contact = row.customer_contacts as unknown as {
      name: string;
      phone: string | null;
      email: string | null;
    } | null;

    return {
      id: row.id,
      call_type: row.call_type as "call" | "scheduled",
      call_category: row.call_category,
      scheduled_date: row.scheduled_date,
      comment: row.comment,
      customer_needs: row.customer_needs,
      meeting_notes: row.meeting_notes,
      contact_name: contact?.name ?? null,
      contact_phone: contact?.phone ?? null,
      contact_email: contact?.email ?? null,
      user_name: row.user_id ? userMap[row.user_id] ?? null : null,
      assigned_to: row.assigned_to,
      assigned_user_name: row.assigned_to
        ? userMap[row.assigned_to] ?? undefined
        : undefined,
      created_at: row.created_at,
    };
  });
}

export async function fetchCustomerContracts(
  customerId: string
): Promise<CustomerContract[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customer_contracts")
    .select("*")
    .eq("customer_id", customerId)
    .order("contract_date", { ascending: false });
  if (error) throw error;
  return (data ?? []) as CustomerContract[];
}

export async function fetchOrgUsers(
  orgId: string
): Promise<{ id: string; full_name: string }[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .eq("organization_id", orgId)
    .order("full_name");
  if (error) throw error;
  return (data ?? []).map((row) => ({
    id: row.user_id,
    full_name: row.full_name ?? "",
  }));
}

export async function fetchCustomerPositions(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quote_items")
    .select(
      "id, product_name, brand, supplier_sku, idn_sku, quantity, purchase_price_original, purchase_currency, procurement_completed_at, quotes!inner(idn_quote, customer_id)"
    )
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(100);

  return (data ?? []).map((row) => ({
    id: row.id,
    product_name: row.product_name,
    brand: row.brand,
    sku: row.supplier_sku,
    idn_sku: row.idn_sku,
    quantity: row.quantity,
    purchase_price: row.purchase_price_original,
    purchase_currency: row.purchase_currency,
    procurement_date: row.procurement_completed_at,
    quote_idn:
      (row.quotes as unknown as { idn_quote: string })?.idn_quote ?? "—",
  }));
}

export async function fetchCustomerFinancials(
  orgId: string
): Promise<Map<string, CustomerFinancials>> {
  const supabase = await createClient();

  const { data, error } = await (supabase.rpc as Function)(
    "get_customer_financials",
    { p_org_id: orgId }
  );

  if (error || !data) return new Map();

  const map = new Map<string, CustomerFinancials>();
  for (const row of data as CustomerFinancials[]) {
    map.set(row.customer_id, row);
  }
  return map;
}
