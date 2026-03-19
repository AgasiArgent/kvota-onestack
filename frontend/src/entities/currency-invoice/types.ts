export interface CurrencyInvoice {
  id: string;
  invoice_number: string;
  segment: "EURTR" | "TRRU";
  status: "draft" | "verified" | "exported";
  total_amount: number | null;
  currency: string;
  seller_name: string | null;
  buyer_name: string | null;
  markup_percent: number;
  created_at: string;
  deal_id: string;
  deal_number: string | null;
  quote_idn: string | null;
  customer_name: string | null;
}

export interface CurrencyInvoiceItem {
  id: string;
  product_name: string;
  sku: string | null;
  idn_sku: string | null;
  manufacturer: string | null;
  unit: string | null;
  hs_code: string | null;
  quantity: number;
  base_price: number;
  price: number;
  total: number;
  sort_order: number;
}

export interface CurrencyInvoiceDetail extends CurrencyInvoice {
  items: CurrencyInvoiceItem[];
  seller_entity_type: string | null;
  seller_entity_id: string | null;
  buyer_entity_type: string | null;
  buyer_entity_id: string | null;
}

export interface CIFilterParams {
  status?: string;
  segment?: string;
  page?: number;
  pageSize?: number;
}

export interface CIListResult {
  data: CurrencyInvoice[];
  total: number;
  page: number;
  pageSize: number;
}

export interface CompanyOption {
  id: string;
  name: string;
}

export const SEGMENT_LABELS: Record<string, string> = {
  EURTR: "EURTR",
  TRRU: "TRRU",
};

export const SEGMENT_COLORS: Record<string, string> = {
  EURTR: "bg-blue-100 text-blue-700",
  TRRU: "bg-purple-100 text-purple-700",
};

export const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  verified: "Подтверждён",
  exported: "Экспортирован",
};

export const STATUS_COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  verified: "bg-green-100 text-green-700",
  exported: "bg-blue-100 text-blue-700",
};

const CI_ALLOWED_ROLES = [
  "admin",
  "currency_controller",
  "finance",
  "training_manager",
];

export function canAccessCurrencyInvoices(roles: string[]): boolean {
  return roles.some((r) => CI_ALLOWED_ROLES.includes(r));
}

const CI_ADMIN_ROLES = ["admin", "currency_controller", "training_manager"];

export function canManageCurrencyInvoices(roles: string[]): boolean {
  return roles.some((r) => CI_ADMIN_ROLES.includes(r));
}
