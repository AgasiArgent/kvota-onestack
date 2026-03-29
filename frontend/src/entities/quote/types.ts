export interface QuoteListItem {
  id: string;
  idn_quote: string;
  created_at: string;
  workflow_status: string;
  total_amount_quote: number | null;
  total_profit_usd: number | null;
  currency: string | null;
  customer: { id: string; name: string } | null;
  manager: { id: string; full_name: string } | null;
  version_count: number;
  current_version: number;
}

export interface QuotesFilterParams {
  status?: string; // status group key or individual status
  customer?: string; // customer UUID
  manager?: string; // manager user UUID
  page?: number; // 1-based page number
  pageSize?: number; // default 20
}

export interface QuotesListResult {
  data: QuoteListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface StatusGroup {
  key: string;
  label: string;
  statuses: string[];
  color: string;
}

export const STATUS_GROUPS: StatusGroup[] = [
  {
    key: "draft",
    label: "Черновик",
    statuses: ["draft"],
    color: "bg-slate-100 text-slate-700",
  },
  {
    key: "in_progress",
    label: "В работе",
    statuses: ["pending_procurement", "logistics", "pending_customs", "pending_logistics_and_customs"],
    color: "bg-blue-100 text-blue-700",
  },
  {
    key: "approval",
    label: "Согласование",
    statuses: [
      "pending_quote_control",
      "pending_spec_control",
      "pending_sales_review",
      "pending_approval",
    ],
    color: "bg-amber-100 text-amber-700",
  },
  {
    key: "deal",
    label: "Сделка",
    statuses: ["approved", "sent_to_client", "accepted", "spec_signed", "deal"],
    color: "bg-green-100 text-green-700",
  },
  {
    key: "closed",
    label: "Закрыт",
    statuses: ["rejected", "cancelled"],
    color: "bg-red-100 text-red-700",
  },
];

const STATUS_GROUP_MAP = new Map<string, StatusGroup>();
for (const group of STATUS_GROUPS) {
  for (const status of group.statuses) {
    STATUS_GROUP_MAP.set(status, group);
  }
}

export function getStatusesForGroup(groupKey: string): string[] {
  const group = STATUS_GROUPS.find((g) => g.key === groupKey);
  return group?.statuses ?? [];
}

export function getGroupForStatus(status: string): StatusGroup | undefined {
  return STATUS_GROUP_MAP.get(status);
}

const ROLE_ACTION_STATUSES: Record<string, string[]> = {
  sales: ["pending_sales_review", "approved"],
  head_of_sales: ["pending_sales_review", "approved"],
  procurement: ["pending_procurement"],
  head_of_procurement: ["pending_procurement"],
  logistics: ["pending_logistics", "pending_logistics_and_customs"],
  head_of_logistics: ["pending_logistics", "pending_logistics_and_customs"],
  customs: ["pending_customs", "pending_logistics_and_customs"],
  quote_controller: ["pending_quote_control"],
  spec_controller: ["pending_spec_control"],
  top_manager: ["pending_approval"],
  admin: [
    "pending_sales_review", "approved",
    "pending_procurement",
    "pending_logistics", "pending_logistics_and_customs",
    "pending_customs",
    "pending_quote_control", "pending_spec_control",
    "pending_approval",
  ],
};

export function getActionStatusesForUser(roles: string[]): string[] {
  const statuses = new Set<string>();
  for (const role of roles) {
    const roleStatuses = ROLE_ACTION_STATUSES[role];
    if (roleStatuses) {
      for (const s of roleStatuses) statuses.add(s);
    }
  }
  return Array.from(statuses);
}

// ---------------------------------------------------------------------------
// Quote Detail types (for quote detail page migration)
// ---------------------------------------------------------------------------

export interface QuoteDetail {
  id: string;
  idn_quote: string;
  workflow_status: string;
  status: string;
  customer_id: string;
  contact_person_id: string | null;
  seller_company_id: string | null;
  currency_of_quote: string;
  delivery_city: string | null;
  delivery_method: string | null;
  offer_incoterms: string | null;
  payment_terms: string | null;
  tender_type: string | null;
  competitors: string | null;
  cancellation_reason: string | null;
  cancellation_comment: string | null;
  total_amount: number | null;
  margin_percent: number | null;
  markup_percent: number | null;
  profit_amount: number | null;
  created_at: string;
  updated_at: string | null;
  created_by: string | null;
  // FK resolved
  customer?: { id: string; name: string; inn: string | null } | null;
  contact_person?: {
    id: string;
    name: string;
    phone: string | null;
    email: string | null;
  } | null;
  seller_company?: {
    id: string;
    name: string;
    company_code: string;
  } | null;
  created_by_profile?: { id: string; full_name: string } | null;
}

export interface QuoteItem {
  id: string;
  quote_id: string;
  invoice_id: string | null;
  brand: string | null;
  sku: string | null;
  supplier_sku: string | null;
  supplier_sku_note: string | null;
  product_name: string;
  manufacturer_product_name: string | null;
  quantity: number;
  unit: string | null;
  purchase_price_original: number | null;
  purchase_currency: string | null;
  sale_price: number | null;
  weight_in_kg: number | null;
  dimension_height_mm: number | null;
  dimension_width_mm: number | null;
  dimension_length_mm: number | null;
  vat_rate: number | null;
  price_includes_vat: boolean;
  is_unavailable: boolean;
  production_time_days: number | null;
  procurement_status: string | null;
  created_at: string;
}

export interface QuoteInvoice {
  id: string;
  quote_id: string;
  invoice_number: string;
  supplier_id: string | null;
  buyer_company_id: string | null;
  pickup_country: string | null;
  pickup_city: string | null;
  currency: string | null;
  total_weight_kg: number | null;
  total_volume_m3: number | null;
  package_count: number | null;
  status: string | null;
  invoice_file_url: string | null;
  created_at: string;
  // FK resolved
  supplier?: { id: string; name: string } | null;
  buyer_company?: { id: string; name: string; company_code: string } | null;
}

export interface QuoteComment {
  id: string;
  quote_id: string;
  user_id: string;
  body: string;
  mentions: string[] | null;
  created_at: string;
  // FK resolved
  user_profile?: {
    id: string;
    full_name: string;
    role_slug: string;
  } | null;
}

export interface QuoteVersion {
  id: string;
  quote_id: string;
  version: number;
  status: string | null;
  input_variables: Record<string, unknown>;
  created_at: string;
  created_by: string | null;
}

// Step type for the status rail
export type QuoteStep =
  | "sales"
  | "calculation"
  | "procurement"
  | "logistics"
  | "customs"
  | "control"
  | "cost-analysis"
  | "negotiation"
  | "specification"
  | "documents";

// Role to allowed steps mapping
export const ROLE_ALLOWED_STEPS: Record<string, QuoteStep[]> = {
  admin: [
    "sales",
    "calculation",
    "procurement",
    "logistics",
    "customs",
    "control",
    "cost-analysis",
    "negotiation",
    "specification",
    "documents",
  ],
  sales: ["sales", "calculation", "negotiation", "specification", "documents"],
  head_of_sales: ["sales", "calculation", "negotiation", "specification", "documents"],
  procurement: ["procurement", "documents"],
  head_of_procurement: ["procurement", "documents"],
  logistics: ["logistics", "documents"],
  head_of_logistics: ["logistics", "documents"],
  customs: ["customs", "documents"],
  quote_controller: ["control", "cost-analysis", "documents"],
  spec_controller: ["specification", "control", "cost-analysis", "documents"],
  finance: ["cost-analysis", "documents"],
  top_manager: [
    "sales",
    "calculation",
    "procurement",
    "logistics",
    "customs",
    "control",
    "cost-analysis",
    "negotiation",
    "specification",
    "documents",
  ],
};

// Workflow status to step mapping (for rail highlighting)
export const STATUS_TO_STEP: Record<string, QuoteStep> = {
  draft: "sales",
  pending_procurement: "procurement",
  procurement_complete: "calculation",
  pending_calculation: "calculation",
  calculated: "calculation",
  pending_sales_review: "calculation",
  pending_approval: "control",
  approved: "negotiation",
  sent_to_client: "negotiation",
  accepted: "negotiation",
  rejected: "negotiation",
  pending_spec_control: "specification",
  spec_draft: "specification",
  spec_signed: "specification",
};
