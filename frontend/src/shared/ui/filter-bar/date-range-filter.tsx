"use client";

import { useState } from "react";
import { Calendar, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface DateRangeFilterProps {
  /** Trigger label (e.g., "Дата входа в этап"). */
  label: string;
  /** Current `from` value in YYYY-MM-DD format (or null). */
  from: string | null;
  /** Current `to` value in YYYY-MM-DD format (or null). */
  to: string | null;
  /** Commits both endpoints; either may be null. */
  onChange: (from: string | null, to: string | null) => void;
  /** Tailwind width class for the popover content (default: "w-72"). */
  popoverWidthClass?: string;
}

const RU_DATE_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

/** YYYY-MM-DD → DD.MM.YYYY. Returns "" on invalid input. */
function formatRu(iso: string | null): string {
  if (!iso) return "";
  const parsed = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return "";
  return RU_DATE_FORMATTER.format(parsed);
}

function buildTriggerLabel(
  base: string,
  from: string | null,
  to: string | null
): string {
  if (!from && !to) return base;
  const fromRu = formatRu(from);
  const toRu = formatRu(to);
  if (fromRu && toRu) return `${base}: ${fromRu} — ${toRu}`;
  if (fromRu) return `${base}: с ${fromRu}`;
  if (toRu) return `${base}: до ${toRu}`;
  return base;
}

/**
 * Date-range filter for the kanban filter bar.
 *
 * Uses two native `<input type="date">` controls inside a popover — works
 * across browsers without pulling in a calendar dependency. The committed
 * `from` / `to` strings are ISO YYYY-MM-DD; the trigger label renders them
 * in Russian DD.MM.YYYY format.
 *
 * Either endpoint can be cleared independently; clearing both removes the
 * filter from the URL. Apply commits both at once; Reset clears both.
 */
export function DateRangeFilter({
  label,
  from,
  to,
  onChange,
  popoverWidthClass = "w-72",
}: DateRangeFilterProps) {
  const [open, setOpen] = useState(false);
  const [localFrom, setLocalFrom] = useState<string>(from ?? "");
  const [localTo, setLocalTo] = useState<string>(to ?? "");

  // Re-sync local state on every open transition. Driven by the popover's
  // own onOpenChange callback rather than a useEffect — avoids the
  // react-hooks/set-state-in-effect lint and the cascading re-render it
  // warns about.
  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) {
      setLocalFrom(from ?? "");
      setLocalTo(to ?? "");
    }
  }

  function apply() {
    onChange(
      localFrom.length > 0 ? localFrom : null,
      localTo.length > 0 ? localTo : null
    );
    setOpen(false);
  }

  function reset() {
    setLocalFrom("");
    setLocalTo("");
    onChange(null, null);
    setOpen(false);
  }

  const isActive = !!from || !!to;
  const triggerLabel = buildTriggerLabel(label, from, to);

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Фильтр: ${label}`}
            className={cn(
              "inline-flex h-8 min-w-[8rem] max-w-[20rem] items-center justify-between gap-1.5 rounded-lg border bg-background px-2.5 py-1 text-sm transition-colors",
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
                  onPointerDown={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    reset();
                  }}
                  className="inline-flex cursor-pointer items-center justify-center rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X size={12} />
                </span>
              )}
              <Calendar size={14} className="text-muted-foreground/60" />
            </span>
          </button>
        }
      />
      <PopoverContent className={cn(popoverWidthClass, "p-3")} side="bottom" align="start">
        <div className="space-y-3">
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              С
            </label>
            <Input
              type="date"
              value={localFrom}
              onChange={(e) => setLocalFrom(e.target.value)}
              className="h-8 text-sm"
              aria-label={`${label}: с`}
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">
              По
            </label>
            <Input
              type="date"
              value={localTo}
              min={localFrom || undefined}
              onChange={(e) => setLocalTo(e.target.value)}
              className="h-8 text-sm"
              aria-label={`${label}: по`}
            />
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              variant="ghost"
              size="xs"
              className="flex-1"
              onClick={reset}
              disabled={!isActive && !localFrom && !localTo}
            >
              Сбросить
            </Button>
            <Button
              variant="default"
              size="xs"
              className="flex-1"
              onClick={apply}
            >
              Применить
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
