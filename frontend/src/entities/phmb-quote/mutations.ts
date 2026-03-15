import { createClient } from "@/shared/lib/supabase/client";
import type {
  CreatePhmbQuoteInput,
  CustomerSearchResult,
  PhmbQuoteItem,
  PhmbItemStatus,
  PriceListSearchResult,
  CalcResult,
  ProcurementQueueStatus,
} from "./types";

async function generateIdnQuote(
  supabase: ReturnType<typeof createClient>,
  orgId: string
): Promise<string> {
  const now = new Date();
  const monthPrefix = `Q-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}-`;

  const { data } = await supabase
    .from("quotes")
    .select("idn_quote")
    .eq("organization_id", orgId)
    .like("idn_quote", `${monthPrefix}%`)
    .order("idn_quote", { ascending: false })
    .limit(1);

  let nextNum = 1;
  if (data && data.length > 0 && data[0].idn_quote) {
    const parts = data[0].idn_quote.split("-");
    const lastNum = parseInt(parts[parts.length - 1], 10);
    if (!isNaN(lastNum)) {
      nextNum = lastNum + 1;
    }
  }

  return `${monthPrefix}${String(nextNum).padStart(4, "0")}`;
}

export async function createPhmbQuote(
  orgId: string,
  userId: string,
  input: CreatePhmbQuoteInput
): Promise<{ id: string }> {
  const supabase = createClient();

  const idnQuote = await generateIdnQuote(supabase, orgId);

  const { data, error } = await supabase
    .from("quotes")
    .insert({
      organization_id: orgId,
      idn_quote: idnQuote,
      title: "PHMB КП",
      customer_id: input.customer_id,
      currency: input.currency,
      seller_company_id: input.seller_company_id,
      is_phmb: true,
      phmb_advance_pct: input.phmb_advance_pct,
      phmb_payment_days: input.phmb_payment_days,
      phmb_markup_pct: input.phmb_markup_pct,
      status: "draft",
      created_by: userId,
      created_by_user_id: userId,
    })
    .select("id")
    .single();

  if (error) throw error;

  return { id: data.id };
}

export async function searchCustomers(
  query: string,
  orgId: string
): Promise<CustomerSearchResult[]> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("customers")
    .select("id, name, inn")
    .eq("organization_id", orgId)
    .ilike("name", `%${query}%`)
    .order("name")
    .limit(10);

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
  }));
}

// --- Workspace mutations (Screen 2) ---

function computeItemStatus(item: {
  list_price_rmb: number | null;
}): PhmbItemStatus {
  if (item.list_price_rmb !== null && item.list_price_rmb > 0) return "priced";
  return "waiting";
}

export async function addItemToQuote(
  quoteId: string,
  orgId: string,
  priceListItem: PriceListSearchResult,
  quantity: number = 1
): Promise<PhmbQuoteItem> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("phmb_quote_items")
    .insert({
      quote_id: quoteId,
      phmb_price_list_id: priceListItem.id,
      cat_number: priceListItem.cat_number,
      product_name: priceListItem.product_name,
      brand: priceListItem.brand,
      product_classification: priceListItem.product_classification,
      quantity,
      list_price_rmb: priceListItem.list_price_rmb,
      discount_pct: priceListItem.discount_pct,
    })
    .select(
      "id, quote_id, cat_number, product_name, brand, product_classification, quantity, list_price_rmb, discount_pct, hs_code, duty_pct, delivery_days, exw_price_usd, cogs_usd, financial_cost_usd, total_price_usd, total_price_with_vat_usd"
    )
    .single();

  if (error) throw error;

  // If item has no price, create procurement queue entry
  if (!priceListItem.list_price_rmb || priceListItem.list_price_rmb <= 0) {
    await supabase.from("phmb_procurement_queue").insert({
      org_id: orgId,
      quote_item_id: data.id,
      quote_id: quoteId,
      brand: priceListItem.brand,
      status: "pending",
    });
  }

  return {
    ...data,
    status: computeItemStatus(data),
  };
}

export async function updateItemQuantity(
  itemId: string,
  quantity: number
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_quote_items")
    .update({ quantity })
    .eq("id", itemId);

  if (error) throw error;
}

export async function updateItemPrice(
  itemId: string,
  listPriceRmb: number,
  discountPct: number
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_quote_items")
    .update({ list_price_rmb: listPriceRmb, discount_pct: discountPct })
    .eq("id", itemId);

  if (error) throw error;
}

export async function deleteItem(itemId: string): Promise<void> {
  const supabase = createClient();

  // Also remove from procurement queue if exists
  await supabase
    .from("phmb_procurement_queue")
    .delete()
    .eq("quote_item_id", itemId);

  const { error } = await supabase
    .from("phmb_quote_items")
    .delete()
    .eq("id", itemId);

  if (error) throw error;
}

export async function savePaymentTerms(
  quoteId: string,
  terms: {
    phmb_advance_pct: number;
    phmb_payment_days: number;
    phmb_markup_pct: number;
  }
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("quotes")
    .update({
      phmb_advance_pct: terms.phmb_advance_pct,
      phmb_payment_days: terms.phmb_payment_days,
      phmb_markup_pct: terms.phmb_markup_pct,
    })
    .eq("id", quoteId);

  if (error) throw error;
}

export async function searchPriceList(
  query: string,
  orgId: string
): Promise<PriceListSearchResult[]> {
  const supabase = createClient();

  // Search by catalog number or product name
  const { data: items, error } = await supabase
    .from("phmb_price_list")
    .select(
      "id, cat_number, product_name, brand, product_classification, list_price_rmb"
    )
    .eq("org_id", orgId)
    .or(`cat_number.ilike.%${query}%,product_name.ilike.%${query}%`)
    .order("cat_number")
    .limit(10);

  if (error) throw error;
  if (!items || items.length === 0) return [];

  // Fetch brand discounts for the org to apply
  const brands = [...new Set(items.map((i) => i.brand))];
  const { data: discounts } = await supabase
    .from("phmb_brand_type_discounts")
    .select("brand, product_classification, discount_pct")
    .eq("org_id", orgId)
    .in("brand", brands);

  const discountMap = new Map<string, number>();
  for (const d of discounts ?? []) {
    const key = `${d.brand}::${d.product_classification}`;
    discountMap.set(key, d.discount_pct);
  }

  return items.map((item) => {
    const key = `${item.brand}::${item.product_classification}`;
    const discount = discountMap.get(key) ?? 0;

    return {
      id: item.id,
      cat_number: item.cat_number,
      product_name: item.product_name,
      brand: item.brand,
      product_classification: item.product_classification,
      list_price_rmb: item.list_price_rmb,
      discount_pct: discount,
    };
  });
}

export async function calculateQuote(quoteId: string): Promise<CalcResult> {
  const response = await fetch("/api/phmb/calculate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quote_id: quoteId }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Calculation failed: ${errorText}`);
  }

  return response.json();
}

export async function exportPdf(
  quoteId: string,
  versionId?: string
): Promise<Blob> {
  const body: Record<string, string> = { quote_id: quoteId };
  if (versionId) body.version_id = versionId;

  const response = await fetch("/api/phmb/export-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`PDF export failed: ${errorText}`);
  }

  return response.blob();
}

// --- Procurement Queue mutations (Screen 3) ---

export async function setProcurementPrice(
  queueItemId: string,
  pricedRmb: number
): Promise<void> {
  if (pricedRmb <= 0) {
    throw new Error("Price must be greater than 0");
  }

  const supabase = createClient();

  // 1. Fetch queue row with FK join to get quote item data
  const { data: queueRow, error: fetchError } = await supabase
    .from("phmb_procurement_queue")
    .select("id, quote_item_id, org_id, phmb_quote_items!quote_item_id(cat_number, product_name, brand, product_classification)")
    .eq("id", queueItemId)
    .single();

  if (fetchError || !queueRow) {
    throw new Error("Queue item not found");
  }

  const quoteItem = queueRow.phmb_quote_items as unknown as {
    cat_number: string;
    product_name: string;
    brand: string;
    product_classification: string;
  } | null;

  // 2. Update queue status to 'priced'
  const { error: queueError } = await supabase
    .from("phmb_procurement_queue")
    .update({
      status: "priced",
      priced_rmb: pricedRmb,
      updated_at: new Date().toISOString(),
    })
    .eq("id", queueItemId);

  if (queueError) throw queueError;

  // 3. Write price back to quote item
  const { error: itemError } = await supabase
    .from("phmb_quote_items")
    .update({
      list_price_rmb: pricedRmb,
      updated_at: new Date().toISOString(),
    })
    .eq("id", queueRow.quote_item_id);

  if (itemError) throw itemError;

  // 4. Upsert into price list (if cat_number is not empty)
  const catNumber = quoteItem?.cat_number ?? "";
  if (catNumber) {
    await supabase
      .from("phmb_price_list")
      .upsert(
        {
          org_id: queueRow.org_id,
          cat_number: catNumber,
          product_name: quoteItem?.product_name ?? "",
          brand: quoteItem?.brand ?? "",
          product_classification: quoteItem?.product_classification ?? "",
          list_price_rmb: pricedRmb,
        },
        { onConflict: "org_id,cat_number" }
      );
  }
}

export async function updateQueueItemStatus(
  queueItemId: string,
  newStatus: ProcurementQueueStatus
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_procurement_queue")
    .update({
      status: newStatus,
      updated_at: new Date().toISOString(),
    })
    .eq("id", queueItemId);

  if (error) throw error;
}
