"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { toast } from "sonner";
import type { UserAvatarChipUser } from "@/entities/user/ui/user-avatar-chip";
import { preserveScroll } from "@/shared/lib/scroll";
import { KanbanCard } from "./kanban-card";
import { selfPullInvoice } from "../server-actions";
import {
  DEFAULT_KANBAN_COLUMNS,
  cardKey,
  isKanbanColumnKey,
  resolveDragAction,
  type ColumnConfig,
  type WorkspaceKanbanBoard,
  type WorkspaceKanbanCard,
  type WorkspaceKanbanColumnKey,
} from "../model/types";

export interface KanbanBoardProps {
  domain: "logistics" | "customs";
  initialBoard: WorkspaceKanbanBoard;
  /** True for head roles (admin/top_manager included) — enables the picker. */
  isHead: boolean;
  /** Team roster for the head assignee picker; empty for members. */
  teamUsers: UserAvatarChipUser[];
  /**
   * Left-to-right column layout. Defaults to the logistics/customs layout
   * (`DEFAULT_KANBAN_COLUMNS`) so existing callers are unaffected — the prop
   * is the parameterization seam introduced in control-spec-workspace task 4.1.
   */
  columns?: ColumnConfig<WorkspaceKanbanColumnKey>[];
}

/** Which column a card currently sits in within the local board state. */
function findColumn(
  board: WorkspaceKanbanBoard,
  id: string,
  columns: ColumnConfig<WorkspaceKanbanColumnKey>[],
): WorkspaceKanbanColumnKey | null {
  for (const col of columns) {
    if (board[col.key].some((c) => c.id === id)) return col.key;
  }
  return null;
}

/**
 * Three-column kanban board with drag-and-drop (REQ-2, REQ-7/8/9).
 *
 * Drag semantics:
 *   - Member, Нераспределено → В работе: `selfPullInvoice` — self-assign.
 *   - Member, В работе → anywhere: blocked (toast).
 *   - Head, Нераспределено / В работе → В работе: opens the assignee picker.
 *   - Завершено is NOT a drop target — cards land there automatically when
 *     the stage-completion flow stamps `{domain}_completed_at`.
 *
 * Optimistic move + rollback on failure (Risk 5 — another member may have
 * pulled the card first), mirroring the procurement kanban `commitTransition`.
 */
export function KanbanBoard({
  domain,
  initialBoard,
  isHead,
  teamUsers,
  columns = DEFAULT_KANBAN_COLUMNS,
}: KanbanBoardProps) {
  const router = useRouter();
  const [board, setBoard] = useState<WorkspaceKanbanBoard>(initialBoard);
  const [activeCard, setActiveCard] = useState<WorkspaceKanbanCard | null>(
    null,
  );
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  // Card whose head assignee picker is open (only one at a time).
  const [openAssignId, setOpenAssignId] = useState<string | null>(null);
  // When a head drag opens the picker, the optimistic move is held here so it
  // can be rolled back if the head cancels without assigning.
  const [pendingHeadMove, setPendingHeadMove] = useState<{
    cardId: string;
    from: WorkspaceKanbanColumnKey;
  } | null>(null);

  // Re-seed local state when the server pushes fresh data (router.refresh()).
  useEffect(() => {
    setBoard(initialBoard);
  }, [initialBoard]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  function markPending(id: string, pending: boolean) {
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (pending) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  /** Move a card between columns in local state (optimistic). */
  function moveCard(
    cardId: string,
    from: WorkspaceKanbanColumnKey,
    to: WorkspaceKanbanColumnKey,
  ): void {
    setBoard((prev) => {
      const card = prev[from].find((c) => c.id === cardId);
      if (!card) return prev;
      return {
        ...prev,
        [from]: prev[from].filter((c) => c.id !== cardId),
        [to]: [card, ...prev[to]],
      };
    });
  }

  function handleDragStart(event: DragStartEvent) {
    const card = event.active.data.current?.card as
      | WorkspaceKanbanCard
      | undefined;
    if (card) setActiveCard(card);
  }

  async function commitSelfPull(
    card: WorkspaceKanbanCard,
    from: WorkspaceKanbanColumnKey,
  ) {
    markPending(card.id, true);
    try {
      await selfPullInvoice(card.id, domain);
      toast.success(`${card.idn}: взято в работу`);
      router.refresh();
    } catch (err) {
      // Rollback: move the card back to «Нераспределено».
      moveCard(card.id, "in_progress", from);
      const msg =
        err instanceof Error ? err.message : "Не удалось взять заявку";
      toast.error(msg);
    } finally {
      markPending(card.id, false);
    }
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveCard(null);
    const { active, over } = event;
    if (!over) return;

    const overId = String(over.id);
    if (!isKanbanColumnKey(overId)) return;
    const to: WorkspaceKanbanColumnKey = overId;

    const card = active.data.current?.card as WorkspaceKanbanCard | undefined;
    if (!card) return;
    const from = findColumn(board, card.id, columns);
    if (!from || from === to) return;

    const action = resolveDragAction(from, to, isHead);

    if (action === "self-pull") {
      // Member self-assign — optimistic move + server commit (REQ-7).
      // `moveCard` assigns its result inside the async `setBoard` updater, so
      // it is not available synchronously — use the `card` already in scope.
      moveCard(card.id, from, to);
      void commitSelfPull(card, from);
      return;
    }

    if (action === "open-picker") {
      // Head assign / reassign — optimistic move held until the picker
      // resolves (REQ-8).
      moveCard(card.id, from, to);
      setPendingHeadMove({ cardId: card.id, from });
      setOpenAssignId(card.id);
      return;
    }

    // Blocked drop (member moving out of «В работе», drop into «Завершено»
    // which is auto-only, etc.).
    toast.error(
      to === "completed"
        ? "Завершение происходит автоматически"
        : isHead
          ? "Недопустимый переход"
          : "Можно только брать заявки из «Нераспределено»",
    );
  }

  function handleAssigned() {
    setOpenAssignId(null);
    setPendingHeadMove(null);
    // Testing 2 rows 62/63 — preserve scroll position across the post-
    // assignment refresh. router.refresh() pulls fresh server data; the
    // card then moves columns (e.g. «Нераспределено» → «В работе»)
    // through the `setBoard(initialBoard)` re-seed effect. The intermediate
    // loading state in the parent page can collapse layout briefly,
    // letting the browser reset scrollTop to 0 — heads picking an
    // assignee on a card far below the fold lost their place.
    //
    // Same fix pattern as Testing 2 row 58 (route-constructor template
    // apply): snapshot scrollY, restore via two-rAF chain after the
    // refresh settles.
    void preserveScroll(async () => {
      router.refresh();
    });
  }

  function handleAssignCancelled() {
    setOpenAssignId(null);
    // Roll back the optimistic head move if it was never committed.
    if (pendingHeadMove) {
      moveCard(pendingHeadMove.cardId, "in_progress", pendingHeadMove.from);
      setPendingHeadMove(null);
    }
  }

  return (
    <DndContext
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {columns.map((col) => (
          <KanbanColumn
            key={col.key}
            column={col.key}
            label={col.label}
            domain={domain}
            cards={board[col.key]}
            isHead={isHead}
            teamUsers={teamUsers}
            pendingIds={pendingIds}
            activeFrom={
              activeCard ? findColumn(board, activeCard.id, columns) : null
            }
            openAssignId={openAssignId}
            onAssignOpenChange={(id, open) =>
              setOpenAssignId(open ? id : null)
            }
            onAssigned={handleAssigned}
            onAssignCancelled={handleAssignCancelled}
          />
        ))}
      </div>
      <DragOverlay>
        {activeCard ? (
          <KanbanCard card={activeCard} domain={domain} />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

interface KanbanColumnProps {
  column: WorkspaceKanbanColumnKey;
  label: string;
  domain: "logistics" | "customs";
  cards: WorkspaceKanbanCard[];
  isHead: boolean;
  teamUsers: UserAvatarChipUser[];
  pendingIds: Set<string>;
  activeFrom: WorkspaceKanbanColumnKey | null;
  openAssignId: string | null;
  onAssignOpenChange: (cardId: string, open: boolean) => void;
  onAssigned: () => void;
  onAssignCancelled: () => void;
}

function KanbanColumn({
  column,
  label,
  domain,
  cards,
  isHead,
  teamUsers,
  pendingIds,
  activeFrom,
  openAssignId,
  onAssignOpenChange,
  onAssigned,
  onAssignCancelled,
}: KanbanColumnProps) {
  // «Завершено» is auto-only (REQ-9) — never a droppable target.
  const isDroppable = column !== "completed";
  const { setNodeRef, isOver } = useDroppable({
    id: column,
    disabled: !isDroppable,
  });

  const isValidTarget =
    isDroppable && activeFrom !== null && activeFrom !== column;

  return (
    <div
      ref={setNodeRef}
      className={[
        "flex min-h-[300px] flex-col gap-2 rounded-lg border p-3",
        "bg-muted/40",
        isOver && isValidTarget
          ? "border-primary ring-2 ring-primary/30"
          : "",
      ].join(" ")}
      aria-label={label}
    >
      <header className="flex items-center justify-between pb-1">
        <h2 className="text-sm font-semibold text-foreground">
          {label}
        </h2>
        <span className="rounded-full bg-background px-2 py-0.5 text-xs text-muted-foreground">
          {cards.length}
        </span>
      </header>

      <div className="flex flex-col gap-2">
        {cards.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            Пусто
          </p>
        ) : (
          cards.map((card) => {
            // The head picker is available on active columns only — not on
            // «Завершено» (the assignee is locked once finished).
            const canAssign = isHead && column !== "completed";
            return (
              <KanbanCard
                key={cardKey(card)}
                card={card}
                domain={domain}
                pending={pendingIds.has(card.id)}
                canAssign={canAssign}
                teamUsers={canAssign ? teamUsers : undefined}
                assignOpen={openAssignId === card.id}
                onAssignOpenChange={(open) =>
                  onAssignOpenChange(card.id, open)
                }
                onAssigned={onAssigned}
                onAssignCancelled={onAssignCancelled}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
