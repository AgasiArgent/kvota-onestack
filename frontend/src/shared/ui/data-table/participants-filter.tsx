"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Filter, Search, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import type { FilterOption } from "./types";

interface ParticipantsFilterProps {
  columnKey: string;
  title: string;
  /** Group key → display label. Sections render in insertion order. */
  groups: Record<string, string>;
  /** All options across groups. Each option.group must match a key in `groups`. */
  options: readonly FilterOption[];
  /** Currently-applied composite values in the form "group:id". */
  selected: readonly string[];
  selectedLogic: "or" | "and";
  onApply: (values: readonly string[], logic: "or" | "and") => void;
  onReset: () => void;
}

/**
 * Grouped multi-select filter popover for "Участники" column.
 *
 * Renders options split into collapsible sections keyed by `option.group`.
 * Client-side search filters across all groups; AND/OR toggle lets the user
 * choose whether matching quotes must contain all selected participants
 * or any of them.
 *
 * Composite value format: `"<groupKey>:<optionId>"`. Callers translate these
 * back into per-role filters in the query layer.
 */
export function ParticipantsFilter({
  title,
  groups,
  options,
  selected,
  selectedLogic,
  onApply,
  onReset,
}: ParticipantsFilterProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [localSelected, setLocalSelected] = useState<Set<string>>(
    () => new Set(selected)
  );
  const [localLogic, setLocalLogic] = useState<"or" | "and">(selectedLogic);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(
    () => new Set()
  );

  useEffect(() => {
    if (open) {
      setLocalSelected(new Set(selected));
      setLocalLogic(selectedLogic);
      setSearch("");
      setCollapsedGroups(new Set());
    }
  }, [open, selected, selectedLogic]);

  // Build grouped option map. Preserves `groups` insertion order.
  const grouped = useMemo(() => {
    const result: { key: string; label: string; items: FilterOption[] }[] = [];
    const index = new Map<string, number>();
    for (const [key, label] of Object.entries(groups)) {
      index.set(key, result.length);
      result.push({ key, label, items: [] });
    }
    for (const opt of options) {
      const groupKey = opt.group ?? "";
      const idx = index.get(groupKey);
      if (idx !== undefined) {
        result[idx].items.push(opt);
      }
    }
    return result;
  }, [groups, options]);

  // Apply search filter within each group
  const filteredGrouped = useMemo(() => {
    if (search.trim().length === 0) return grouped;
    const needle = search.toLowerCase();
    return grouped.map((g) => ({
      ...g,
      items: g.items.filter((o) => o.label.toLowerCase().includes(needle)),
    }));
  }, [grouped, search]);

  function toggleValue(value: string, checked: boolean) {
    setLocalSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(value);
      else next.delete(value);
      return next;
    });
  }

  function toggleGroupCollapse(groupKey: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  }

  function handleApply() {
    onApply(Array.from(localSelected), localLogic);
    setOpen(false);
  }

  function handleReset() {
    setLocalSelected(new Set());
    setLocalLogic("or");
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
      <PopoverContent className="w-72 p-0" side="bottom" align="start">
        <div className="flex flex-col">
          {/* Search + AND/OR toggle */}
          <div className="border-b border-border p-2 space-y-2">
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

            {/* OR / AND segmented toggle */}
            <div className="flex items-center gap-1 text-[11px]">
              <span className="text-muted-foreground mr-1">Логика:</span>
              <button
                type="button"
                onClick={() => setLocalLogic("or")}
                className={cn(
                  "px-2 py-0.5 rounded font-medium transition-colors",
                  localLogic === "or"
                    ? "bg-accent text-white"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                ИЛИ
              </button>
              <button
                type="button"
                onClick={() => setLocalLogic("and")}
                className={cn(
                  "px-2 py-0.5 rounded font-medium transition-colors",
                  localLogic === "and"
                    ? "bg-accent text-white"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                И
              </button>
              <span className="ml-auto text-muted-foreground opacity-70">
                {localLogic === "or" ? "любой совпал" : "все совпали"}
              </span>
            </div>
          </div>

          {/* Grouped option list */}
          <div className="max-h-72 overflow-y-auto py-1">
            {filteredGrouped.every((g) => g.items.length === 0) ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                {search.length > 0 ? "Ничего не найдено" : "Нет значений"}
              </div>
            ) : (
              filteredGrouped.map((group) => {
                if (group.items.length === 0) return null;
                const isCollapsed = collapsedGroups.has(group.key);
                const selectedInGroup = group.items.filter((o) =>
                  localSelected.has(o.value)
                ).length;
                return (
                  <div key={group.key} className="mb-0.5">
                    <button
                      type="button"
                      onClick={() => toggleGroupCollapse(group.key)}
                      className="w-full flex items-center gap-1 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground hover:text-foreground hover:bg-muted/40"
                    >
                      {isCollapsed ? (
                        <ChevronRight size={12} />
                      ) : (
                        <ChevronDown size={12} />
                      )}
                      <span>{group.label}</span>
                      {selectedInGroup > 0 && (
                        <span className="ml-1 rounded-full bg-accent px-1 text-[9px] font-semibold text-white tabular-nums">
                          {selectedInGroup}
                        </span>
                      )}
                      <span className="ml-auto text-[10px] opacity-60">
                        {group.items.length}
                      </span>
                    </button>
                    {!isCollapsed &&
                      group.items.map((option) => (
                        <label
                          key={option.value}
                          className="flex items-center gap-2 px-3 py-1 text-xs hover:bg-muted/50 cursor-pointer"
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
                      ))}
                  </div>
                );
              })
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
