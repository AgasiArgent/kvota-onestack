"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

/**
 * Generic searchable combobox for entity-pickers (suppliers, buyer companies,
 * etc.) — fixes МОЗ Тест fail items #76, #78 and РОЗ-89 / РОЗ-91.
 *
 * Pattern matches `shared/ui/geo/country-combobox.tsx`: Popover trigger button
 * + Search input + filtered list + arrow-key navigation + Enter to commit
 * + click-outside via Popover. Generic over the item shape; consumers provide
 * a key extractor and a label extractor.
 *
 * Per CLAUDE.md "UI Standards": every entity-picker dropdown in the app must
 * be searchable. Native `<select>` is unusable for lists ≥ 14 options.
 */

export interface SearchableComboboxItem {
  /** Stable identifier used as the option's React key and the value emitted on select. */
  id: string;
}

export interface SearchableComboboxProps<T extends SearchableComboboxItem> {
  /** Currently selected id, or null when nothing is selected. */
  value: string | null;
  /** Invoked with the newly picked id, or null on clear. */
  onChange: (id: string | null) => void;
  /** Source list (already loaded — this combobox does not fetch). */
  items: readonly T[];
  /**
   * Maps an item to its display label (for both the trigger and the list rows).
   * Must be stable for a given item — React keys are derived from `item.id`,
   * not from the label.
   */
  getLabel: (item: T) => string;
  /**
   * Optional secondary text rendered after the primary label inside list rows
   * (e.g., supplier country, buyer company code). Not used in the search match.
   */
  getSecondary?: (item: T) => string | null;
  /**
   * Optional extra search tokens for an item (e.g., country, alternate name).
   * Filter compares against `[getLabel, ...getSearchableExtras]` joined.
   */
  getSearchableExtras?: (item: T) => readonly string[];
  /** Trigger placeholder when nothing is selected. */
  placeholder?: string;
  /** Search input placeholder. Default: "Поиск...". */
  searchPlaceholder?: string;
  /** Empty-list message shown when the source list is empty. */
  emptyMessage?: string;
  /** Empty-search message shown when search filters everything out. */
  noMatchMessage?: string;
  /** Default: true. When false, the X clear affordance is hidden. */
  clearable?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  /** Marks the trigger with the destructive border (validation error). */
  invalid?: boolean;
  className?: string;
  /** Default: 256 (px). Upper bound on the scrollable list height. */
  listMaxHeight?: number;
  /** Tailwind width class for the popover content (default: "w-72"). */
  popoverWidthClass?: string;
}

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

// Combining diacritical marks block U+0300..U+036F (literal marks in source).
// NFD decomposes "café" → "café", then this regex strips the ́.
// Cyrillic has no precomposed accents that decompose this way, so Russian
// search degrades to plain case-insensitive substring match — which is what
// the spec requires for МОЗ/РОЗ supplier/buyer pickers.
const DIACRITICS_RE = /[̀-ͯ]/g;

function normalize(str: string): string {
  return str.trim().toLowerCase().normalize("NFD").replace(DIACRITICS_RE, "");
}

/**
 * Case- and accent-insensitive substring search across the label plus any
 * extras the consumer flagged. Returns the full list for empty queries.
 */
export function filterItems<T extends SearchableComboboxItem>(
  items: readonly T[],
  query: string,
  getLabel: (item: T) => string,
  getSearchableExtras?: (item: T) => readonly string[],
): readonly T[] {
  const needle = normalize(query);
  if (needle.length === 0) return items;
  return items.filter((item) => {
    const haystack = [getLabel(item), ...(getSearchableExtras?.(item) ?? [])]
      .map(normalize)
      .join(" ");
    return haystack.includes(needle);
  });
}

/**
 * Compute the next focused index for ArrowUp/ArrowDown keyboard navigation.
 * Mirrors `country-combobox.computeNextFocusedIndex`:
 *  - ArrowDown wraps last → 0; ArrowUp wraps 0 → last.
 *  - -1 (no focus yet) jumps to first on Down, last on Up.
 *  - Out-of-range starts get clamped into a valid range.
 */
export function computeNextFocusedIndex(
  current: number,
  direction: "up" | "down",
  listLength: number,
): number {
  if (listLength <= 0) return -1;
  let start = current;
  if (start >= listLength) start = listLength - 1;
  if (start < -1) start = -1;

  if (direction === "down") {
    if (start === -1) return 0;
    return (start + 1) % listLength;
  }
  if (start === -1) return listLength - 1;
  return (start - 1 + listLength) % listLength;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SearchableCombobox<T extends SearchableComboboxItem>({
  value,
  onChange,
  items,
  getLabel,
  getSecondary,
  getSearchableExtras,
  placeholder = "Выберите…",
  searchPlaceholder = "Поиск...",
  emptyMessage = "Список пуст",
  noMatchMessage = "Ничего не найдено",
  clearable = true,
  disabled = false,
  ariaLabel,
  invalid = false,
  className,
  listMaxHeight = 256,
  popoverWidthClass = "w-72",
}: SearchableComboboxProps<T>) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [rawFocusedIndex, setRawFocusedIndex] = useState(-1);
  const listRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const selected = useMemo(
    () => items.find((it) => it.id === value) ?? null,
    [items, value],
  );
  const triggerLabel = selected ? getLabel(selected) : placeholder;

  const filtered = useMemo(
    () => filterItems(items, search, getLabel, getSearchableExtras),
    [items, search, getLabel, getSearchableExtras],
  );

  // Derived clamp — keeps the focus pointer inside the current filtered list
  // without a setState-in-effect. When the search shrinks `filtered`, the
  // index used for rendering and keyboard nav is the clamped value.
  const focusedIndex = useMemo(() => {
    if (rawFocusedIndex < 0 || filtered.length === 0) return -1;
    if (rawFocusedIndex >= filtered.length) return filtered.length - 1;
    return rawFocusedIndex;
  }, [rawFocusedIndex, filtered.length]);

  // Reset search/focus when the popover opens or closes via the Popover's
  // own onOpenChange handler — avoids a setState-in-effect on `open`.
  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next) {
      setSearch("");
      setRawFocusedIndex(-1);
    }
  }

  // Scroll the focused option into view for keyboard navigation.
  useEffect(() => {
    if (focusedIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(
      `[data-combobox-index="${focusedIndex}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [focusedIndex]);

  function commitSelection(id: string) {
    onChange(id);
    setOpen(false);
  }

  function handleClear(e: React.PointerEvent<HTMLElement>) {
    // Fire on pointerdown so we commit BEFORE the trigger's own click handler
    // opens the popover. preventDefault blocks the trigger from receiving
    // focus, stopPropagation keeps base-ui from interpreting this as a
    // trigger-open event.
    e.preventDefault();
    e.stopPropagation();
    onChange(null);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setRawFocusedIndex(
        computeNextFocusedIndex(focusedIndex, "down", filtered.length),
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setRawFocusedIndex(
        computeNextFocusedIndex(focusedIndex, "up", filtered.length),
      );
    } else if (e.key === "Enter") {
      if (focusedIndex >= 0 && focusedIndex < filtered.length) {
        e.preventDefault();
        commitSelection(filtered[focusedIndex].id);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const showClear = clearable && selected != null && !disabled;

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            disabled={disabled}
            aria-label={ariaLabel}
            className={cn(
              "inline-flex h-8 w-full items-center justify-between gap-2 rounded-lg border bg-background px-2.5 py-1 text-sm transition-colors",
              "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              "disabled:pointer-events-none disabled:opacity-50",
              "aria-expanded:bg-muted",
              invalid ? "border-destructive" : "border-input",
              className,
            )}
          >
            <span
              className={cn(
                "truncate",
                selected ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {triggerLabel}
            </span>
            <span className="flex shrink-0 items-center gap-1">
              {showClear && (
                <span
                  role="button"
                  tabIndex={-1}
                  aria-label="Очистить"
                  onPointerDown={handleClear}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleClear(
                        event as unknown as React.PointerEvent<HTMLElement>,
                      );
                    }
                  }}
                  className="inline-flex cursor-pointer items-center justify-center rounded p-0.5 text-muted-foreground hover:text-foreground"
                >
                  <X size={14} />
                </span>
              )}
              <ChevronsUpDown
                size={14}
                className="text-muted-foreground/60"
              />
            </span>
          </button>
        }
      />
      <PopoverContent
        className={cn(popoverWidthClass, "p-0")}
        side="bottom"
        align="start"
        // Focus the search input WITHOUT scrolling the page (Testing 2 row
        // 30 #1). Base UI focuses the popup's first focusable element on
        // open; a plain .focus() on an element below the fold makes the
        // browser jump to the top. preventScroll keeps the viewport put.
        // Returning false tells Base UI not to apply its own focus on top.
        initialFocus={() => {
          searchInputRef.current?.focus({ preventScroll: true });
          return false;
        }}
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
                ref={searchInputRef}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={handleSearchKeyDown}
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
          <div
            ref={listRef}
            className="overflow-y-auto py-1"
            style={{ maxHeight: listMaxHeight }}
          >
            {items.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                {emptyMessage}
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                {noMatchMessage}
              </div>
            ) : (
              filtered.map((item, index) => {
                const isSelected = item.id === value;
                const isFocused = index === focusedIndex;
                const secondary = getSecondary?.(item) ?? null;
                return (
                  <button
                    type="button"
                    key={item.id}
                    data-combobox-index={index}
                    onClick={() => commitSelection(item.id)}
                    onMouseEnter={() => setRawFocusedIndex(index)}
                    className={cn(
                      "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs",
                      "hover:bg-muted/50",
                      isFocused && "bg-muted/50",
                    )}
                  >
                    <span className="flex w-3 shrink-0 justify-center text-accent">
                      {isSelected && <Check size={12} />}
                    </span>
                    <span className="flex-1 truncate">
                      <span className="text-foreground">{getLabel(item)}</span>
                      {secondary && (
                        <>
                          <span className="text-muted-foreground"> · </span>
                          <span className="text-muted-foreground">
                            {secondary}
                          </span>
                        </>
                      )}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
