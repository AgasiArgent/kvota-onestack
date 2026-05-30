import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  STATUS_BADGE_STYLES,
  getStatusLabel,
} from "@/entities/quote/status-labels";
import type { ControlKanbanCard } from "@/entities/workspace-control";
import type { ControlBoardDomain } from "@/entities/workspace-control";

/** The quote-detail step a card opens, per board. */
function stepForDomain(domain: ControlBoardDomain): "control" | "specification" {
  return domain === "calc" ? "control" : "specification";
}

const sumFormatter = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 0,
});

function formatTotal(total: number | null, currency: string): string {
  if (total == null) return "—";
  return `${sumFormatter.format(total)} ${currency}`;
}

export interface ControlCardProps {
  card: ControlKanbanCard;
  domain: ControlBoardDomain;
}

/**
 * A control-board card — clickable (NOT draggable, owner decision). The whole
 * card is a link to the quote-detail tab for the board's gate:
 *   - calc board → /quotes/{id}?step=control
 *   - spec board → /quotes/{id}?step=specification
 *
 * Shows the quote IDN, customer, total (in quote currency), a status badge and
 * the assigned controller's ФИО when one is set.
 */
export function ControlCard({ card, domain }: ControlCardProps) {
  const step = stepForDomain(domain);
  return (
    <Link
      href={`/quotes/${card.quoteId}?step=${step}`}
      className="block rounded-md border border-border bg-background p-3 text-sm shadow-sm hover:border-ring focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`КП ${card.idnQuote}`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="min-w-0 truncate font-medium text-foreground tabular-nums">
          {card.idnQuote}
        </span>
        <Badge
          variant="outline"
          className={STATUS_BADGE_STYLES[card.workflowStatus] ?? ""}
        >
          {getStatusLabel(card.workflowStatus)}
        </Badge>
      </div>

      <p className="mt-1 truncate text-xs text-muted-foreground">
        {card.customerName}
      </p>

      <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-medium text-foreground">
          {formatTotal(card.total, card.currency)}
        </span>
        <span className="truncate">
          {card.controllerName ?? "Не назначен"}
        </span>
      </div>
    </Link>
  );
}
