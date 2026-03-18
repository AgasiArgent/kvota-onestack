import { createClient } from "@/shared/lib/supabase/server";
import type {
  PhmbQuoteListItem,
  PhmbQuoteStatus,
  PhmbQuoteDetail,
  PhmbQuoteItem,
  PhmbItemStatus,
  PhmbDefaults,
  SellerCompany,
  PhmbVersion,
  ProcurementQueueItem,
  ProcurementQueueStatus,
  BrandGroup,
} from "./types";

const PAGE_SIZE = 20;

export async function fetchPhmbQuotesList(params: {
  orgId: string;
  search?: string;
  status?: PhmbQuoteStatus;
  page?: number;
}): Promise<{ data: PhmbQuoteListItem[]; total: number }> {
  const supabase = await createClient();
  const { orgId, search = "", status, page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  // Fetch PHMB quotes with customer name join
  let query = supabase
    .from("quotes")
    .select(
      "id, idn_quote, customer_id, total_amount_usd, created_at, customers!customer_id(name)",
      { count: "exact" }
    )
    .eq("organization_id", orgId)
    .eq("is_phmb", true)
    .is("deleted_at", null)
    .order("created_at", { ascending: false })
    .range(from, to);

  if (search) {
    query = query.or(
      `idn_quote.ilike.%${search}%,customers.name.ilike.%${search}%`
    );
  }

  const { data: quotes, count, error } = await query;
  if (error) throw error;

  const rows = quotes ?? [];
  if (rows.length === 0) {
    return { data: [], total: count ?? 0 };
  }

  // Batch-fetch item counts for all quotes
  const quoteIds = rows.map((q) => q.id);

  const { data: allItems, error: itemsError } = await supabase
    .from("phmb_quote_items")
    .select("quote_id, total_price_usd")
    .in("quote_id", quoteIds);

  if (itemsError) throw itemsError;

  // Build count maps
  const totalMap = new Map<string, number>();
  const pricedMap = new Map<string, number>();

  for (const item of allItems ?? []) {
    totalMap.set(item.quote_id, (totalMap.get(item.quote_id) ?? 0) + 1);
    if (item.total_price_usd !== null) {
      pricedMap.set(item.quote_id, (pricedMap.get(item.quote_id) ?? 0) + 1);
    }
  }

  function computeStatus(total: number, priced: number): PhmbQuoteStatus {
    if (total === 0) return "draft";
    if (priced < total) return "waiting_prices";
    return "ready";
  }

  const items: PhmbQuoteListItem[] = rows.map((row) => {
    const itemsTotal = totalMap.get(row.id) ?? 0;
    const itemsPriced = pricedMap.get(row.id) ?? 0;
    const customerData = row.customers as unknown as { name: string } | null;

    return {
      id: row.id,
      idn_quote: row.idn_quote,
      customer_name: customerData?.name ?? "—",
      items_total: itemsTotal,
      items_priced: itemsPriced,
      total_amount_usd: row.total_amount_usd,
      status: computeStatus(itemsTotal, itemsPriced),
      created_at: row.created_at ?? "",
    };
  });

  // Apply client-side status filter (status is computed, not a DB column)
  const filtered = status
    ? items.filter((item) => item.status === status)
    : items;

  return {
    data: filtered,
    total: status ? filtered.length : (count ?? 0),
  };
}

export async function fetchPhmbDefaults(
  orgId: string
): Promise<PhmbDefaults> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("phmb_settings")
    .select("default_advance_pct, default_payment_days, default_markup_pct")
    .eq("org_id", orgId)
    .maybeSingle();

  if (error) throw error;

  return {
    default_advance_pct: data?.default_advance_pct ?? 0,
    default_payment_days: data?.default_payment_days ?? 30,
    default_markup_pct: data?.default_markup_pct ?? 10,
  };
}

export async function fetchSellerCompanies(
  orgId: string
): Promise<SellerCompany[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("seller_companies")
    .select("id, name")
    .eq("organization_id", orgId)
    .order("name");

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
  }));
}

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function resolvePhmbQuoteId(
  idOrIdn: string
): Promise<string | null> {
  if (UUID_RE.test(idOrIdn)) return idOrIdn;

  const supabase = await createClient();
  const { data } = await supabase
    .from("quotes")
    .select("id")
    .eq("idn_quote", idOrIdn)
    .is("deleted_at", null)
    .single();

  return data?.id ?? null;
}

export async function fetchPhmbQuoteDetail(
  quoteId: string
): Promise<PhmbQuoteDetail | null> {
  const supabase = await createClient();

  const resolvedId = await resolvePhmbQuoteId(quoteId);
  if (!resolvedId) return null;

  const { data, error } = await supabase
    .from("quotes")
    .select(
      "id, idn_quote, currency, phmb_advance_pct, phmb_payment_days, phmb_markup_pct, total_amount_usd, created_at, is_phmb, customers!customer_id(name)"
    )
    .eq("id", resolvedId)
    .is("deleted_at", null)
    .single();

  if (error) return null;
  if (!data || !data.is_phmb) return null;

  const customerData = data.customers as unknown as { name: string } | null;

  return {
    id: data.id,
    idn_quote: data.idn_quote,
    customer_name: customerData?.name ?? "—",
    currency: data.currency,
    phmb_advance_pct: data.phmb_advance_pct ?? 0,
    phmb_payment_days: data.phmb_payment_days ?? 0,
    phmb_markup_pct: data.phmb_markup_pct ?? 0,
    total_amount_usd: data.total_amount_usd,
    created_at: data.created_at ?? "",
  };
}

function computeItemStatus(item: {
  list_price_rmb: number | null;
  total_price_usd: number | null;
}): PhmbItemStatus {
  // An item is "priced" if it has a list price (from price list or procurement)
  if (item.list_price_rmb !== null && item.list_price_rmb > 0) return "priced";
  return "waiting";
}

export async function fetchPhmbQuoteItems(
  quoteId: string
): Promise<PhmbQuoteItem[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("phmb_quote_items")
    .select(
      "id, quote_id, cat_number, product_name, brand, product_classification, quantity, list_price_rmb, discount_pct, hs_code, duty_pct, delivery_days, exw_price_usd, cogs_usd, financial_cost_usd, total_price_usd, total_price_with_vat_usd"
    )
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    quote_id: row.quote_id,
    cat_number: row.cat_number,
    product_name: row.product_name,
    brand: row.brand,
    product_classification: row.product_classification,
    quantity: row.quantity,
    list_price_rmb: row.list_price_rmb,
    discount_pct: row.discount_pct,
    hs_code: row.hs_code,
    duty_pct: row.duty_pct,
    delivery_days: row.delivery_days,
    exw_price_usd: row.exw_price_usd,
    cogs_usd: row.cogs_usd,
    financial_cost_usd: row.financial_cost_usd,
    total_price_usd: row.total_price_usd,
    total_price_with_vat_usd: row.total_price_with_vat_usd,
    status: computeItemStatus(row),
  }));
}

// --- Version queries ---

export async function fetchPhmbVersions(
  quoteId: string
): Promise<PhmbVersion[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("phmb_versions")
    .select(
      "id, quote_id, version_number, label, phmb_advance_pct, phmb_payment_days, phmb_markup_pct, total_amount_usd, created_at, updated_at"
    )
    .eq("quote_id", quoteId)
    .order("version_number", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    quote_id: row.quote_id,
    version_number: row.version_number,
    label: row.label,
    phmb_advance_pct: row.phmb_advance_pct,
    phmb_payment_days: row.phmb_payment_days,
    phmb_markup_pct: row.phmb_markup_pct,
    total_amount_usd: row.total_amount_usd,
    created_at: row.created_at ?? "",
    updated_at: row.updated_at ?? "",
  }));
}

// --- Procurement Queue queries (Screen 3) ---

export async function fetchProcurementQueue(params: {
  orgId: string;
  brandGroupId?: string;
  status?: ProcurementQueueStatus;
}): Promise<ProcurementQueueItem[]> {
  const supabase = await createClient();
  const { orgId, brandGroupId, status } = params;

  let query = supabase
    .from("phmb_procurement_queue")
    .select(
      "id, quote_item_id, quote_id, brand, brand_group_id, status, priced_rmb, notes, created_at, phmb_quote_items!quote_item_id(cat_number, product_name, quantity, delivery_days), quotes!quote_id(idn_quote, customers!customer_id(name))"
    )
    .eq("org_id", orgId)
    .order("created_at", { ascending: true });

  if (brandGroupId) {
    query = query.eq("brand_group_id", brandGroupId);
  }
  if (status) {
    query = query.eq("status", status);
  }

  const { data, error } = await query;
  if (error) throw error;

  return (data ?? []).map((row) => {
    const quoteItem = row.phmb_quote_items as unknown as {
      cat_number: string;
      product_name: string;
      quantity: number;
      delivery_days: number | null;
    } | null;

    const quoteData = row.quotes as unknown as {
      idn_quote: string;
      customers: { name: string } | null;
    } | null;

    return {
      id: row.id,
      quote_item_id: row.quote_item_id,
      quote_id: row.quote_id,
      brand: row.brand,
      brand_group_id: row.brand_group_id,
      status: row.status as ProcurementQueueStatus,
      priced_rmb: row.priced_rmb,
      notes: row.notes,
      created_at: row.created_at ?? "",
      cat_number: quoteItem?.cat_number ?? "",
      product_name: quoteItem?.product_name ?? "",
      quantity: quoteItem?.quantity ?? 0,
      delivery_days: quoteItem?.delivery_days ?? null,
      quote_idn: quoteData?.idn_quote ?? "—",
      customer_name: (quoteData?.customers as { name: string } | null)?.name ?? "—",
    };
  });
}

export async function fetchBrandGroups(orgId: string): Promise<BrandGroup[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("phmb_brand_groups")
    .select("id, name")
    .eq("org_id", orgId)
    .order("sort_order", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
  }));
}
