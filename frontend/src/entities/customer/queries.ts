import { createClient } from "@/shared/lib/supabase/server";
import type {
  CustomerListItem,
  Customer,
  CustomerContact,
  CustomerStats,
} from "./types";

const PAGE_SIZE = 50;

export async function fetchCustomersList(params: {
  search?: string;
  status?: string;
  page?: number;
}): Promise<{ data: CustomerListItem[]; total: number }> {
  const supabase = await createClient();
  const { search = "", status = "", page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("customers")
    .select("id, name, inn, status, manager_id", { count: "exact" })
    .order("created_at", { ascending: false })
    .range(from, to);

  if (search) {
    query = query.or(`name.ilike.%${search}%,inn.ilike.%${search}%`);
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
    supabase
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
    manager:
      row.manager_id && managerMap.has(row.manager_id)
        ? { full_name: managerMap.get(row.manager_id)! }
        : null,
    quotes_count: countsMap.get(row.id)?.count ?? 0,
    last_quote_date: countsMap.get(row.id)?.lastDate ?? null,
  }));

  return { data: items, total: count ?? 0 };
}

export async function fetchCustomerDetail(
  id: string
): Promise<Customer | null> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("customers")
    .select("*")
    .eq("id", id)
    .single();
  if (error) return null;

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
  return (data ?? []) as CustomerContact[];
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
      "id, call_type, call_category, scheduled_date, comment, customer_needs, meeting_notes, created_at, customer_contacts!calls_contact_person_id_fkey(name), user_profiles!calls_user_id_fkey(full_name)"
    )
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(50);

  return (data ?? []).map((row) => ({
    id: row.id,
    call_type: row.call_type as "call" | "scheduled",
    call_category: row.call_category,
    scheduled_date: row.scheduled_date,
    comment: row.comment,
    customer_needs: row.customer_needs,
    meeting_notes: row.meeting_notes,
    contact_name:
      (row.customer_contacts as unknown as { name: string } | null)?.name ?? null,
    user_name:
      (row.user_profiles as unknown as { full_name: string } | null)?.full_name ?? null,
    created_at: row.created_at,
  }));
}

export async function fetchCustomerPositions(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quote_items")
    .select(
      "id, product_name, brand, idn_sku, quantity, purchase_price_original, purchase_currency, procurement_completed_at, quotes!inner(idn_quote, customer_id)"
    )
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(100);

  return (data ?? []).map((row) => ({
    id: row.id,
    product_name: row.product_name,
    brand: row.brand,
    sku: row.idn_sku,
    quantity: row.quantity,
    purchase_price: row.purchase_price_original,
    purchase_currency: row.purchase_currency,
    procurement_date: row.procurement_completed_at,
    quote_idn:
      (row.quotes as unknown as { idn_quote: string })?.idn_quote ?? "—",
  }));
}
