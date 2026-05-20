"use client";

import { useDraggable } from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import Link from "next/link";
import { Package, Boxes } from "lucide-react";
// Direct imports (not barrel) — barrel exports server-only queries that break
// "use client" bundling.
import {
  LocationChip,
} from "@/entities/location/ui/location-chip";
import {
  UserAvatarChip,
  type UserAvatarChipUser,
} from "@/entities/user/ui/user-avatar-chip";
import { SlaTimerBadge } from "@/shared/ui/sla-timer-badge";
import { AssigneePickerPopover } from "./assignee-picker-popover";
import { cardKey, type WorkspaceKanbanCard } from "../model/types";

export interface KanbanCardProps {
  card: WorkspaceKanbanCard;
  domain: "logistics" | "customs";
  /** Disables drag while a server action for this card is in flight. */
  pending?: boolean;
  /** Whether the head assignee picker is allowed for this card. */
  canAssign?: boolean;
  teamUsers?: UserAvatarChipUser[];
  /** Controlled open state of the assignee picker (head flow). */
  assignOpen?: boolean;
  onAssignOpenChange?: (open: boolean) => void;
  onAssigned?: () => void;
  onAssignCancelled?: () => void;
}

const EM_DASH = "—";
const NBSP = " ";

const sumFormatter = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
});

function formatDealSum(total: number | null, currency: string): string {
  if (total == null) return EM_DASH;
  return `${sumFormatter.format(total)}${NBSP}${currency}`;
}

function formatDims(
  lengthMm: number | null,
  widthMm: number | null,
  heightMm: number | null,
): string | null {
  if (lengthMm == null && widthMm == null && heightMm == null) return null;
  const part = (mm: number | null) => (mm == null ? "?" : Math.round(mm));
  return `${part(lengthMm)}×${part(widthMm)}×${part(heightMm)}${NBSP}мм`;
}

function pluralPlaces(n: number): string {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return "мест";
  if (mod10 === 1) return "место";
  if (mod10 >= 2 && mod10 <= 4) return "места";
  return "мест";
}

/**
 * Draggable invoice card for the logistics / customs kanban board (REQ-10).
 *
 * Shows: route (Откуда→Куда), IDN + customer, stage timer (running even when
 * unassigned), deal sum + item count, and cargo places with their dimensions
 * and weight. The IDN is a link to the quote detail — its pointer events are
 * isolated so dnd-kit does not start a drag.
 */
export function KanbanCard({
  card,
  domain,
  pending = false,
  canAssign = false,
  teamUsers,
  assignOpen = false,
  onAssignOpenChange,
  onAssigned,
  onAssignCancelled,
}: KanbanCardProps) {
  const key = cardKey(card);
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: key,
      data: { card },
      disabled: pending,
    });

  const style = {
    transform: CSS.Translate.toString(transform),
    opacity: isDragging ? 0.5 : pending ? 0.7 : 1,
  };

  const cargoCount = card.cargoPlaces.length;
  const showAssignee = card.assignedUser != null;
  // Distribution hint is meaningful only while the card sits in
  // «Нераспределено» (no assignee + not completed). Once a МОЛ / МОТ has
  // picked the card up, the hint is stale and would clutter the «В работе»
  // view; the context panel on the quote/deal page keeps showing it as
  // historical reference for the entire pipeline.
  //
  // Defensive trim: while `fetchKanbanInvoices` normalizes whitespace-only
  // values to null, the card may be re-rendered from a parent component
  // that didn't go through the fetcher (optimistic updates, etc.).
  const trimmedDistributionComment = card.distributionComment?.trim() ?? "";
  const showDistributionComment =
    trimmedDistributionComment.length > 0 &&
    card.assignedUserId == null &&
    card.completedAt == null;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      className={[
        "cursor-grab select-none rounded-md border border-border bg-background p-3 text-sm shadow-sm",
        "hover:border-ring focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        isDragging ? "cursor-grabbing shadow-lg" : "",
        pending ? "pointer-events-none" : "",
      ].join(" ")}
      role="article"
      aria-label={`Инвойс ${card.idn}`}
    >
      {/* Header: IDN link + stage timer */}
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/quotes/${card.quoteId}?invoice=${card.id}`}
          className="min-w-0 truncate font-medium text-foreground hover:underline tabular-nums"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {card.idn}
        </Link>
        <SlaTimerBadge
          assignedAt={card.assignedAt ?? card.stageEnteredAt}
          deadlineAt={card.deadlineAt}
          completedAt={card.completedAt}
        />
      </div>

      {/* Customer */}
      <p className="mt-1 truncate text-xs text-muted-foreground">
        {card.customerName}
      </p>

      {/* Route */}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <LocationChip location={card.pickupLocation} size="sm" />
        <span className="text-xs text-muted-foreground" aria-hidden>
          →
        </span>
        <LocationChip location={card.deliveryLocation} size="sm" />
      </div>

      {/* Deal sum + item count */}
      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          <span className="font-medium text-foreground">
            {formatDealSum(card.dealSumTotal, card.dealSumCurrency)}
          </span>
        </span>
        <span className="inline-flex items-center gap-1 tabular-nums">
          <Package size={11} aria-hidden />
          {card.itemCount} поз.
        </span>
      </div>

      {/* Cargo places */}
      <div className="mt-2 rounded-sm bg-muted/50 p-2 text-xs">
        <div className="flex items-center gap-1 font-medium text-foreground">
          <Boxes size={12} aria-hidden />
          {cargoCount > 0
            ? `${cargoCount} ${pluralPlaces(cargoCount)}`
            : "Грузовые места не указаны"}
        </div>
        {cargoCount > 0 && (
          <ul className="mt-1 space-y-0.5 text-muted-foreground">
            {card.cargoPlaces.map((cp) => {
              const dims = formatDims(cp.lengthMm, cp.widthMm, cp.heightMm);
              return (
                <li key={cp.position} className="tabular-nums">
                  #{cp.position}
                  {dims ? ` · ${dims}` : ""}
                  {cp.weightKg != null
                    ? ` · ${cp.weightKg}${NBSP}кг`
                    : ""}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Distribution hint from МОП — visible only in «Нераспределено». */}
      {showDistributionComment && (
        <div
          data-testid="kanban-card-distribution-comment"
          className="mt-2 rounded-sm border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs italic text-amber-900 whitespace-pre-wrap break-words"
          title="Комментарий для распределения"
        >
          {trimmedDistributionComment}
        </div>
      )}

      {/* Assignee (in-progress / completed cards) */}
      {showAssignee && card.assignedUser && (
        <div className="mt-2">
          <UserAvatarChip user={card.assignedUser} size="xs" />
        </div>
      )}

      {/* Head assignee picker */}
      {canAssign && teamUsers && (
        <AssigneePickerPopover
          card={card}
          domain={domain}
          teamUsers={teamUsers}
          open={assignOpen}
          onOpenChange={(open) => onAssignOpenChange?.(open)}
          onAssigned={() => onAssigned?.()}
          onCancelled={() => onAssignCancelled?.()}
        />
      )}
    </div>
  );
}
