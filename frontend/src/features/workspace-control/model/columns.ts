import type { ColumnConfig } from "@/features/workspace-kanban";
import type { ControlBoardDomain } from "@/entities/workspace-control";

/**
 * Control-board column layouts (control-spec-workspace Req 9.2 / 9.3). Each
 * column key IS a workflow status — `ControlBoard` buckets cards by their
 * `workflowStatus` against these keys.
 *
 * - calc board: «На контроле» (pending_quote_control) → «На согласовании»
 *   (pending_approval).
 * - spec board: «На контроле» (pending_spec_control) → «На подписании»
 *   (pending_signature).
 *
 * Labels are board-local (the kanban-column phrasing the owner specified) and
 * deliberately not pulled from the global STATUS_LABELS map, which uses a
 * different register («Контроль КП», «На согласовании») for badges.
 */
export const CALC_COLUMNS: ColumnConfig[] = [
  { key: "pending_quote_control", label: "На контроле" },
  { key: "pending_approval", label: "На согласовании" },
];

export const SPEC_COLUMNS: ColumnConfig[] = [
  { key: "pending_spec_control", label: "На контроле" },
  { key: "pending_signature", label: "На подписании" },
];

export function columnsForDomain(domain: ControlBoardDomain): ColumnConfig[] {
  return domain === "calc" ? CALC_COLUMNS : SPEC_COLUMNS;
}
