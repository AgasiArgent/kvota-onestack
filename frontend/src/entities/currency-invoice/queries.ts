import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  CurrencyInvoice,
  CurrencyInvoiceDetail,
  CurrencyInvoiceItem,
  CIFilterParams,
  CIListResult,
  CompanyOption,
} from "./types";

const DEFAULT_PAGE_SIZE = 20;

export async function fetchCurrencyInvoices(
  orgId: string,
  filters: CIFilterParams
): Promise<CIListResult> {
  const admin = createAdminClient();
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // Step 1: Fetch currency invoices (scalar columns only)
  let query = admin
    .from("currency_invoices")
    .select(
      "id, invoice_number, segment, status, total_amount, currency, markup_percent, created_at, deal_id, seller_entity_type, seller_entity_id, buyer_entity_type, buyer_entity_id",
      { count: "exact" }
    )
    .eq("organization_id", orgId)
    .order("created_at", { ascending: false });

  if (filters.status) {
    query = query.eq("status", filters.status);
  }
  if (filters.segment) {
    query = query.eq("segment", filters.segment);
  }

  query = query.range(offset, offset + pageSize - 1);

  const { data: rows, count, error } = await query;
  if (error) throw error;

  const ciRows = rows ?? [];
  if (ciRows.length === 0) {
    return { data: [], total: count ?? 0, page, pageSize };
  }

  // Step 2: Batch-resolve deal info (deal_number, quote_id)
  const dealIds = Array.from(
    new Set(ciRows.map((r) => r.deal_id).filter(Boolean))
  );

  const { data: deals } = await admin
    .from("deals")
    .select("id, deal_number, quote_id")
    .in("id", dealIds);

  const dealMap = new Map(
    (deals ?? []).map((d) => [d.id, { deal_number: d.deal_number, quote_id: d.quote_id }])
  );

  // Step 3: Batch-resolve quote info (idn_quote, customer_id)
  const quoteIds = Array.from(
    new Set(
      (deals ?? [])
        .map((d) => d.quote_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: quotes } = quoteIds.length > 0
    ? await admin
        .from("quotes")
        .select("id, idn_quote, customer_id")
        .in("id", quoteIds)
    : { data: [] as { id: string; idn_quote: string; customer_id: string | null }[] };

  const quoteMap = new Map(
    (quotes ?? []).map((q) => [q.id, { idn_quote: q.idn_quote, customer_id: q.customer_id }])
  );

  // Step 4: Batch-resolve customer names
  const customerIds = Array.from(
    new Set(
      (quotes ?? [])
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: customers } = customerIds.length > 0
    ? await admin
        .from("customers")
        .select("id, name")
        .in("id", customerIds)
    : { data: [] as { id: string; name: string }[] };

  const customerMap = new Map(
    (customers ?? []).map((c) => [c.id, c.name])
  );

  // Step 5: Batch-resolve seller/buyer company names
  const sellerIds = Array.from(
    new Set(
      ciRows
        .filter((r) => r.seller_entity_type === "seller_company" && r.seller_entity_id)
        .map((r) => r.seller_entity_id!)
    )
  );
  const buyerIds = Array.from(
    new Set(
      ciRows
        .filter((r) => r.buyer_entity_type === "buyer_company" && r.buyer_entity_id)
        .map((r) => r.buyer_entity_id!)
    )
  );

  const [sellersResult, buyersResult] = await Promise.all([
    sellerIds.length > 0
      ? admin.from("seller_companies").select("id, name").in("id", sellerIds)
      : Promise.resolve({ data: [] as { id: string; name: string }[] }),
    buyerIds.length > 0
      ? admin.from("buyer_companies").select("id, name").in("id", buyerIds)
      : Promise.resolve({ data: [] as { id: string; name: string }[] }),
  ]);

  const sellerMap = new Map(
    (sellersResult.data ?? []).map((s) => [s.id, s.name])
  );
  const buyerMap = new Map(
    (buyersResult.data ?? []).map((b) => [b.id, b.name])
  );

  // Step 6: Assemble results
  const items: CurrencyInvoice[] = ciRows.map((row) => {
    const deal = dealMap.get(row.deal_id);
    const quote = deal?.quote_id ? quoteMap.get(deal.quote_id) : undefined;
    const customerName = quote?.customer_id
      ? customerMap.get(quote.customer_id) ?? null
      : null;

    return {
      id: row.id,
      invoice_number: row.invoice_number,
      segment: row.segment as "EURTR" | "TRRU",
      status: row.status as "draft" | "verified" | "exported",
      total_amount: row.total_amount,
      currency: row.currency,
      seller_name: row.seller_entity_id
        ? sellerMap.get(row.seller_entity_id) ?? null
        : null,
      buyer_name: row.buyer_entity_id
        ? buyerMap.get(row.buyer_entity_id) ?? null
        : null,
      markup_percent: row.markup_percent,
      created_at: row.created_at ?? "",
      deal_id: row.deal_id,
      deal_number: deal?.deal_number ?? null,
      quote_idn: quote?.idn_quote ?? null,
      customer_name: customerName,
    };
  });

  return { data: items, total: count ?? 0, page, pageSize };
}

export async function fetchCurrencyInvoiceDetail(
  id: string,
  orgId: string
): Promise<CurrencyInvoiceDetail | null> {
  const admin = createAdminClient();

  // Fetch the invoice
  const { data: row, error } = await admin
    .from("currency_invoices")
    .select(
      "id, invoice_number, segment, status, total_amount, currency, markup_percent, created_at, deal_id, seller_entity_type, seller_entity_id, buyer_entity_type, buyer_entity_id"
    )
    .eq("id", id)
    .eq("organization_id", orgId)
    .single();

  if (error || !row) return null;

  // Fetch items
  const { data: itemRows } = await admin
    .from("currency_invoice_items")
    .select(
      "id, product_name, sku, idn_sku, manufacturer, unit, hs_code, quantity, base_price, price, total, sort_order"
    )
    .eq("currency_invoice_id", id)
    .order("sort_order", { ascending: true });

  // Resolve deal info
  const { data: deal } = await admin
    .from("deals")
    .select("id, deal_number, quote_id")
    .eq("id", row.deal_id)
    .single();

  let quoteIdn: string | null = null;
  let customerName: string | null = null;
  let dealNumber: string | null = deal?.deal_number ?? null;

  if (deal?.quote_id) {
    const { data: quote } = await admin
      .from("quotes")
      .select("idn_quote, customer_id")
      .eq("id", deal.quote_id)
      .single();

    quoteIdn = quote?.idn_quote ?? null;

    if (quote?.customer_id) {
      const { data: customer } = await admin
        .from("customers")
        .select("name")
        .eq("id", quote.customer_id)
        .single();

      customerName = customer?.name ?? null;
    }
  }

  // Resolve seller/buyer names
  let sellerName: string | null = null;
  let buyerName: string | null = null;

  if (row.seller_entity_type === "seller_company" && row.seller_entity_id) {
    const { data: seller } = await admin
      .from("seller_companies")
      .select("name")
      .eq("id", row.seller_entity_id)
      .single();
    sellerName = seller?.name ?? null;
  }

  if (row.buyer_entity_type === "buyer_company" && row.buyer_entity_id) {
    const { data: buyer } = await admin
      .from("buyer_companies")
      .select("name")
      .eq("id", row.buyer_entity_id)
      .single();
    buyerName = buyer?.name ?? null;
  }

  const items: CurrencyInvoiceItem[] = (itemRows ?? []).map((item) => ({
    id: item.id,
    product_name: item.product_name,
    sku: item.sku,
    idn_sku: item.idn_sku,
    manufacturer: item.manufacturer,
    unit: item.unit,
    hs_code: item.hs_code,
    quantity: item.quantity,
    base_price: item.base_price,
    price: item.price,
    total: item.total,
    sort_order: item.sort_order ?? 0,
  }));

  return {
    id: row.id,
    invoice_number: row.invoice_number,
    segment: row.segment as "EURTR" | "TRRU",
    status: row.status as "draft" | "verified" | "exported",
    total_amount: row.total_amount,
    currency: row.currency,
    seller_name: sellerName,
    buyer_name: buyerName,
    markup_percent: row.markup_percent,
    created_at: row.created_at ?? "",
    deal_id: row.deal_id,
    deal_number: dealNumber,
    quote_idn: quoteIdn,
    customer_name: customerName,
    items,
    seller_entity_type: row.seller_entity_type,
    seller_entity_id: row.seller_entity_id,
    buyer_entity_type: row.buyer_entity_type,
    buyer_entity_id: row.buyer_entity_id,
  };
}

export async function fetchCompanyOptions(
  orgId: string
): Promise<{ sellers: CompanyOption[]; buyers: CompanyOption[] }> {
  const admin = createAdminClient();

  const [sellersResult, buyersResult] = await Promise.all([
    admin
      .from("seller_companies")
      .select("id, name")
      .eq("organization_id", orgId)
      .eq("is_active", true)
      .order("name"),
    admin
      .from("buyer_companies")
      .select("id, name")
      .eq("organization_id", orgId)
      .eq("is_active", true)
      .order("name"),
  ]);

  return {
    sellers: (sellersResult.data ?? []).map((s) => ({ id: s.id, name: s.name })),
    buyers: (buyersResult.data ?? []).map((b) => ({ id: b.id, name: b.name })),
  };
}
