/**
 * Pure filter helpers for the logistics / customs kanban board (Testing 2
 * rows 64-65). Splitting them out of the React component keeps the matching
 * logic unit-testable without a DOM environment.
 */

import { isInUrgencyBucket, type UrgencyBucket } from "@/shared/ui/filter-bar";
import type {
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
} from "@/entities/workspace-invoice";

export interface WorkspaceFilterState {
  /** Selected customer ids — empty means «all clients». */
  customerIds: readonly string[];
  /** Selected assignee user-ids — empty means «all assignees». */
  assigneeIds: readonly string[];
  /** ISO YYYY-MM-DD lower bound on `stageEnteredAt` (inclusive). */
  stageFrom: string | null;
  /** ISO YYYY-MM-DD upper bound on `stageEnteredAt` (inclusive). */
  stageTo: string | null;
  /** Срочность bucket against `deadlineAt`. */
  urgency: UrgencyBucket | null;
}

export function emptyWorkspaceFilters(): WorkspaceFilterState {
  return {
    customerIds: [],
    assigneeIds: [],
    stageFrom: null,
    stageTo: null,
    urgency: null,
  };
}

export function hasActiveWorkspaceFilters(
  filters: WorkspaceFilterState
): boolean {
  return (
    filters.customerIds.length > 0 ||
    filters.assigneeIds.length > 0 ||
    filters.stageFrom !== null ||
    filters.stageTo !== null ||
    filters.urgency !== null
  );
}

/**
 * Decide whether a single card passes the filter set.
 *
 * Empty filter slots are no-ops (match everything). All non-empty slots are
 * combined with AND. Cards missing the field a non-empty filter targets
 * (no customer id, no assignee, no deadline) are excluded — they cannot
 * match a specific positive selection.
 */
export function cardPassesFilters(
  card: WorkspaceKanbanCard,
  filters: WorkspaceFilterState,
  now: Date = new Date()
): boolean {
  // Customer
  if (filters.customerIds.length > 0) {
    if (!card.customerId || !filters.customerIds.includes(card.customerId))
      return false;
  }

  // Assignee
  if (filters.assigneeIds.length > 0) {
    if (!card.assignedUserId) return false;
    if (!filters.assigneeIds.includes(card.assignedUserId)) return false;
  }

  // Stage-entered date range (inclusive, UTC day-precision).
  //
  // The `stageFrom` / `stageTo` strings are picked from a native date input
  // — they are calendar days, not timestamps. We anchor them to UTC midnight
  // / end-of-day so the comparison is stable regardless of the user's local
  // tz (otherwise a card timestamped 23:30Z would mis-bucket on the user's
  // last calendar day of the range).
  if (filters.stageFrom || filters.stageTo) {
    const ts = card.stageEnteredAt
      ? new Date(card.stageEnteredAt).getTime()
      : NaN;
    if (Number.isNaN(ts)) return false;
    if (filters.stageFrom) {
      const lower = new Date(`${filters.stageFrom}T00:00:00Z`).getTime();
      if (Number.isFinite(lower) && ts < lower) return false;
    }
    if (filters.stageTo) {
      // End of UTC day — inclusive upper bound.
      const upper = new Date(`${filters.stageTo}T23:59:59.999Z`).getTime();
      if (Number.isFinite(upper) && ts > upper) return false;
    }
  }

  // Urgency (deadline-based)
  if (filters.urgency) {
    if (!isInUrgencyBucket(card.deadlineAt, filters.urgency, now)) return false;
  }

  return true;
}

/**
 * Filter every column in a workspace kanban board by the given filter set.
 * Returns a new board object — never mutates `board`.
 */
export function filterWorkspaceBoard(
  board: WorkspaceKanbanBoard,
  filters: WorkspaceFilterState,
  now: Date = new Date()
): WorkspaceKanbanBoard {
  return {
    unassigned: board.unassigned.filter((c) =>
      cardPassesFilters(c, filters, now)
    ),
    in_progress: board.in_progress.filter((c) =>
      cardPassesFilters(c, filters, now)
    ),
    completed: board.completed.filter((c) =>
      cardPassesFilters(c, filters, now)
    ),
  };
}

export function totalCardCount(board: WorkspaceKanbanBoard): number {
  return (
    board.unassigned.length + board.in_progress.length + board.completed.length
  );
}
