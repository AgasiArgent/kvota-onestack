import type { ColumnConfig } from "@/features/workspace-kanban";
import type {
  ControlBoardDomain,
  ControlKanbanCard,
} from "@/entities/workspace-control";
import { ControlCard } from "./control-card";

export interface ControlBoardProps {
  domain: ControlBoardDomain;
  /** Left-to-right column layout (one column per workflow status). */
  columns: ColumnConfig[];
  /** All cards for this board, bucketed later by their workflowStatus. */
  cards: ControlKanbanCard[];
}

/**
 * Read-only, status-columned control board (control-spec-workspace task 4.3).
 *
 * Unlike the logistics/customs `KanbanBoard`, control cards are clickable, not
 * draggable — controllers open a quote's control tab rather than moving cards
 * between gates (gate transitions happen on the quote page). So this board is a
 * plain column grid that reuses the shared `ColumnConfig` contract for its
 * layout and the `ControlCard` renderer for each card.
 */
export function ControlBoard({ domain, columns, cards }: ControlBoardProps) {
  const byColumn = new Map<string, ControlKanbanCard[]>();
  for (const col of columns) byColumn.set(col.key, []);
  for (const card of cards) {
    const bucket = byColumn.get(card.workflowStatus);
    if (bucket) bucket.push(card);
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {columns.map((col) => {
        const colCards = byColumn.get(col.key) ?? [];
        return (
          <div
            key={col.key}
            className="flex min-h-[300px] flex-col gap-2 rounded-lg border bg-muted/40 p-3"
            aria-label={col.label}
          >
            <header className="flex items-center justify-between pb-1">
              <h2 className="text-sm font-semibold text-foreground">
                {col.label}
              </h2>
              <span className="rounded-full bg-background px-2 py-0.5 text-xs text-muted-foreground">
                {colCards.length}
              </span>
            </header>

            <div className="flex flex-col gap-2">
              {colCards.length === 0 ? (
                <p className="py-8 text-center text-xs text-muted-foreground">
                  Пусто
                </p>
              ) : (
                colCards.map((card) => (
                  <ControlCard
                    key={card.quoteId}
                    card={card}
                    domain={domain}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
