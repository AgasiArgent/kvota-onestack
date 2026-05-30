/**
 * Domain types for the /workspace/control board (control-spec-workspace Req 9).
 *
 * A `ControlKanbanCard` is a quote in one of the control gates, rendered as a
 * clickable (NOT draggable) kanban card. The card lives in the entity layer so
 * both the fetcher (entities) and the renderer (features/workspace-control) can
 * depend on it without violating FSD's top-down import rule.
 */

/** Which control board a fetch targets. */
export type ControlBoardDomain = "calc" | "spec";

/**
 * One quote rendered as a control-board card. `workflowStatus` maps the card to
 * its column (e.g. `pending_spec_control` → «На контроле», `pending_signature`
 * → «На подписании»).
 */
export interface ControlKanbanCard {
  quoteId: string;
  idnQuote: string;
  customerName: string;
  total: number | null;
  currency: string;
  workflowStatus: string;
  /** Assigned controller's ФИО, or null while the gate is still unclaimed. */
  controllerName: string | null;
}

/** Workflow statuses that make up the «Контроль расчёта» (calc) board. */
export const CALC_BOARD_STATUSES = [
  "pending_quote_control",
  "pending_approval",
] as const;

/** Workflow statuses that make up the «Контроль спецификации» (spec) board. */
export const SPEC_BOARD_STATUSES = [
  "pending_spec_control",
  "pending_signature",
] as const;

/** The set of workflow statuses a given control board renders. */
export function boardStatuses(domain: ControlBoardDomain): readonly string[] {
  return domain === "calc" ? CALC_BOARD_STATUSES : SPEC_BOARD_STATUSES;
}
