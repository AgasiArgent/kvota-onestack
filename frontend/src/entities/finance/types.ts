export interface DealListItem {
  id: string;
  deal_number: string;
  spec_number: string | null;
  quote_idn: string | null;
  customer_name: string | null;
  total_amount_usd: number | null;
  profit_usd: number | null;
  sign_date: string | null;
  status: "active" | "completed" | "cancelled";
  payment_terms: string | null;
  // ERPS extended columns (for expanded view)
  advance_percent: number | null;
  total_paid_usd: number | null;
  remaining_usd: number | null;
  deadline: string | null;
}

export interface DealSummary {
  active_count: number;
  active_total: number;
  completed_count: number;
  completed_total: number;
  cancelled_count: number;
  cancelled_total: number;
  total_count: number;
  total_amount: number;
}

export interface DealsFilterParams {
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface DealsListResult {
  data: DealListItem[];
  summary: DealSummary;
  total: number;
  page: number;
  pageSize: number;
}

export interface PaymentRecord {
  id: string;
  deal_id: string;
  deal_number: string;
  customer_name: string | null;
  category_id: string;
  category_name: string;
  category_slug: string;
  is_income: boolean;
  description: string | null;
  planned_amount: number | null;
  planned_date: string | null;
  planned_currency: string;
  actual_amount: number | null;
  actual_currency: string | null;
  actual_date: string | null;
}

export interface PaymentsFilterParams {
  grouping?: "records" | "customers";
  type?: "income" | "expense";
  payment_status?: "plan" | "paid" | "overdue";
  date_from?: string;
  date_to?: string;
  page?: number;
  pageSize?: number;
}

export interface PaymentTotals {
  planned_income: number;
  actual_income: number;
  planned_expense: number;
  actual_expense: number;
  balance: number;
}

export interface PaymentsListResult {
  data: PaymentRecord[];
  totals: PaymentTotals;
  total: number;
  page: number;
  pageSize: number;
}

export interface SupplierInvoiceItem {
  id: string;
  invoice_number: string;
  supplier_name: string | null;
  date: string | null;
  amount: number | null;
  currency: string;
  status: string;
  quote_idn: string | null;
}

export interface SupplierInvoicesFilterParams {
  page?: number;
  pageSize?: number;
}

export interface CurrencyTotal {
  currency: string;
  total: number;
}

export interface SupplierInvoicesListResult {
  data: SupplierInvoiceItem[];
  currency_totals: CurrencyTotal[];
  total: number;
  page: number;
  pageSize: number;
}

// Status display configuration
export const DEAL_STATUS_LABELS: Record<string, string> = {
  active: "В работе",
  completed: "Завершено",
  cancelled: "Отменено",
};

export const DEAL_STATUS_COLORS: Record<string, string> = {
  active: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

export const SUPPLIER_INVOICE_STATUS_LABELS: Record<string, string> = {
  pending: "Ожидает",
  paid: "Оплачен",
  partial: "Частично",
  cancelled: "Отменён",
  overdue: "Просрочен",
};

export const SUPPLIER_INVOICE_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-700",
  paid: "bg-green-100 text-green-700",
  partial: "bg-blue-100 text-blue-700",
  cancelled: "bg-red-100 text-red-700",
  overdue: "bg-red-100 text-red-700",
};

// Logistics stage label map
const STAGE_LABELS: Record<string, string> = {
  first_mile: "Первая миля",
  hub: "Хаб",
  consolidation: "Консолидация",
  main_line: "Основная линия",
  customs_clearance: "Таможенная очистка",
  last_mile: "Последняя миля",
  warehouse: "Склад",
};

export function formatStageLabel(raw: string): string {
  for (const [key, label] of Object.entries(STAGE_LABELS)) {
    if (raw.includes(key)) return raw.replace(key, label);
  }
  return raw;
}

// ---------------------------------------------------------------------------
// Plan-Fact types
// ---------------------------------------------------------------------------

export type PlanFactCurrency = "RUB" | "USD" | "EUR";

export interface PlanFactCategory {
  id: string;
  code: string;
  name: string;
  is_income: boolean;
  display_order: number;
}

export interface PlanFactItem {
  id: string;
  deal_id: string;
  category: {
    id: string;
    code: string;
    name: string;
    is_income: boolean;
  };
  description: string;
  planned_amount: number;
  planned_currency: PlanFactCurrency;
  planned_date: string;
  actual_amount: number | null;
  actual_currency: PlanFactCurrency | null;
  actual_date: string | null;
  variance_amount: number | null;
  payment_document: string | null;
  notes: string | null;
  created_at: string;
}

export interface CreatePlanFactPayload {
  category_id: string;
  description: string;
  planned_amount: number;
  planned_currency: PlanFactCurrency;
  planned_date: string;
}

export interface RecordActualPayload {
  actual_amount: number;
  actual_currency: PlanFactCurrency;
  actual_date: string;
  payment_document?: string;
  notes?: string;
}

export interface QuoteSearchResult {
  id: string;
  idn: string;
  customer_name: string;
  deal_id: string;
  deal_number: string;
}

const FINANCE_ALLOWED_ROLES = ["admin", "finance", "top_manager"];

export function canAccessFinance(roles: string[]): boolean {
  return roles.some((r) => FINANCE_ALLOWED_ROLES.includes(r));
}
