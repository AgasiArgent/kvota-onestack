import type { ProcurementSubstatus } from "@/shared/lib/workflow-substates";

/** One invoice total attached to a kanban card. */
export interface KanbanInvoiceSum {
  invoice_number: string;
  currency: string;
  total: number;
}

/**
 * A single (quote, brand) slice as rendered on the kanban board. Mirrors the
 * shape returned by GET /api/quotes/kanban?status=pending_procurement.
 *
 * The kanban is scoped per-brand: one quote with N brands produces N cards.
 * `brand` is the empty string `""` for items without a brand — such unbranded
 * lines are grouped into a single "Без бренда" card per quote.
 */
export interface KanbanBrandCard {
  quote_id: string;
  brand: string;
  idn_quote: string;
  customer_name: string | null;
  days_in_state: number;
  latest_reason: string | null;
  procurement_substatus: ProcurementSubstatus;
  manager_name: string | null;
  procurement_user_names: string[];
  invoice_sums: KanbanInvoiceSum[];
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
