"use client";

import { type ReactNode } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface FilterBarProps {
  /** Filter trigger buttons (MultiSelect / DateRange / SingleSelect…). */
  children: ReactNode;
  /** When true, shows the "Сбросить все" affordance. */
  hasActiveFilters: boolean;
  /** Wipe all filters back to the unfiltered default. */
  onClearAll: () => void;
  /** Optional extra class on the wrapper. */
  className?: string;
}

/**
 * Horizontal filter bar wrapper. Composes pre-built filter triggers via
 * `children` so each page can pick exactly which filters to expose (logistics
 * skips the brand filter, etc.). Re-flows on narrow viewports and surfaces a
 * single "Сбросить все" pill once any filter is active.
 *
 * Mounted ABOVE the kanban board (toolbar position). Keeps a constrained
 * 8-tap UI as specified in `ux-complexity.md` — no clusters of 10+ controls.
 */
export function FilterBar({
  children,
  hasActiveFilters,
  onClearAll,
  className,
}: FilterBarProps) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-lg border border-border bg-background p-2",
        className
      )}
      role="toolbar"
      aria-label="Фильтры"
    >
      {children}
      {hasActiveFilters && (
        <Button
          variant="ghost"
          size="xs"
          onClick={onClearAll}
          className="ml-auto gap-1 text-muted-foreground"
        >
          <X size={12} />
          Сбросить все
        </Button>
      )}
    </div>
  );
}
