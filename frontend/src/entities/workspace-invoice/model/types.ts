/**
 * Workspace-invoice domain types for the logistics & customs kanban boards.
 *
 * `WorkspaceKanbanCard` is the business shape produced by `fetchKanbanInvoices`
 * and rendered by the `workspace-kanban` feature. It lives in the entity layer
 * so both the data query (entities) and the UI (features) can depend on it
 * without violating FSD's top-down import rule.
 */

import type { LocationChipLocation } from "@/entities/location/ui/location-chip";
import type { UserAvatarChipUser } from "@/entities/user";

export type WorkspaceDomain = "logistics" | "customs";

/** Which kanban column an invoice falls into for a given domain. */
export type WorkspaceKanbanColumnKey =
  | "unassigned"
  | "in_progress"
  | "completed";

/** One cargo place (box) with its dimensions, sourced from invoice_cargo_places. */
export interface WorkspaceCargoPlace {
  position: number;
  weightKg: number | null;
  lengthMm: number | null;
  widthMm: number | null;
  heightMm: number | null;
}

/**
 * A single invoice rendered as a kanban card. The same business entity at the
 * logistics or customs stage — `domain` selects which timer / assignee fields
 * apply.
 */
export interface WorkspaceKanbanCard {
  id: string;
  quoteId: string;
  invoiceNumber: string;
  /** "Q-202604-0018 / inv-1" — display IDN. */
  idn: string;
  quoteIdn: string;
  customerName: string;
  pickupLocation: LocationChipLocation;
  deliveryLocation: LocationChipLocation;
  /** Stage entry — drives the running timer (= procurement_completed_at). */
  stageEnteredAt: string;
  /** `{domain}_assigned_at` — null while the card sits in «Нераспределено». */
  assignedAt: string | null;
  /** `{domain}_deadline_at` — null until the invoice is assigned. */
  deadlineAt: string | null;
  completedAt: string | null;
  assignedUserId: string | null;
  assignedUser?: UserAvatarChipUser;
  itemCount: number;
  /** Deal sum from the parent quote. */
  dealSumTotal: number | null;
  dealSumCurrency: string;
  totalWeightKg: number | null;
  totalVolumeM3: number | null;
  packageCount: number | null;
  cargoPlaces: WorkspaceCargoPlace[];
  /**
   * Optional «Комментарий для распределения» captured by МОП in the «Контрольный
   * список» modal. Sourced from `kvota.quotes.sales_checklist.distribution_comment`.
   * Surfaced only on cards still in the «Нераспределено» column — once a user is
   * assigned the hint becomes stale and the card hides it. Null when missing.
   *
   * Marked optional so legacy callers / fixtures that didn't go through
   * `fetchKanbanInvoices` (older tests, optimistic local construction) still
   * type-check; the render path tolerates `undefined` via the same trim guard.
   */
  distributionComment?: string | null;
}

/** Cards bucketed by kanban column — one key per column. */
export type WorkspaceKanbanBoard = Record<
  WorkspaceKanbanColumnKey,
  WorkspaceKanbanCard[]
>;

/**
 * Derive the kanban column an invoice belongs to (REQ-2).
 *
 * - completed:    `{domain}_completed_at IS NOT NULL`
 * - in_progress:  assigned + not completed
 * - unassigned:   no assignee + not completed
 *
 * Callers gate on `procurement_completed_at IS NOT NULL` in the query, so
 * every row reaching here has entered the stage.
 */
export function deriveKanbanColumn(inv: {
  completedAt: string | null;
  assignedUserId: string | null;
}): WorkspaceKanbanColumnKey {
  if (inv.completedAt) return "completed";
  if (inv.assignedUserId) return "in_progress";
  return "unassigned";
}

/**
 * Kanban card visibility (REQ-5/6).
 *
 * - «Нераспределено» / «Завершено» — visible to every domain user.
 * - «В работе» — a member sees only cards assigned to themselves; a head
 *   (`head_of_*` / admin / top_manager) sees all.
 */
export function isCardVisibleToUser(
  column: WorkspaceKanbanColumnKey,
  assignedUserId: string | null,
  userId: string,
  isHead: boolean
): boolean {
  if (column !== "in_progress") return true;
  if (isHead) return true;
  return assignedUserId === userId;
}
