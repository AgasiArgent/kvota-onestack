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
