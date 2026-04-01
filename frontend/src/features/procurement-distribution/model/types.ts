/** A single unassigned quote item from the server */
export interface UnassignedItemRow {
  id: string;
  quote_id: string;
  brand: string | null;
  product_name: string;
  quantity: number;
  created_at: string | null;
}

/** Quote-level metadata for grouping */
export interface QuoteInfo {
  id: string;
  idn: string;
  customer_name: string | null;
  sales_manager_name: string | null;
  created_at: string | null;
}

/** A brand group within a quote — the unit of assignment */
export interface BrandGroup {
  brand: string | null;
  itemCount: number;
  itemIds: string[];
}

/** A quote with its unassigned brand groups */
export interface QuoteWithBrandGroups {
  quote: QuoteInfo;
  brandGroups: BrandGroup[];
}

/** Procurement user with current workload (counted in quotes, not items) */
export interface ProcurementUserWorkload {
  user_id: string;
  full_name: string | null;
  active_quotes: number;
}
