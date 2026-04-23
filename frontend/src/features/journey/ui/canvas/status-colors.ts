/**
 * Status → semantic Tailwind token mapping.
 *
 * Reqs 4.4 / 4.5 dictate the canonical colour meaning:
 *   impl_status: done=green, partial=yellow, missing=red, unset=grey
 *   qa_status:   verified=green, broken=red, untested=grey
 *
 * We map each literal onto one of the project's existing semantic tokens
 * (`--color-success`, `--color-warning`, `--color-error`, `--color-text-subtle`,
 * `--color-info`) defined in `src/app/globals.css`. Introducing journey-specific
 * colour tokens was considered and rejected — the existing palette already
 * covers the four states and we keep a single source of truth.
 */

import type { GhostStatus, ImplStatus, QaStatus } from "@/entities/journey";

/** Tailwind background class for the status dot. */
export function implStatusDotClass(status: ImplStatus | null): string {
  switch (status) {
    case "done":
      return "bg-success";
    case "partial":
      return "bg-warning";
    case "missing":
      return "bg-error";
    default:
      return "bg-text-subtle";
  }
}

export function qaStatusDotClass(status: QaStatus | null): string {
  switch (status) {
    case "verified":
      return "bg-success";
    case "broken":
      return "bg-error";
    default:
      return "bg-text-subtle";
  }
}

/** Badge colour classes for ghost-status chips. */
export function ghostStatusBadgeClasses(status: GhostStatus): string {
  switch (status) {
    case "proposed":
      return "bg-warning-bg text-warning";
    case "approved":
    case "in_progress":
      return "bg-accent-subtle text-info";
    case "shipped":
      return "bg-success-bg text-success";
    default:
      return "bg-accent-subtle text-text-muted";
  }
}

/** Human-readable Russian labels for the ghost-status badge. */
export function ghostStatusLabel(status: GhostStatus): string {
  switch (status) {
    case "proposed":
      return "Предложен";
    case "approved":
      return "Одобрен";
    case "in_progress":
      return "В разработке";
    case "shipped":
      return "Реализован";
    default:
      return status;
  }
}
