"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
  value: string;
  label: string;
}

export interface MultiSelectFilterProps {
  /** Trigger label (e.g., "Клиент", "МОЛ"). */
  label: string;
  /** Available options to pick from. */
  options: readonly MultiSelectOption[];
  /** Currently committed values (URL-backed). */
  selected: readonly string[];
  /** Commits the new selection set. Called with empty array on full clear. */
  onChange: (values: readonly string[]) => void;
  /** Search input placeholder (default: "Поиск..."). */
  searchPlaceholder?: string;
  /** Message shown when `options` is empty. */
  emptyMessage?: string;
  /** Tailwind width class for the popover content (default: "w-72"). */
  popoverWidthClass?: string;
}

/**
 * Searchable multi-select filter for the kanban filter bar.
 *
 * Per the project-wide UI standard, every entity-picker dropdown must be
 * searchable (CLAUDE.md). Mirrors the shadcn/data-table `ColumnFilter`
 * popover style for visual consistency but commits selections immediately
 * (no Apply button) — filters are URL-backed and the kanban board re-renders
 * the filtered set live as each chip toggles.
 *
 * The trigger collapses long selection labels: 1 picked → "Клиент: Coca-Cola";
 * 2+ picked → "Клиент: 3" (count badge). Empty → "Клиент" placeholder.
 */
export function MultiSelectFilter({
  label,
  options,
  selected,
  onChange,
  searchPlaceholder = "Поиск...",
  emptyMessage = "Нет значений",
  popoverWidthClass = "w-72",
}: MultiSelectFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  // Reset search whenever the popover transitions to open. Driven by the
  // popover's own onOpenChange callback rather than an effect — avoids a
  // setState-in-effect cascade (eslint react-hooks/set-state-in-effect).
  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) setSearch("");
  }

  const filteredOptions = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (needle.length === 0) return options;
    return options.filter((o) => o.label.toLowerCase().includes(needle));
  }, [options, search]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);

  function toggle(value: string, checked: boolean) {
    const next = new Set(selectedSet);
    if (checked) next.add(value);
    else next.delete(value);
    onChange(Array.from(next));
  }

  function clearAll() {
    onChange([]);
  }

  const activeCount = selectedSet.size;
  const isActive = activeCount > 0;

  // Trigger label: collapsed for 2+ picks, single-label for 1.
  const triggerLabel = (() => {
    if (activeCount === 0) return label;
    if (activeCount === 1) {
      const only = options.find((o) => o.value === Array.from(selectedSet)[0]);
      return `${label}: ${only?.label ?? "—"}`;
    }
    return `${label}`;
  })();

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
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
              {isActive && activeCount > 1 && (
                <span className="inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-none text-white tabular-nums">
                  {activeCount}
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
        <div className="flex flex-col">
          {/* Search input */}
          <div className="border-b border-border p-2">
            <div className="relative">
              <Search
                className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                size={14}
              />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={searchPlaceholder}
                className="h-7 pl-7 text-xs"
                aria-label={searchPlaceholder}
              />
              {search.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label="Очистить поиск"
                >
                  <X size={12} />
                </button>
              )}
            </div>
          </div>

          {/* Option list */}
          <div className="max-h-56 overflow-y-auto py-1">
            {options.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                {emptyMessage}
              </div>
            ) : filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Ничего не найдено
              </div>
            ) : (
              filteredOptions.map((option) => (
                <label
                  key={option.value}
                  className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted/50"
                >
                  <Checkbox
                    checked={selectedSet.has(option.value)}
                    onCheckedChange={(checked) =>
                      toggle(option.value, checked === true)
                    }
                  />
                  <span className="truncate" title={option.label}>
                    {option.label}
                  </span>
                </label>
              ))
            )}
          </div>

          {/* Footer: clear */}
          {isActive && (
            <div className="flex justify-end border-t border-border p-2">
              <Button
                variant="ghost"
                size="xs"
                onClick={clearAll}
                className="text-xs"
              >
                Сбросить
              </Button>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
