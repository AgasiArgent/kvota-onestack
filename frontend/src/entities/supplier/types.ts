/**
 * Suppliers table row (Testing 2 row 84). Columns:
 *   1. Наименование (name)
 *   2. Страна (country)
 *   3. МОЗ (assigned procurement manager — first supplier_assignees user)
 *   4. Дата последнего КПП (MAX(invoices.created_at) for this supplier)
 *   5. Сумма КПП (SUM(invoice_items.purchase_price_original * quantity)
 *                  per-КПП converted to USD via kvota.exchange_rates looked up
 *                  by the КПП's created_at, then summed; rounded to integer USD)
 *   6. Статус (is_active)
 *
 * `invoice_total_usd` is null when the supplier has no priced КПП or every
 * КПП currency lacks an FX rate. Otherwise it's an integer USD value.
 */
export interface SupplierListItem {
  id: string;
  name: string;
  country: string | null;
  is_active: boolean;
  assignee_name: string | null;
  last_invoice_at: string | null;
  invoice_total_usd: number | null;
}

export interface SupplierDetail {
  id: string;
  organization_id: string;
  name: string;
  supplier_code: string | null;
  country: string | null;
  /** ISO 3166-1 alpha-2 (migration 295). Nullable for unmatched legacy rows. */
  country_code: string | null;
  city: string | null;
  registration_number: string | null;
  default_payment_terms: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface SupplierContact {
  id: string;
  supplier_id: string;
  name: string;
  position: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface BrandAssignment {
  id: string;
  brand: string;
  supplier_id: string;
  is_primary: boolean;
  notes: string | null;
  created_at: string | null;
}

export interface SupplierAssignee {
  user_id: string;
  full_name: string;
  created_at: string;
}

export interface SupplierQuoteItem {
  id: string;
  product_name: string | null;
  brand: string | null;
  sku: string | null;
  idn_sku: string | null;
  quantity: number | null;
  purchase_price: number | null;
  purchase_currency: string | null;
  procurement_date: string | null;
  quote_idn: string;
}
