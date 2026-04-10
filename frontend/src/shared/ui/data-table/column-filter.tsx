"use client";

import { useMemo, useState, useEffect } from "react";
import { Search, Filter, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import type { FilterOption } from "./types";

interface ColumnFilterProps {
  columnKey: string;
  title: string;
  options: readonly FilterOption[];
  selected: readonly string[];
  onApply: (values: readonly string[]) => void;
  onReset: () => void;
}

/**
 * Multi-select column filter popover.
 *
 * Renders a trigger button with an active-state indicator plus a popover
 * containing a search input, a scrollable checkbox list of options, and
 * apply/reset controls.
 *
 * Behavior:
 *  - Local selection state in the popover — not committed until Apply.
 *  - Search input filters the visible options client-side.
 *  - "Select all" toggles only the currently visible (post-search) options.
 *  - Reset clears only this column's filter.
 */
export function ColumnFilter({
  title,
  options,
  selected,
  onApply,
  onReset,
}: ColumnFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [localSelected, setLocalSelected] = useState<Set<string>>(
    () => new Set(selected)
  );

  // Re-sync local state whenever the popover opens so it always reflects the
  // current applied filter value (in case it changed while popover was closed).
  useEffect(() => {
    if (open) {
      setLocalSelected(new Set(selected));
      setSearch("");
    }
  }, [open, selected]);

  const filteredOptions = useMemo(() => {
    if (search.trim().length === 0) return options;
    const needle = search.toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(needle));
  }, [options, search]);

  const visibleKeys = useMemo(
    () => new Set(filteredOptions.map((o) => o.value)),
    [filteredOptions]
  );

  /** True when every currently-visible option is selected. */
  const allVisibleSelected =
    filteredOptions.length > 0 &&
    filteredOptions.every((o) => localSelected.has(o.value));

  function toggleValue(value: string, checked: boolean) {
    setLocalSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(value);
      else next.delete(value);
      return next;
    });
  }

  function handleSelectAll() {
    setLocalSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        // Unselect only the currently visible ones — preserve hidden selections.
        for (const key of visibleKeys) next.delete(key);
      } else {
        for (const key of visibleKeys) next.add(key);
      }
      return next;
    });
  }

  function handleApply() {
    onApply(Array.from(localSelected));
    setOpen(false);
  }

  function handleReset() {
    setLocalSelected(new Set());
    onReset();
    setOpen(false);
  }

  const activeCount = selected.length;
  const isActive = activeCount > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Фильтр: ${title}`}
            className={cn(
              "inline-flex items-center justify-center rounded p-0.5 transition-colors",
              isActive
                ? "text-accent hover:text-accent-hover"
                : "text-muted-foreground/60 hover:text-foreground"
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <Filter size={12} />
            {isActive && (
              <span className="ml-0.5 rounded-full bg-accent px-1 text-[10px] font-semibold leading-4 text-white tabular-nums">
                {activeCount}
              </span>
            )}
          </button>
        }
      />
      <PopoverContent className="w-64 p-0" side="bottom" align="start">
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
                placeholder="Поиск..."
                className="h-7 pl-7 text-xs"
                autoFocus
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

          {/* Select all */}
          {options.length > 0 && (
            <label className="flex items-center gap-2 border-b border-border px-3 py-2 text-xs font-medium hover:bg-muted/50 cursor-pointer">
              <Checkbox
                checked={allVisibleSelected}
                onCheckedChange={handleSelectAll}
              />
              <span className="text-muted-foreground">
                {allVisibleSelected ? "Снять все" : "Выбрать все"}
                {search.length > 0 && filteredOptions.length !== options.length && (
                  <span className="ml-1 opacity-60">({filteredOptions.length})</span>
                )}
              </span>
            </label>
          )}

          {/* Option list */}
          <div className="max-h-56 overflow-y-auto py-1">
            {options.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Нет значений для фильтрации
              </div>
            ) : filteredOptions.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Ничего не найдено
              </div>
            ) : (
              filteredOptions.map((option) => (
                <label
                  key={option.value}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={localSelected.has(option.value)}
                    onCheckedChange={(checked) =>
                      toggleValue(option.value, checked === true)
                    }
                  />
                  <span className="truncate" title={option.label}>
                    {option.label}
                  </span>
                </label>
              ))
            )}
          </div>

          {/* Footer actions */}
          <div className="flex gap-2 border-t border-border p-2">
            <Button
              variant="ghost"
              size="xs"
              className="flex-1"
              onClick={handleReset}
              disabled={!isActive && localSelected.size === 0}
            >
              Сбросить
            </Button>
            <Button
              variant="default"
              size="xs"
              className="flex-1"
              onClick={handleApply}
            >
              Применить
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
