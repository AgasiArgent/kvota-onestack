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
  status?: "active" | "inactive" | "";
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
  const customerIds = rows.map((c: any) => c.id);
  const managerIds = rows.map((c: any) => c.manager_id).filter(Boolean);

  // Fetch manager names and quote counts in parallel
  const [quoteCounts, managers] = await Promise.all([
    supabase.rpc("get_customers_quote_counts", { customer_ids: customerIds }).then((r) => r.data),
    managerIds.length > 0
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", managerIds)
          .then((r) => r.data)
      : Promise.resolve([]),
  ]);

  const countsMap = new Map<string, { count: number; lastDate: string | null }>(
    (quoteCounts ?? []).map(
      (r: { customer_id: string; cnt: number; last_date: string | null }) => [
        r.customer_id,
        { count: r.cnt, lastDate: r.last_date },
      ]
    )
  );

  const managerMap = new Map<string, string>(
    (managers ?? []).map((m: any) => [m.user_id, m.full_name])
  );

  const items: CustomerListItem[] = rows.map((row: any) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
    status: row.status,
    manager: row.manager_id && managerMap.has(row.manager_id)
      ? { full_name: managerMap.get(row.manager_id)! }
      : null,
    quotes_count: countsMap.get(row.id)?.count ?? 0,
    last_quote_date: countsMap.get(row.id)?.lastDate ?? null,
  }));

  return { data: items, total: count ?? 0 };
}

export async function fetchCustomerDetail(id: string): Promise<Customer | null> {
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
    if (profile) manager = { full_name: profile.full_name };
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
  const inReview = quotesList.filter(
    (q: any) => q.status === "in_review"
  ).length;
  const inProgress = quotesList.filter((q: any) =>
    ["draft", "calculating", "calculated"].includes(q.status)
  ).length;

  const { data: specs } = await supabase
    .from("specifications")
    .select("id, status")
    .eq("customer_id", customerId);

  const specsList = specs ?? [];
  const active = specsList.filter(
    (s: any) => s.status !== "signed" && s.status !== "cancelled"
  ).length;
  const signed = specsList.filter((s: any) => s.status === "signed").length;

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
    .select("id, idn_quote, total_amount, profit_quote_currency, created_at, status")
    .eq("customer_id", customerId)
    .order("created_at", { ascending: false });

  return (data ?? []).map((row: any) => ({
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
    .select("id, specification_number, status, created_at, quotes!inner(customer_id)")
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false });

  return (data ?? []).map((row: any) => ({
    id: row.id,
    idn: row.specification_number,
    total_amount: null,
    profit_amount: null,
    created_at: row.created_at,
    status: row.status,
  }));
}

export async function fetchCustomerPositions(customerId: string) {
  const supabase = await createClient();
  const { data } = await supabase
    .from("quote_items")
    .select(
      "id, product_name, brand, sku, quantity, quotes!inner(idn_quote, customer_id)"
    )
    .eq("quotes.customer_id", customerId)
    .order("created_at", { ascending: false })
    .limit(100);

  return (data ?? []).map((row: any) => ({
    id: row.id,
    product_name: row.product_name,
    brand: row.brand,
    sku: row.sku,
    quantity: row.quantity,
    quote_idn: row.quotes?.idn_quote ?? "—",
  }));
}
