import type { ProcurementSubstatus } from "@/shared/lib/workflow-substates";

/** One invoice total attached to a kanban card. */
export interface KanbanInvoiceSum {
  invoice_number: string;
  currency: string;
  total: number;
}

/**
 * A single quote card as rendered on the kanban board. Mirrors the shape
 * returned by GET /api/quotes/kanban?status=pending_procurement.
 */
export interface KanbanQuoteCard {
  id: string;
  idn_quote: string;
  customer_name: string | null;
  days_in_state: number;
  latest_reason: string | null;
  procurement_substatus: ProcurementSubstatus;
  brands: string[];
  manager_name: string | null;
  procurement_user_names: string[];
  invoice_sums: KanbanInvoiceSum[];
}

/** Quotes bucketed by substatus — one key per column. */
export type KanbanColumns = Record<ProcurementSubstatus, KanbanQuoteCard[]>;

/** Full response shape from GET /api/quotes/kanban. */
export interface KanbanResponse {
  status: string;
  columns: KanbanColumns;
}
