import type { ProcurementSubstatus } from "@/shared/lib/workflow-substates";

/** One invoice total attached to a kanban card. */
export interface KanbanInvoiceSum {
  invoice_number: string;
  currency: string;
  total: number;
}

/**
 * Latest open pause log row surfaced on «На паузе» cards (Testing 2 row 74).
 * Drives the inline reason display: «На паузе с ДД.ММ.ГГ: <reason> (<actor>)».
 */
export interface KanbanPauseLog {
  id: string;
  paused_at: string; // ISO-8601
  paused_by_name: string | null;
  reason: string;
}

/**
 * A single (quote, brand) slice as rendered on the kanban board. Mirrors the
 * shape returned by GET /api/quotes/kanban?status=pending_procurement.
 *
 * The kanban is scoped per-brand: one quote with N brands produces N cards.
 * `brand` is the empty string `""` for items without a brand — such unbranded
 * lines are grouped into a single "Без бренда" card per quote.
 *
 * The `*_id` fields are required for filtering (Testing 2 row 66 filter bar);
 * names alone collide when two customers/users share a label. They are
 * optional on the type to stay backwards-compatible with older API responses
 * (cached before the filter rollout).
 */
export interface KanbanBrandCard {
  quote_id: string;
  brand: string;
  idn_quote: string;
  customer_id?: string | null;
  customer_name: string | null;
  days_in_state: number;
  /**
   * ISO-8601 timestamp of the underlying `quote_brand_substates.updated_at`.
   * Used by the kanban board to sort newest-first (more precise than the
   * day-rounded `days_in_state`). Optional for backwards compat with
   * pre-deploy responses.
   */
  updated_at?: string | null;
  latest_reason: string | null;
  procurement_substatus: ProcurementSubstatus;
  manager_id?: string | null;
  manager_name: string | null;
  /** МОЗ ids parallel to `procurement_user_names` (same order). */
  procurement_user_ids?: string[];
  procurement_user_names: string[];
  invoice_sums: KanbanInvoiceSum[];
  /**
   * Tender flag from the parent quote (kvota.quotes.tender_type). Non-null
   * for КП distributed via the tender flow — surfaces as a «Тендер» badge
   * on the card so head_of_procurement can triage them differently
   * (Testing 2 row 67).
   */
  tender_type?: string | null;
  /**
   * Latest open pause log row (Testing 2 row 74). Null unless the card is
   * in the «На паузе» column AND there's an active pause_log row for the
   * quote. Drives inline reason display + click-through to history drawer.
   */
  pause_log?: KanbanPauseLog | null;
  /**
   * Quote-level `procurement_completed_at` timestamp (Testing 2 row 83).
   * Non-null cards represent slices whose workflow has already moved past
   * `pending_procurement` (e.g. `pending_logistics_and_customs`); they
   * stay visible on the procurement kanban so РОЗ / СтМОЗ / МОЗ can audit
   * the completed work instead of seeing the slice disappear silently.
   * The UI renders a «Готово» badge when this is set.
   */
  procurement_completed_at?: string | null;
}

/**
 * Stable identity for a (quote, brand) card — used as React key, draggable id,
 * and lookup key in optimistic-update state maps.
 */
export function brandCardKey(card: KanbanBrandCard): string {
  return `${card.quote_id}|${card.brand}`;
}

/** Parses a draggable id back into its (quote_id, brand) components. */
export function parseBrandCardKey(key: string): {
  quote_id: string;
  brand: string;
} {
  const sep = key.indexOf("|");
  if (sep === -1) return { quote_id: key, brand: "" };
  return {
    quote_id: key.slice(0, sep),
    brand: key.slice(sep + 1),
  };
}

/** Cards bucketed by substatus — one key per column. */
export type KanbanColumns = Record<ProcurementSubstatus, KanbanBrandCard[]>;

/** Full response shape from GET /api/quotes/kanban. */
export interface KanbanResponse {
  status: string;
  columns: KanbanColumns;
}
