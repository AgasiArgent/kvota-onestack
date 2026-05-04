"use client";

/**
 * Multi-select list of quote positions used inside the certificate /
 * expense modals (REQ-7 AC#4, REQ-10 AC#2 — sub-component shared across
 * both modals).
 *
 * Renders one row per `quote_items` entry with a checkbox, the position
 * label («№N {name}»), and the pre-derived RUB cost basis (formatted via
 * `formatRub`). A search input filters the list case-insensitively against
 * `name` and `product_code`. A toggle button at the top selects all
 * filtered rows or clears the entire selection.
 *
 * The component is a controlled value: the parent owns `selectedIds[]`
 * and is notified of every change via `onChange(nextIds)`. We never
 * mutate the incoming arrays — `onChange` always receives a fresh array.
 *
 * Test framework constraint: the workspace has no jsdom harness, so this
 * file separates pure helpers (`filterItems`, `toggleId`, `allFilteredSelected`,
 * `nextSelectionAfterToggleAll`) from the React component. The helpers are
 * exported and unit-tested directly; the JSX is exercised via SSR snapshots
 * to assert markup. Click handlers are verified through localhost:3000 per
 * `reference_localhost_browser_test.md`.
 */

import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { QuoteItemForSelect } from "../model/types";
import { formatRub } from "../lib/format-rub";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM.
// ---------------------------------------------------------------------------

/**
 * Case-insensitive substring filter against `name` and `product_code`.
 * Returns the full list for empty / whitespace-only queries.
 */
export function filterItems(
  items: readonly QuoteItemForSelect[],
  query: string,
): readonly QuoteItemForSelect[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return items;
  return items.filter((item) => {
    const name = item.name?.toLowerCase() ?? "";
    const code = item.product_code?.toLowerCase() ?? "";
    return name.includes(needle) || code.includes(needle);
  });
}

/**
 * Toggle a single id in the selection — pure, returns a new array.
 *
 *  - Adds the id if missing.
 *  - Removes the id if present.
 *  - Preserves the order of remaining ids.
 */
export function toggleId(
  selectedIds: readonly string[],
  id: string,
): string[] {
  if (selectedIds.includes(id)) {
    return selectedIds.filter((x) => x !== id);
  }
  return [...selectedIds, id];
}

/**
 * `true` iff every visible (filtered) item is currently selected.
 * `false` for an empty filtered list — there's nothing to select.
 */
export function allFilteredSelected(
  filtered: readonly QuoteItemForSelect[],
  selectedIds: readonly string[],
): boolean {
  if (filtered.length === 0) return false;
  const set = new Set(selectedIds);
  return filtered.every((item) => set.has(item.id));
}

/**
 * Compute the selection after pressing «Выбрать все» / «Снять все».
 *
 * Behavior:
 *  - When all filtered rows are selected → remove all filtered ids
 *    (deselect-all within the visible scope; ids outside the filter are
 *    left untouched so a user search → toggle doesn't wipe their picks).
 *  - Otherwise → add all filtered ids to the existing selection.
 *
 * Pure — never mutates inputs.
 */
export function nextSelectionAfterToggleAll(
  filtered: readonly QuoteItemForSelect[],
  selectedIds: readonly string[],
): string[] {
  if (allFilteredSelected(filtered, selectedIds)) {
    const filteredIdSet = new Set(filtered.map((i) => i.id));
    return selectedIds.filter((id) => !filteredIdSet.has(id));
  }
  const merged = new Set(selectedIds);
  for (const item of filtered) {
    merged.add(item.id);
  }
  return Array.from(merged);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface PositionsMultiSelectProps {
  /** Full list of selectable positions in the current quote. */
  items: QuoteItemForSelect[];
  /** UUIDs of the currently selected positions (controlled). */
  selectedIds: string[];
  /** Invoked with the next array of selected ids on every change. */
  onChange: (ids: string[]) => void;
  /**
   * When `false`, the search input is hidden — useful inside compact
   * popovers where vertical space is at a premium. Default `true`.
   */
  searchable?: boolean;
  /** Optional className passed to the outer container for layout overrides. */
  className?: string;
}

export function PositionsMultiSelect({
  items,
  selectedIds,
  onChange,
  searchable = true,
  className,
}: PositionsMultiSelectProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => filterItems(items, search), [items, search]);
  const allSelected = allFilteredSelected(filtered, selectedIds);

  function handleToggleRow(id: string) {
    onChange(toggleId(selectedIds, id));
  }

  function handleToggleAll() {
    onChange(nextSelectionAfterToggleAll(filtered, selectedIds));
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border bg-card",
        className,
      )}
      data-slot="positions-multi-select"
    >
      {searchable && (
        <div className="border-b border-border p-2">
          <div className="relative">
            <Search
              className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
              size={14}
            />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск по названию/SKU"
              className="h-7 pl-7 text-xs"
              aria-label="Поиск позиций"
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
      )}

      <div className="flex items-center justify-between px-2 pt-1 pb-1">
        <span className="text-xs text-muted-foreground">
          {`Выбрано: ${selectedIds.length} из ${items.length}`}
        </span>
        <Button
          type="button"
          variant="ghost"
          size="xs"
          onClick={handleToggleAll}
          disabled={filtered.length === 0}
          aria-label={allSelected ? "Снять все" : "Выбрать все"}
        >
          {allSelected ? "Снять все" : "Выбрать все"}
        </Button>
      </div>

      <div
        className="flex flex-col overflow-y-auto"
        style={{ maxHeight: 320 }}
        data-slot="positions-list"
      >
        {filtered.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-muted-foreground">
            Ничего не найдено
          </div>
        ) : (
          filtered.map((item) => {
            const isChecked = selectedIds.includes(item.id);
            return (
              <label
                key={item.id}
                className={cn(
                  "flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left text-xs",
                  "hover:bg-muted/50",
                  isChecked && "bg-muted/30",
                )}
                data-slot="positions-row"
                data-item-id={item.id}
              >
                <Checkbox
                  checked={isChecked}
                  onCheckedChange={() => handleToggleRow(item.id)}
                  aria-label={`Позиция №${item.position}`}
                />
                <span className="flex-1 truncate">
                  <span className="font-medium text-foreground">
                    {`№${item.position}`}
                  </span>
                  <span className="text-muted-foreground"> · </span>
                  <span className="text-foreground">{item.name}</span>
                  {item.product_code ? (
                    <>
                      <span className="text-muted-foreground"> · </span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {item.product_code}
                      </span>
                    </>
                  ) : null}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatRub(item.rub_basis)}
                </span>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}
