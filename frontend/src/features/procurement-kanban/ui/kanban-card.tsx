"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Clock } from "lucide-react";
import type { KanbanQuoteCard } from "../model/types";

export interface KanbanCardProps {
  card: KanbanQuoteCard;
  onClick: (card: KanbanQuoteCard) => void;
  pending?: boolean;
}

/**
 * Draggable quote card. Clicking it (without dragging) opens the status
 * history panel. dnd-kit's activation constraint lets us distinguish a click
 * from a drag by requiring 4px of movement to start a drag.
 */
export function KanbanCard({ card, onClick, pending = false }: KanbanCardProps) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: card.id,
      data: {
        fromSubstatus: card.procurement_substatus,
        card,
      },
      disabled: pending,
    });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : pending ? 0.7 : 1,
  };

  const reason = card.latest_reason?.trim();

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={(e) => {
        // Prevent click after drag (dnd-kit suppresses drag but native click fires).
        if (isDragging) return;
        e.stopPropagation();
        onClick(card);
      }}
      className={[
        "cursor-grab select-none rounded-md border border-border bg-background p-3 text-sm shadow-sm",
        "hover:border-ring focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isDragging ? "cursor-grabbing shadow-lg" : "",
        pending ? "pointer-events-none" : "",
      ].join(" ")}
      title={reason || undefined}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-foreground">{card.idn_quote}</span>
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          <Clock className="size-3" />
          {card.days_in_state}д
        </span>
      </div>
      {card.customer_name && (
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {card.customer_name}
        </p>
      )}
    </div>
  );
}
