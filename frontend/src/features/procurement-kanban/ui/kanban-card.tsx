"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import Link from "next/link";
import { Clock } from "lucide-react";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import { AssignPopover } from "./assign-popover";
import { ReassignPopover } from "./reassign-popover";
import {
  brandCardKey,
  type KanbanBrandCard,
  type KanbanInvoiceSum,
  type KanbanPauseLog,
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
  /**
   * Whether the current user can reassign (head_of_procurement / admin /
   * procurement_senior). Testing 2 row 75. Drives the «Переназначить»
   * button on non-distributing cards.
   */
  canReassign?: boolean;
  /** Controlled open state of the reassign popover. */
  reassignOpen?: boolean;
  /** Called when the reassign popover requests to open/close. */
  onReassignOpenChange?: (open: boolean) => void;
  /** Called after a successful reassignment. */
  onReassigned?: () => void;
  /**
   * Testing 2 row 74 — click handler for the inline pause reason on «На
   * паузе» cards. Opens the full pause-history drawer. Optional because
   * non-paused cards don't use it.
   */
  onPauseHistoryClick?: (card: KanbanBrandCard) => void;
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

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "2-digit",
  timeZone: "Europe/Moscow",
});

/**
 * Testing 2 row 67 — substate-transition timestamp on the kanban card.
 * Driven by `quote_brand_substates.updated_at` (latest transition for this
 * slice), formatted in MSK to keep server (UTC) and client (any TZ) in
 * agreement.
 */
function formatDistributionTimestamp(iso: string): string | null {
  const parsed = Date.parse(iso);
  if (Number.isNaN(parsed)) return null;
  return dateFormatter.format(new Date(parsed));
}

/** Max characters before truncating the inline pause reason. */
export const PAUSE_INLINE_REASON_MAX = 80;

/**
 * Format the inline pause label rendered on «На паузе» cards.
 * Shape: «На паузе с ДД.ММ.ГГ: <truncated reason> (<author>)».
 * Exported for unit tests.
 */
export function formatPauseInline(log: KanbanPauseLog): string {
  const date = formatDistributionTimestamp(log.paused_at) ?? log.paused_at;
  const reasonRaw = log.reason || "";
  const reason =
    reasonRaw.length > PAUSE_INLINE_REASON_MAX
      ? `${reasonRaw.slice(0, PAUSE_INLINE_REASON_MAX - 1).trimEnd()}…`
      : reasonRaw;
  const author = log.paused_by_name?.trim();
  const authorSuffix = author ? ` (${author})` : "";
  return `На паузе с ${date}: ${reason}${authorSuffix}`;
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
  canReassign = false,
  reassignOpen = false,
  onReassignOpenChange,
  onReassigned,
  onPauseHistoryClick,
}: KanbanCardProps) {
  const isDistributing = card.procurement_substatus === "distributing";
  const canAssign =
    isDistributing && workload !== undefined && orgId !== undefined;
  // Reassign is only meaningful past the «Распределение» column AND when the
  // card actually has someone assigned. Head can reassign even an empty
  // slice, but the picker shows «Текущий исполнитель: —», which is fine.
  const showReassign =
    canReassign && !isDistributing && workload !== undefined;
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
  // Testing 2 row 67 — surface tender flag + last-transition timestamp as
  // visible card fields, plus the distribution comment promoted from
  // tooltip-only to a dedicated row so МОЗ doesn't have to hover.
  const isTender = Boolean(card.tender_type);
  const distributionTimestamp = card.updated_at
    ? formatDistributionTimestamp(card.updated_at)
    : null;
  // Testing 2 row 74 — paused cards show the latest pause reason inline so
  // users don't have to open the history drawer. Click on the inline row
  // opens the full pause-history panel.
  const isPaused = card.procurement_substatus === "paused";
  const pauseLog = isPaused ? card.pause_log : null;
  const pauseInline = pauseLog ? formatPauseInline(pauseLog) : null;

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
          {isTender && (
            <span
              className="inline-flex items-center rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800"
              title={`Тендер${card.tender_type && card.tender_type !== "tender" ? ` (${card.tender_type})` : ""}`}
            >
              Тендер
            </span>
          )}
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
        {distributionTimestamp && (
          <p className="truncate">
            <span className="font-medium">Этап с:</span> {distributionTimestamp}
          </p>
        )}
        {pauseInline ? (
          <button
            type="button"
            // Prevent dnd-kit drag activation AND the card-level click that
            // opens the substatus history; this opens the pause-history
            // drawer instead.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              onPauseHistoryClick?.(card);
            }}
            className="line-clamp-2 truncate text-left italic text-muted-foreground hover:text-foreground hover:underline"
            title={pauseLog?.reason || pauseInline}
          >
            {pauseInline}
          </button>
        ) : (
          reason && (
            <p
              className="line-clamp-2 italic text-muted-foreground"
              title={reason}
            >
              <span className="font-medium not-italic">Коммент:</span> {reason}
            </p>
          )
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
      {showReassign && workload && (
        <ReassignPopover
          card={card}
          users={workload}
          open={reassignOpen}
          onOpenChange={(next) => onReassignOpenChange?.(next)}
          onReassigned={() => {
            onReassignOpenChange?.(false);
            onReassigned?.();
          }}
        />
      )}
    </div>
  );
}
