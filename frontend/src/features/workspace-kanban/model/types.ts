/**
 * UI-layer types for the logistics & customs kanban board.
 *
 * The business shapes (`WorkspaceKanbanCard`, board buckets) live in the
 * `workspace-invoice` entity — re-exported here so feature components import
 * them from a single place. This module adds only UI-specific concerns:
 * column metadata and the draggable card key.
 */

import type {
  WorkspaceKanbanCard,
  WorkspaceKanbanBoard,
  WorkspaceKanbanColumnKey,
} from "@/entities/workspace-invoice";

export type {
  WorkspaceKanbanCard,
  WorkspaceKanbanBoard,
  WorkspaceKanbanColumnKey,
};

/** Fixed left-to-right column order. */
export const KANBAN_COLUMNS: readonly WorkspaceKanbanColumnKey[] = [
  "unassigned",
  "in_progress",
  "completed",
] as const;

/** Russian column labels (REQ-2). */
export const KANBAN_COLUMN_LABELS: Record<WorkspaceKanbanColumnKey, string> = {
  unassigned: "Нераспределено",
  in_progress: "В работе",
  completed: "Завершено",
};

/** Stable draggable id / React key for a kanban card. */
export function cardKey(card: WorkspaceKanbanCard): string {
  return card.id;
}

/** Type guard — narrows a droppable id to a known column key. */
export function isKanbanColumnKey(
  value: string
): value is WorkspaceKanbanColumnKey {
  return (KANBAN_COLUMNS as readonly string[]).includes(value);
}

/**
 * The action a drop should trigger (REQ-7/8/9).
 *
 * - `self-pull` — member self-assigns (Нераспределено → В работе).
 * - `open-picker` — head opens the assignee picker (any column → В работе).
 * - `blocked` — invalid drop (member moving out of В работе, drop into
 *   Завершено which is auto-only, etc.) — surfaces a toast, no mutation.
 */
export type KanbanDragAction = "self-pull" | "open-picker" | "blocked";

/**
 * Map a drag (from-column, to-column, actor role) to its action. Pure — the
 * board calls this in `handleDragEnd` so the rule is unit-testable.
 */
export function resolveDragAction(
  from: WorkspaceKanbanColumnKey,
  to: WorkspaceKanbanColumnKey,
  isHead: boolean
): KanbanDragAction {
  // «Завершено» is auto-only — never a manual drop target (REQ-9).
  if (to === "completed") return "blocked";
  if (from === to) return "blocked";

  if (isHead) {
    // Heads assign / reassign by dropping into «В работе» (REQ-8).
    return to === "in_progress" ? "open-picker" : "blocked";
  }

  // Members may only pull from «Нераспределено» into «В работе» (REQ-7).
  if (from === "unassigned" && to === "in_progress") return "self-pull";
  return "blocked";
}
