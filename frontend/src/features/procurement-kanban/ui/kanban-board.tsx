"use client";

import { useState } from "react";
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
import { KanbanCard } from "./kanban-card";
import { SubstatusReasonDialog } from "./substatus-reason-dialog";
import { StatusHistoryPanel } from "./status-history-panel";
import {
  PROCUREMENT_SUBSTATUSES,
  SUBSTATUS_LABELS_RU,
  isBackwardTransition,
  isValidTransition,
  isProcurementSubstatus,
  type ProcurementSubstatus,
} from "@/shared/lib/workflow-substates";
import { transitionSubstatus } from "@/entities/quote/mutations";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import { countUnassignedItems } from "../lib/count-unassigned";
import {
  brandCardKey,
  type KanbanColumns,
  type KanbanBrandCard,
} from "../model/types";

export interface KanbanBoardProps {
  initialColumns: KanbanColumns;
  workload: ProcurementUserWorkload[];
  orgId: string;
}

const FORCED_ASSIGN_NOTICE =
  "Не все позиции назначены. Назначьте оставшиеся.";

interface PendingBackwardMove {
  card: KanbanBrandCard;
  from: ProcurementSubstatus;
  to: ProcurementSubstatus;
}

/**
 * Four-column kanban board with drag-and-drop transitions.
 *
 * Each card represents a single (quote, brand) slice. The same quote can
 * appear in multiple columns simultaneously if its brands are at different
 * substatuses — the kanban axis is (quote_id, brand), not quote_id alone.
 *
 * Optimistic update flow:
 *   1. Drop event → move card locally immediately.
 *   2. Forward transition → fire-and-forget POST, toast on error + rollback.
 *   3. Backward transition → open reason dialog; submit or rollback on cancel.
 *
 * Invalid drops are rejected visually at the column (useDroppable disabled)
 * but also defensively here so a malformed drop does nothing.
 */
export function KanbanBoard({
  initialColumns,
  workload,
  orgId,
}: KanbanBoardProps) {
  const router = useRouter();
  const [columns, setColumns] = useState<KanbanColumns>(initialColumns);
  const [activeCard, setActiveCard] = useState<KanbanBrandCard | null>(null);
  const [pendingBackward, setPendingBackward] =
    useState<PendingBackwardMove | null>(null);
  const [submittingReason, setSubmittingReason] = useState(false);
  const [historyQuote, setHistoryQuote] = useState<KanbanBrandCard | null>(
    null
  );
  const [pendingKeys, setPendingKeys] = useState<Set<string>>(new Set());
  // Which card (if any) has its assign popover open. Only one at a time.
  const [openAssignCardKey, setOpenAssignCardKey] = useState<string | null>(
    null
  );
  // If non-null, the drag-guard forced this card's popover open with a notice.
  const [forcedAssignCardKey, setForcedAssignCardKey] = useState<string | null>(
    null
  );

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  );

  function moveCard(
    cardKey: string,
    from: ProcurementSubstatus,
    to: ProcurementSubstatus,
    nextSubstatus?: ProcurementSubstatus
  ): KanbanBrandCard | null {
    let moved: KanbanBrandCard | null = null;
    setColumns((prev) => {
      const fromCol = prev[from];
      const card = fromCol.find((c) => brandCardKey(c) === cardKey);
      if (!card) return prev;
      moved = card;
      const updatedCard: KanbanBrandCard = {
        ...card,
        procurement_substatus: nextSubstatus ?? to,
        days_in_state: 0,
      };
      return {
        ...prev,
        [from]: fromCol.filter((c) => brandCardKey(c) !== cardKey),
        [to]: [updatedCard, ...prev[to]],
      };
    });
    return moved;
  }

  function markPending(key: string, pending: boolean) {
    setPendingKeys((prev) => {
      const next = new Set(prev);
      if (pending) next.add(key);
      else next.delete(key);
      return next;
    });
  }

  async function commitTransition(
    card: KanbanBrandCard,
    from: ProcurementSubstatus,
    to: ProcurementSubstatus,
    reason?: string
  ) {
    const key = brandCardKey(card);
    markPending(key, true);
    try {
      await transitionSubstatus(card.quote_id, card.brand, to, reason);
      toast.success(
        `${card.idn_quote}: ${SUBSTATUS_LABELS_RU[from]} → ${SUBSTATUS_LABELS_RU[to]}`
      );
    } catch (err) {
      // Rollback: move the card back to its original column.
      moveCard(key, to, from, from);
      const msg = err instanceof Error ? err.message : "Не удалось сохранить";
      toast.error(msg);
    } finally {
      markPending(key, false);
    }
  }

  function handleDragStart(event: DragStartEvent) {
    const card = event.active.data.current?.card as
      | KanbanBrandCard
      | undefined;
    if (card) setActiveCard(card);
  }

  async function handleDragEnd(event: DragEndEvent) {
    setActiveCard(null);
    const { active, over } = event;
    if (!over) return;

    const overId = String(over.id);
    if (!isProcurementSubstatus(overId)) return;
    const to: ProcurementSubstatus = overId;

    const from = active.data.current?.fromSubstatus as
      | ProcurementSubstatus
      | undefined;
    const card = active.data.current?.card as KanbanBrandCard | undefined;
    if (!from || !card) return;
    if (from === to) return; // no-op
    if (!isValidTransition(from, to)) {
      toast.error("Недопустимый переход");
      return;
    }

    // Guard: moving out of "distributing" requires all items to be assigned.
    // We check before the optimistic move so no rollback is needed on rejection.
    if (from === "distributing" && to === "searching_supplier") {
      try {
        const unassigned = await countUnassignedItems(
          card.quote_id,
          card.brand
        );
        if (unassigned > 0) {
          toast.error("Не все позиции назначены");
          const key = brandCardKey(card);
          setForcedAssignCardKey(key);
          setOpenAssignCardKey(key);
          return;
        }
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Не удалось проверить позиции";
        toast.error(msg);
        return;
      }
    }

    // Optimistic move first so the UI feels instant.
    moveCard(brandCardKey(card), from, to);

    if (isBackwardTransition(from, to)) {
      setPendingBackward({ card, from, to });
    } else {
      void commitTransition(card, from, to);
    }
  }

  async function handleReasonConfirm(reason: string) {
    if (!pendingBackward) return;
    setSubmittingReason(true);
    const { card, from, to } = pendingBackward;
    try {
      await commitTransition(card, from, to, reason);
      setPendingBackward(null);
    } finally {
      setSubmittingReason(false);
    }
  }

  function handleReasonCancel() {
    if (!pendingBackward) return;
    const { card, from, to } = pendingBackward;
    // Roll back the optimistic move.
    moveCard(brandCardKey(card), to, from, from);
    setPendingBackward(null);
  }

  return (
    <>
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {PROCUREMENT_SUBSTATUSES.map((sub) => (
            <KanbanColumn
              key={sub}
              substatus={sub}
              cards={columns[sub]}
              fromActive={
                activeCard
                  ? (activeCard.procurement_substatus as ProcurementSubstatus)
                  : null
              }
              onCardClick={setHistoryQuote}
              pendingKeys={pendingKeys}
              workload={workload}
              orgId={orgId}
              openAssignCardKey={openAssignCardKey}
              forcedAssignCardKey={forcedAssignCardKey}
              onAssignOpenChange={(key, open) => {
                setOpenAssignCardKey(open ? key : null);
                if (!open) setForcedAssignCardKey(null);
              }}
              onAssigned={() => {
                setOpenAssignCardKey(null);
                setForcedAssignCardKey(null);
                router.refresh();
              }}
            />
          ))}
        </div>
        <DragOverlay>
          {activeCard ? (
            <KanbanCard card={activeCard} onClick={() => {}} />
          ) : null}
        </DragOverlay>
      </DndContext>

      <SubstatusReasonDialog
        open={pendingBackward !== null}
        fromSubstatus={pendingBackward?.from ?? null}
        toSubstatus={pendingBackward?.to ?? null}
        quoteIdn={pendingBackward?.card.idn_quote ?? null}
        brand={pendingBackward?.card.brand ?? null}
        onConfirm={handleReasonConfirm}
        onCancel={handleReasonCancel}
        submitting={submittingReason}
      />

      <StatusHistoryPanel
        open={historyQuote !== null}
        quoteId={historyQuote?.quote_id ?? null}
        quoteIdn={historyQuote?.idn_quote ?? null}
        onClose={() => setHistoryQuote(null)}
      />
    </>
  );
}

interface KanbanColumnProps {
  substatus: ProcurementSubstatus;
  cards: KanbanBrandCard[];
  fromActive: ProcurementSubstatus | null;
  onCardClick: (card: KanbanBrandCard) => void;
  pendingKeys: Set<string>;
  workload: ProcurementUserWorkload[];
  orgId: string;
  openAssignCardKey: string | null;
  forcedAssignCardKey: string | null;
  onAssignOpenChange: (cardKey: string, open: boolean) => void;
  onAssigned: () => void;
}

function KanbanColumn({
  substatus,
  cards,
  fromActive,
  onCardClick,
  pendingKeys,
  workload,
  orgId,
  openAssignCardKey,
  forcedAssignCardKey,
  onAssignOpenChange,
  onAssigned,
}: KanbanColumnProps) {
  const isValidTarget =
    fromActive !== null &&
    fromActive !== substatus &&
    isValidTransition(fromActive, substatus);
  const isDisabledTarget =
    fromActive !== null && fromActive !== substatus && !isValidTarget;

  // Keep the droppable enabled even when the target is visually disabled —
  // the drop still reaches handleDragEnd, which emits the "Недопустимый
  // переход" toast + rolls back. Silent rejection is worse UX.
  const { setNodeRef, isOver } = useDroppable({ id: substatus });

  return (
    <div
      ref={setNodeRef}
      className={[
        "flex min-h-[300px] flex-col gap-2 rounded-lg border p-3",
        "bg-muted/40",
        isOver && isValidTarget ? "border-primary ring-2 ring-primary/30" : "",
        isDisabledTarget ? "opacity-50" : "",
      ].join(" ")}
      aria-label={SUBSTATUS_LABELS_RU[substatus]}
    >
      <header className="flex items-center justify-between pb-1">
        <h2 className="text-sm font-semibold text-foreground">
          {SUBSTATUS_LABELS_RU[substatus]}
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
            const key = brandCardKey(card);
            const isAssignOpen = openAssignCardKey === key;
            const isForced = forcedAssignCardKey === key;
            return (
              <KanbanCard
                key={key}
                card={card}
                onClick={onCardClick}
                pending={pendingKeys.has(key)}
                workload={workload}
                orgId={orgId}
                assignOpen={isAssignOpen}
                onAssignOpenChange={(open) => onAssignOpenChange(key, open)}
                assignNotice={isForced ? FORCED_ASSIGN_NOTICE : undefined}
                onAssigned={onAssigned}
              />
            );
          })
        )}
      </div>
    </div>
  );
}
