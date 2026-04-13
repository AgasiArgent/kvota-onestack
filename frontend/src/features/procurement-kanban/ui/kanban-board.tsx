"use client";

import { useState } from "react";
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
import type { KanbanColumns, KanbanQuoteCard } from "../model/types";

export interface KanbanBoardProps {
  initialColumns: KanbanColumns;
}

interface PendingBackwardMove {
  card: KanbanQuoteCard;
  from: ProcurementSubstatus;
  to: ProcurementSubstatus;
}

/**
 * Four-column kanban board with drag-and-drop transitions.
 *
 * Optimistic update flow:
 *   1. Drop event → move card locally immediately.
 *   2. Forward transition → fire-and-forget POST, toast on error + rollback.
 *   3. Backward transition → open reason dialog; submit or rollback on cancel.
 *
 * Invalid drops are rejected visually at the column (useDroppable disabled)
 * but also defensively here so a malformed drop does nothing.
 */
export function KanbanBoard({ initialColumns }: KanbanBoardProps) {
  const [columns, setColumns] = useState<KanbanColumns>(initialColumns);
  const [activeCard, setActiveCard] = useState<KanbanQuoteCard | null>(null);
  const [pendingBackward, setPendingBackward] =
    useState<PendingBackwardMove | null>(null);
  const [submittingReason, setSubmittingReason] = useState(false);
  const [historyQuote, setHistoryQuote] = useState<KanbanQuoteCard | null>(
    null
  );
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } })
  );

  function moveCard(
    cardId: string,
    from: ProcurementSubstatus,
    to: ProcurementSubstatus,
    nextSubstatus?: ProcurementSubstatus
  ): KanbanQuoteCard | null {
    let moved: KanbanQuoteCard | null = null;
    setColumns((prev) => {
      const fromCol = prev[from];
      const card = fromCol.find((c) => c.id === cardId);
      if (!card) return prev;
      moved = card;
      const updatedCard: KanbanQuoteCard = {
        ...card,
        procurement_substatus: nextSubstatus ?? to,
        days_in_state: 0,
      };
      return {
        ...prev,
        [from]: fromCol.filter((c) => c.id !== cardId),
        [to]: [updatedCard, ...prev[to]],
      };
    });
    return moved;
  }

  function markPending(id: string, pending: boolean) {
    setPendingIds((prev) => {
      const next = new Set(prev);
      if (pending) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function commitTransition(
    card: KanbanQuoteCard,
    from: ProcurementSubstatus,
    to: ProcurementSubstatus,
    reason?: string
  ) {
    markPending(card.id, true);
    try {
      await transitionSubstatus(card.id, to, reason);
      toast.success(
        `${card.idn_quote}: ${SUBSTATUS_LABELS_RU[from]} → ${SUBSTATUS_LABELS_RU[to]}`
      );
    } catch (err) {
      // Rollback: move the card back to its original column.
      moveCard(card.id, to, from, from);
      const msg = err instanceof Error ? err.message : "Не удалось сохранить";
      toast.error(msg);
    } finally {
      markPending(card.id, false);
    }
  }

  function handleDragStart(event: DragStartEvent) {
    const card = event.active.data.current?.card as KanbanQuoteCard | undefined;
    if (card) setActiveCard(card);
  }

  function handleDragEnd(event: DragEndEvent) {
    setActiveCard(null);
    const { active, over } = event;
    if (!over) return;

    const overId = String(over.id);
    if (!isProcurementSubstatus(overId)) return;
    const to: ProcurementSubstatus = overId;

    const from = active.data.current?.fromSubstatus as
      | ProcurementSubstatus
      | undefined;
    const card = active.data.current?.card as KanbanQuoteCard | undefined;
    if (!from || !card) return;
    if (from === to) return; // no-op
    if (!isValidTransition(from, to)) {
      toast.error("Недопустимый переход");
      return;
    }

    // Optimistic move first so the UI feels instant.
    moveCard(card.id, from, to);

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
    moveCard(card.id, to, from, from);
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
              pendingIds={pendingIds}
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
        onConfirm={handleReasonConfirm}
        onCancel={handleReasonCancel}
        submitting={submittingReason}
      />

      <StatusHistoryPanel
        open={historyQuote !== null}
        quoteId={historyQuote?.id ?? null}
        quoteIdn={historyQuote?.idn_quote ?? null}
        onClose={() => setHistoryQuote(null)}
      />
    </>
  );
}

interface KanbanColumnProps {
  substatus: ProcurementSubstatus;
  cards: KanbanQuoteCard[];
  fromActive: ProcurementSubstatus | null;
  onCardClick: (card: KanbanQuoteCard) => void;
  pendingIds: Set<string>;
}

function KanbanColumn({
  substatus,
  cards,
  fromActive,
  onCardClick,
  pendingIds,
}: KanbanColumnProps) {
  const isValidTarget =
    fromActive !== null &&
    fromActive !== substatus &&
    isValidTransition(fromActive, substatus);
  const isDisabledTarget =
    fromActive !== null && fromActive !== substatus && !isValidTarget;

  const { setNodeRef, isOver } = useDroppable({
    id: substatus,
    disabled: fromActive !== null && !isValidTarget,
  });

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
          cards.map((card) => (
            <KanbanCard
              key={card.id}
              card={card}
              onClick={onCardClick}
              pending={pendingIds.has(card.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}
