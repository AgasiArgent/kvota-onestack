"use client";

import { useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";

import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface SingleSelectOption {
  value: string;
  label: string;
}

export interface SingleSelectFilterProps {
  /** Trigger label (e.g., "Срочность", "На этапе > N дней"). */
  label: string;
  /** Available options. */
  options: readonly SingleSelectOption[];
  /** Currently selected value, or null. */
  value: string | null;
  /** Commit a new value or clear (null). */
  onChange: (value: string | null) => void;
  /** Tailwind width class (default: "w-56"). */
  popoverWidthClass?: string;
}

/**
 * Single-select dropdown for the filter bar (Срочность, «На этапе > N дней»).
 *
 * Used for buckets that are mutually exclusive — picking one replaces any
 * previous pick. Default state shows just the label as a placeholder; an
 * active pick swaps the trigger to `<label>: <picked label>` plus an inline
 * X clear affordance.
 *
 * Commits immediately on click (no Apply button) — selections are URL-backed
 * and the consuming kanban re-filters live.
 */
export function SingleSelectFilter({
  label,
  options,
  value,
  onChange,
  popoverWidthClass = "w-56",
}: SingleSelectFilterProps) {
  const [open, setOpen] = useState(false);

  const selected = options.find((o) => o.value === value) ?? null;
  const triggerLabel = selected ? `${label}: ${selected.label}` : label;
  const isActive = selected != null;

  function handleSelect(next: string) {
    onChange(next === value ? null : next);
    setOpen(false);
  }

  function handleClear(e: React.PointerEvent<HTMLElement>) {
    e.preventDefault();
    e.stopPropagation();
    onChange(null);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Фильтр: ${label}`}
            className={cn(
              "inline-flex h-8 min-w-[8rem] max-w-[16rem] items-center justify-between gap-1.5 rounded-lg border bg-background px-2.5 py-1 text-sm transition-colors",
              "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              "aria-expanded:bg-muted",
              isActive
                ? "border-accent text-foreground"
                : "border-input text-muted-foreground"
            )}
          >
            <span className="truncate">{triggerLabel}</span>
            <span className="flex shrink-0 items-center gap-1">
              {isActive && (
                <span
                  role="button"
                  tabIndex={-1}
                  aria-label="Очистить"
                  onPointerDown={handleClear}
                  className="inline-flex cursor-pointer items-center justify-center rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X size={12} />
                </span>
              )}
              <ChevronDown size={14} className="text-muted-foreground/60" />
            </span>
          </button>
        }
      />
      <PopoverContent
        className={cn(popoverWidthClass, "p-0")}
        side="bottom"
        align="start"
      >
        <div className="flex flex-col py-1">
          {options.map((option) => {
            const isSelected = option.value === value;
            return (
              <button
                type="button"
                key={option.value}
                onClick={() => handleSelect(option.value)}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 text-left text-xs",
                  "hover:bg-muted/50",
                  isSelected && "bg-muted/40"
                )}
              >
                <span className="flex w-3 shrink-0 justify-center text-accent">
                  {isSelected && <Check size={12} />}
                </span>
                <span className="flex-1 truncate text-foreground">
                  {option.label}
                </span>
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
