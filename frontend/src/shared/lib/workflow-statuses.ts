/**
 * Single source of truth for `quotes.workflow_status` enum → human-readable
 * Russian labels.
 *
 * The enum is defined on the Python side (`services/workflow_service.py`
 * `WorkflowStatus`) and the DB stores raw enum values in
 * `kvota.quotes.workflow_status`. The /quotes registry, the filter dropdown,
 * the sidebar action group, and any other UI that needs to display a
 * workflow_status to a user must go through this map — never render the raw
 * enum value (e.g. "pending_procurement") to end users.
 *
 * NOTE: This intentionally covers EVERY enum value the backend can store,
 * including transient/legacy ones like `procurement_complete` that don't
 * appear in the filter dropdown but can land on a quote row. Without full
 * coverage the table renders English fallback strings to МОЗ/МОП/etc.
 * (regression: МОЗ-47, 2026-05-05 ROP test session).
 */

/** Russian labels keyed by `quotes.workflow_status`. */
export const WORKFLOW_STATUS_LABELS_RU: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "Закупки",
  procurement_complete: "Закупки завершены",
  pending_logistics: "Логистика",
  pending_customs: "Таможня",
  pending_logistics_and_customs: "Логистика и таможня",
  pending_quote_control: "Контроль КП",
  pending_spec_control: "Контроль спец.",
  pending_sales_review: "Ревью продаж",
  pending_approval: "На утверждении",
  approved: "Одобрено",
  sent_to_client: "Отправлено клиенту",
  client_negotiation: "Торги с клиентом",
  accepted: "Принято",
  pending_signature: "Подписание",
  spec_signed: "Спецификация",
  deal: "Сделка",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

/**
 * Subset of statuses that are surfaced in the /quotes filter dropdown.
 * Order is meaningful — it's the order shown in the multi-select UI.
 *
 * Terminal/transient states (procurement_complete, accepted) are excluded
 * because filtering by them rarely matches user intent — but
 * WORKFLOW_STATUS_LABELS_RU still covers them so a row carrying that status
 * renders a Russian label.
 */
export const WORKFLOW_STATUS_FILTER_VALUES: readonly string[] = [
  "draft",
  "pending_procurement",
  "pending_logistics",
  "pending_customs",
  "pending_logistics_and_customs",
  "pending_quote_control",
  "pending_spec_control",
  "pending_sales_review",
  "pending_approval",
  "approved",
  "sent_to_client",
  "spec_signed",
  "deal",
  "rejected",
  "cancelled",
];

/** Build the {value, label} options used by the /quotes status filter. */
export function getWorkflowStatusFilterOptions(): {
  value: string;
  label: string;
}[] {
  return WORKFLOW_STATUS_FILTER_VALUES.map((value) => ({
    value,
    label: WORKFLOW_STATUS_LABELS_RU[value] ?? value,
  }));
}

/**
 * Stages whose duration is tracked by the deadline timer — the only stages
 * that can carry a configurable per-org deadline (Настройки › «Дедлайны
 * стадий»).
 *
 * Mirrors the Python `IN_PROGRESS_STATUSES` set in
 * `services/workflow_service.py`: every non-terminal, non-draft workflow
 * status. The stage timer (`services/stage_timer_service.py`) keys deadlines
 * by `quotes.workflow_status` and skips only `TERMINAL_STATUSES`
 * (draft, deal, rejected, cancelled), so this list MUST stay in sync with that
 * set or a quote can sit in a stage the settings screen can't configure
 * (e.g. `approved` was missing — it silently fell through to no_deadline).
 *
 * Order is meaningful — it's the row order in the settings table.
 */
export const DEADLINE_TRACKED_STAGES: readonly string[] = [
  "pending_procurement",
  "pending_logistics",
  "pending_customs",
  "pending_logistics_and_customs",
  "pending_sales_review",
  "pending_quote_control",
  "pending_approval",
  "approved",
  "sent_to_client",
  "client_negotiation",
  "pending_spec_control",
  "pending_signature",
];

/**
 * Build the {stage, label} options for the stage-deadline settings table,
 * deriving labels from {@link WORKFLOW_STATUS_LABELS_RU} so the settings list
 * never drifts from the canonical workflow vocabulary.
 */
export function getDeadlineTrackedStageOptions(): {
  stage: string;
  label: string;
}[] {
  return DEADLINE_TRACKED_STAGES.map((stage) => ({
    stage,
    label: WORKFLOW_STATUS_LABELS_RU[stage] ?? stage,
  }));
}

/**
 * Return the Russian label for `workflow_status`, falling back to the raw
 * value only when truly unknown — a missing label is a bug, not graceful
 * degradation. Callers should still pass the fallback through so users see
 * *something* rather than a blank cell.
 */
export function workflowStatusLabel(status: string | null | undefined): string {
  if (!status) return "—";
  return WORKFLOW_STATUS_LABELS_RU[status] ?? status;
}
