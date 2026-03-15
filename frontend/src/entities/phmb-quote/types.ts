export type PhmbQuoteStatus = "draft" | "waiting_prices" | "ready";

export interface PhmbQuoteListItem {
  id: string;
  idn_quote: string;
  customer_name: string;
  items_total: number;
  items_priced: number;
  total_amount_usd: number | null;
  status: PhmbQuoteStatus;
  created_at: string;
}

export interface CreatePhmbQuoteInput {
  customer_id: string;
  currency: string;
  seller_company_id: string;
  phmb_advance_pct: number;
  phmb_payment_days: number;
  phmb_markup_pct: number;
}

export interface PhmbDefaults {
  default_advance_pct: number;
  default_payment_days: number;
  default_markup_pct: number;
}

export interface SellerCompany {
  id: string;
  name: string;
}

export interface CustomerSearchResult {
  id: string;
  name: string;
  inn: string | null;
}

// --- Version types ---

export interface PhmbVersion {
  id: string;
  quote_id: string;
  version_number: number;
  label: string;
  phmb_advance_pct: number;
  phmb_payment_days: number;
  phmb_markup_pct: number;
  total_amount_usd: number | null;
  created_at: string;
  updated_at: string;
}

// --- Workspace types (Screen 2) ---

export interface PhmbQuoteDetail {
  id: string;
  idn_quote: string;
  customer_name: string;
  currency: string;
  phmb_advance_pct: number;
  phmb_payment_days: number;
  phmb_markup_pct: number;
  total_amount_usd: number | null;
  created_at: string;
}

export type PhmbItemStatus = "priced" | "waiting";

export interface PhmbQuoteItem {
  id: string;
  quote_id: string;
  cat_number: string;
  product_name: string;
  brand: string;
  product_classification: string;
  quantity: number;
  list_price_rmb: number | null;
  discount_pct: number;
  hs_code: string | null;
  duty_pct: number | null;
  delivery_days: number | null;
  // Calculated fields (populated by calc API)
  exw_price_usd: number | null;
  cogs_usd: number | null;
  financial_cost_usd: number | null;
  total_price_usd: number | null;
  total_price_with_vat_usd: number | null;
  // Computed client-side
  status: PhmbItemStatus;
}

export interface PriceListSearchResult {
  id: string;
  cat_number: string;
  product_name: string;
  brand: string;
  product_classification: string;
  list_price_rmb: number;
  discount_pct: number;
}

export interface CalcResult {
  items: Array<{
    id: string;
    exw_price_usd: number;
    cogs_usd: number;
    financial_cost_usd: number;
    total_price_usd: number;
    total_price_with_vat_usd: number;
  }>;
  totals: {
    subtotal_usd: number;
    total_usd: number;
    total_with_vat_usd: number;
  };
}

// --- Procurement Queue types (Screen 3) ---

export type ProcurementQueueStatus = "new" | "requested" | "priced";

export interface ProcurementQueueItem {
  id: string;
  quote_item_id: string;
  quote_id: string;
  brand: string;
  brand_group_id: string | null;
  status: ProcurementQueueStatus;
  priced_rmb: number | null;
  notes: string | null;
  created_at: string;
  // Joined from phmb_quote_items
  cat_number: string;
  product_name: string;
  quantity: number;
  delivery_days: number | null;
  // Joined from quotes
  quote_idn: string;
  customer_name: string;
}

export interface BrandGroup {
  id: string;
  name: string;
}
