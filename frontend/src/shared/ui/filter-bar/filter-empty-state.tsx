"use client";

import { Filter } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface FilterEmptyStateProps {
  /** Called when the user requests a full reset of all filters. */
  onClearAll: () => void;
}

/**
 * Empty-state surface for a filtered kanban with zero remaining cards.
 *
 * Rendered ONLY when filters are active and the resulting board is empty —
 * not when the unfiltered board is naturally empty (the columns already
 * show "Пусто" in that case).
 */
export function FilterEmptyState({ onClearAll }: FilterEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-muted/40 py-12 text-center">
      <div className="rounded-full bg-background p-3 text-muted-foreground">
        <Filter size={20} />
      </div>
      <p className="max-w-sm text-sm text-muted-foreground">
        Нет карточек по выбранным фильтрам
      </p>
      <Button variant="outline" size="sm" onClick={onClearAll}>
        Сбросить фильтры
      </Button>
    </div>
  );
}
