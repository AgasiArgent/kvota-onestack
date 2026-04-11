// ============================================================================
// Phase 5b — Composition (multi-supplier quote composition)
// ============================================================================
// These types mirror the response shape of GET /api/quotes/{id}/composition
// in api/composition.py. The picker UI consumes this shape directly.

/** A single supplier invoice alternative for one quote_item. */
export interface CompositionAlternative {
  invoice_id: string;
  supplier_id: string | null;
  supplier_name: string | null;
  supplier_country: string | null;
  purchase_price_original: number | null;
  purchase_currency: string | null;
  base_price_vat: number | null;
  price_includes_vat: boolean | null;
  production_time_days: number | null;
  version: number | null;
  frozen_at: string | null;
}

/** One row in the CompositionPicker — a quote_item with its alternatives. */
export interface CompositionItem {
  quote_item_id: string;
  brand: string | null;
  sku: string | null;
  name: string | null;
  quantity: number | null;
  selected_invoice_id: string | null;
  alternatives: CompositionAlternative[];
}

/** Full response from GET /api/quotes/{id}/composition. */
export interface CompositionView {
  quote_id: string;
  items: CompositionItem[];
  composition_complete: boolean;
  can_edit: boolean;
}

// ============================================================================
// Quotes list — existing types
// ============================================================================

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
  brands: readonly string[];
  procurement_managers: readonly { id: string; full_name: string }[];
  logistics_user: { id: string; full_name: string } | null;
  customs_user: { id: string; full_name: string } | null;
}

export interface QuotesFilterParams {
  /** Multi-value status filter (workflow_status IN). Comma-separated in URL. */
  status?: readonly string[];
  /** Multi-value customer filter (customer_id IN). */
  customer?: readonly string[];
  /** Multi-value sales manager filter (created_by IN). */
  manager?: readonly string[];
  /** Multi-value brand filter (quote_items.brand IN → quote IDs). */
  brand?: readonly string[];
  /** Multi-value procurement manager filter (quote_items.assigned_procurement_user IN → quote IDs). */
  procurement_manager?: readonly string[];
  /**
   * Composite participant filter. Values in the form "<role>:<user_id>".
   * Roles: sales, procurement, logistics, customs.
   * Logic controls whether a quote must match ALL selected participants
   * (and) or ANY of them (or, default).
   */
  participants?: readonly string[];
  participants_logic?: "or" | "and";
  /** Amount range filter (total_amount_quote gte/lte). */
  amount_min?: number;
  amount_max?: number;
  /** Sort field with optional leading minus for desc. Format: "amount" | "-amount" | "created_at". */
  sort?: string;
  /** Full-text search over idn_quote, customer name, and brand names. */
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface QuotesListResult {
  data: QuoteListItem[];
  total: number;
  page: number;
  pageSize: number;
}

const ROLE_ACTION_STATUSES: Record<string, string[]> = {
  sales: ["pending_sales_review", "approved"],
  head_of_sales: ["pending_sales_review", "approved"],
  procurement: ["pending_procurement"],
  procurement_senior: ["pending_procurement"],
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
  cancelled_at: string | null;
  cancelled_by: string | null;
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
  min_order_quantity: number | null;
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

export interface CommentAttachment {
  id: string;
  original_filename: string;
  storage_path: string;
  mime_type: string | null;
  file_size_bytes: number | null;
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
  attachments?: CommentAttachment[];
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
  | "documents"
  | "plan-fact";

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
    "plan-fact",
  ],
  sales: ["sales", "calculation", "negotiation", "specification", "documents"],
  head_of_sales: ["sales", "calculation", "negotiation", "specification", "documents"],
  procurement: ["procurement", "documents"],
  head_of_procurement: ["procurement", "documents"],
  procurement_senior: [
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
    "plan-fact",
  ],
  logistics: ["logistics", "documents"],
  head_of_logistics: ["logistics", "documents"],
  customs: ["customs", "documents"],
  quote_controller: ["control", "cost-analysis", "documents"],
  spec_controller: ["specification", "control", "cost-analysis", "documents"],
  finance: ["cost-analysis", "documents", "plan-fact"],
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
    "plan-fact",
  ],
};

// Roles that can view all steps but only edit specific ones.
// If a role is NOT listed here, it can edit all its allowed steps.
export const ROLE_EDITABLE_STEPS: Record<string, QuoteStep[]> = {
  procurement_senior: ["procurement", "documents"],
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
  cancelled: "sales",
};
