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
  /**
   * Testing 2 row 85 — supplier minimum order quantity for this alternative's
   * invoice_item. When set and greater than the ordered quantity, the calc
   * engine rounds the line quantity up to this floor (max(ordered, MOQ)), so
   * the picker surfaces the effective quantity. Optional/nullable so pre-row-85
   * fixtures and pre-deploy API responses (which omit it) still typecheck; the
   * picker treats missing/null/0 as "no MOQ floor".
   */
  minimum_order_quantity?: number | null;
  version: number | null;
  frozen_at: string | null;
  /**
   * Testing 2 row 36: the КПП (supplier КП) creation date —
   * `invoices.created_at` for this alternative's invoice. Used as the
   * as-of date for the historical FX tooltip on the Цена column. Optional
   * so pre-row-36 test fixtures (and pre-deploy API responses) that omit
   * the field still typecheck; the picker treats missing/null as "no
   * historical date available" and renders the price without a tooltip.
   */
  kpp_date?: string | null;
  /**
   * Structural context for this alternative (Phase 5c Task 14).
   * "" for 1:1, "→ name ×ratio + ..." for split, "← name, ... объединены" for merge.
   */
  coverage_summary: string;
  /**
   * Set when this is a merged alternative (← объединены) AND the covered
   * quote_items carry different `markup` values. The calc engine uses the
   * first qi's markup (design.md §7.1 option a) — the UI surfaces this as
   * a warning so the sales user can decide.
   */
  divergent_markups: boolean;
}

/** One row in the CompositionPicker — a quote_item with its alternatives. */
export interface CompositionItem {
  quote_item_id: string;
  brand: string | null;
  sku: string | null;
  name: string | null;
  quantity: number | null;
  selected_invoice_id: string | null;
  /**
   * Testing 2 row 90: МОП-controlled inclusion flag. When `false` the
   * item is rendered greyed-out with an "Исключено по решению МОП" label
   * and is dropped by the backend `build_calculation_inputs()` so it does
   * not contribute to totals. Optional in the type so pre-row-90 test
   * fixtures (which omit the field) continue to typecheck; the picker
   * treats `undefined` the same as `true`. Pre-migration API responses
   * also omit the field — same behaviour.
   */
  included_in_calc?: boolean;
  alternatives: CompositionAlternative[];
}

/** Full response from GET /api/quotes/{id}/composition. */
export interface CompositionView {
  quote_id: string;
  items: CompositionItem[];
  composition_complete: boolean;
  can_edit: boolean;
  /**
   * Testing 2 row 36: the КП (quote) currency — the tooltip target for the
   * picker's Цена column. Optional/nullable so pre-deploy API responses
   * (and test fixtures) that omit it still typecheck; the picker falls back
   * to showing only the supplier-local price when it is absent.
   */
  currency_of_quote?: string | null;
}

// ============================================================================
// Quotes list — existing types
// ============================================================================

export interface QuoteListItem {
  id: string;
  idn_quote: string;
  created_at: string;
  workflow_status: string;
  total_quote_currency: number | null;
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
  /** Amount range filter (total_quote_currency gte/lte). */
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
  // head_of_logistics ↔ head_of_customs: in this org one person typically
  // wears both hats, so each "head_of" role covers the other's workflow
  // statuses (and also each other's allowed steps below).
  head_of_logistics: [
    "pending_logistics",
    "pending_logistics_and_customs",
    "pending_customs",
  ],
  customs: ["pending_customs", "pending_logistics_and_customs"],
  head_of_customs: [
    "pending_customs",
    "pending_logistics_and_customs",
    "pending_logistics",
  ],
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
    last_name: string | null;
    patronymic: string | null;
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

/**
 * Customer-side quote_item shape after Phase 5c migration 284.
 *
 * Migration 284 drops 10 supplier-side columns from `kvota.quote_items`
 * because they now live on `kvota.invoice_items` (per-supplier positions):
 *   invoice_id, purchase_price_original, purchase_currency, base_price_vat,
 *   price_includes_vat, customs_code, supplier_country, weight_in_kg,
 *   production_time_days, minimum_order_quantity, dimension_*_mm,
 *   license_*_cost.
 *
 * Those fields are intentionally absent here. Consumers that still read
 * them are legacy surfaces scheduled for Phase 5d refactor — they import
 * `QuoteItemRow` from `./queries`, not this type, and are unaffected.
 */
export interface QuoteItem {
  id: string;
  quote_id: string;
  brand: string | null;
  sku: string | null;
  supplier_sku: string | null;
  supplier_sku_note: string | null;
  product_name: string;
  manufacturer_product_name: string | null;
  quantity: number;
  unit: string | null;
  sale_price: number | null;
  vat_rate: number | null;
  is_unavailable: boolean;
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
  // head_of_logistics ↔ head_of_customs: cross-permission — the same person
  // typically holds both roles in this org, so each lead sees the other's
  // step. Avoid having to log out / impersonate to switch contexts.
  head_of_logistics: ["logistics", "customs", "documents"],
  customs: ["customs", "documents"],
  head_of_customs: ["customs", "logistics", "documents"],
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
//
// Resolution (quotes/[id]/page.tsx): editableSteps is the UNION across the
// user's roles of `ROLE_EDITABLE_STEPS[r] ?? ROLE_ALLOWED_STEPS[r]`. So an
// empty list contributes nothing (a user who ALSO holds an editing role still
// edits via that role); admin bypasses this map entirely.
//
// control-spec-workspace (Req 11.2/11.3):
//   - top_manager → [] : views the whole rail but edits nothing (read-only).
//   - quote_controller → ["control"] : edits only its Контроль расчёта gate.
//   - spec_controller → ["specification"] : edits only its Контроль спецификации
//     gate (it can still VIEW "control"/"cost-analysis"/"documents", but the
//     calc gate belongs to quote_controller). NOTE: this also makes
//     "documents"/"cost-analysis" view-only for a pure controller — deliberate
//     (controllers verify correctness, they don't author upstream data).
export const ROLE_EDITABLE_STEPS: Record<string, QuoteStep[]> = {
  procurement_senior: ["procurement", "documents"],
  top_manager: [],
  quote_controller: ["control"],
  spec_controller: ["specification"],
};

/**
 * Maps workflow_status → step for RAIL HIGHLIGHTING (which tab is active).
 *
 * NOTE: For default landing step (URL without ?step=), use STATUS_DEFAULT_STEP
 * from `entities/quote/default-step.ts` — that map intentionally differs.
 * See default-step.ts JSDoc for divergence rationale.
 */
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
