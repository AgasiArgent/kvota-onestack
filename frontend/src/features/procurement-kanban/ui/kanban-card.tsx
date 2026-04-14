"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import Link from "next/link";
import { Clock } from "lucide-react";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import { AssignPopover } from "./assign-popover";
import {
  brandCardKey,
  type KanbanBrandCard,
  type KanbanInvoiceSum,
} from "../model/types";

export interface KanbanCardProps {
  card: KanbanBrandCard;
  onClick: (card: KanbanBrandCard) => void;
  pending?: boolean;
  /** Procurement users with workload — required for distributing cards. */
  workload?: ProcurementUserWorkload[];
  /** Org id — required when the assign popover can be opened. */
  orgId?: string;
  /**
   * Whether the inline assign popover is open. Controlled by Board so only
   * one popover is visible at a time.
   */
  assignOpen?: boolean;
  /** Called when the popover requests to open/close. */
  onAssignOpenChange?: (open: boolean) => void;
  /** Optional notice shown inside the popover (set by drag-guard). */
  assignNotice?: string;
  /** Called after a successful assignment. */
  onAssigned?: () => void;
}

const EM_DASH = "—";
const NBSP = "\u00A0";

const numberFormatter = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatInvoiceAmount(sum: KanbanInvoiceSum): string {
  return `${numberFormatter.format(sum.total)}${NBSP}${sum.currency}`;
}

/**
 * Draggable per-(quote, brand) card. Clicking the card body (without dragging)
 * opens the status history panel. The Quote IDN is a link that navigates to
 * the quote detail page at the procurement step; its pointer events are
 * isolated so dnd-kit does not start a drag and the history panel does not
 * open.
 */
export function KanbanCard({
  card,
  onClick,
  pending = false,
  workload,
  orgId,
  assignOpen = false,
  onAssignOpenChange,
  assignNotice,
  onAssigned,
}: KanbanCardProps) {
  const isDistributing = card.procurement_substatus === "distributing";
  const canAssign =
    isDistributing && workload !== undefined && orgId !== undefined;
  const key = brandCardKey(card);
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: key,
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
  const managerText = card.manager_name?.trim() || EM_DASH;
  const procurementText =
    card.procurement_user_names.length > 0
      ? card.procurement_user_names.join(", ")
      : EM_DASH;
  const hasInvoices = card.invoice_sums.length > 0;
  const isUnbranded = card.brand === "";
  const brandLabel = isUnbranded ? "Без бренда" : card.brand;

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
        <div className="flex min-w-0 items-center gap-1.5">
          <Link
            href={`/quotes/${card.quote_id}?step=procurement`}
            className="font-medium text-foreground hover:underline"
            // Stop drag activation and the card-level click that opens history.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
          >
            {card.idn_quote}
          </Link>
          <span
            className={[
              "inline-flex max-w-[12rem] items-center truncate rounded-full bg-muted px-1.5 py-0.5 text-xs",
              isUnbranded
                ? "italic text-muted-foreground opacity-70"
                : "text-foreground",
            ].join(" ")}
            title={brandLabel}
          >
            {brandLabel}
          </span>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          <Clock className="size-3" />
          {card.days_in_state}д
        </span>
      </div>
      {card.customer_name && (
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {card.customer_name}
        </p>
      )}
      <div className="mt-2 space-y-0.5 text-xs text-muted-foreground">
        <p className="truncate">
          <span className="font-medium">МОП:</span> {managerText}
        </p>
        <p className="truncate">
          <span className="font-medium">МОЗ:</span> {procurementText}
        </p>
        {hasInvoices ? (
          card.invoice_sums.map((sum) => (
            <p key={sum.invoice_number} className="truncate">
              <span className="font-medium">{sum.invoice_number}:</span>{" "}
              {formatInvoiceAmount(sum)}
            </p>
          ))
        ) : (
          <p className="truncate">
            <span className="font-medium">Сумма:</span> {EM_DASH}
          </p>
        )}
      </div>
      {canAssign && workload && orgId && (
        <AssignPopover
          card={card}
          users={workload}
          orgId={orgId}
          open={assignOpen}
          onOpenChange={(next) => onAssignOpenChange?.(next)}
          notice={assignNotice}
          onAssigned={() => {
            onAssignOpenChange?.(false);
            onAssigned?.();
          }}
        />
      )}
    </div>
  );
}
