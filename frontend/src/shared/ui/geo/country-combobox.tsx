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

import {
  COUNTRIES,
  findCountryByCode,
  type Country,
} from "./countries";

export interface CountryComboboxProps {
  /** ISO 3166-1 alpha-2 code, or null when no country is selected. */
  value: string | null;
  /** Invoked with the newly picked ISO-2 code or null on clear. */
  onChange: (code: string | null) => void;
  placeholder?: string;
  /** Default: true. When false, the X clear affordance is hidden. */
  clearable?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  className?: string;
  /** Default: 256 (px). Upper bound on the scrollable list height. */
  listMaxHeight?: number;
  /** Default: "ru". Controls which locale drives the trigger label. */
  displayLocale?: "ru" | "en";
}

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

/**
 * Case-insensitive substring search against nameRu, nameEn, and ISO-2 code
 * simultaneously. Returns the full list for empty/whitespace-only queries.
 */
export function filterCountries(
  countries: readonly Country[],
  query: string,
): readonly Country[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return countries;
  return countries.filter(
    (c) =>
      c.nameRu.toLowerCase().includes(needle) ||
      c.nameEn.toLowerCase().includes(needle) ||
      c.code.toLowerCase().includes(needle),
  );
}

/**
 * Compute the next focused index for ArrowUp/ArrowDown keyboard navigation.
 *
 *  - ArrowDown wraps: last → 0.
 *  - ArrowUp wraps: 0 → last; -1 → last (so first ArrowUp lands on the tail).
 *  - Out-of-range starting indices are clamped into a valid range.
 *  - Returns -1 for an empty list (nothing to focus).
 */
export function computeNextFocusedIndex(
  current: number,
  direction: "up" | "down",
  listLength: number,
): number {
  if (listLength <= 0) return -1;
  // Clamp current into [-1, listLength-1] so out-of-bounds start values
  // (e.g., when the filtered list just shrank) still produce a legal move.
  let start = current;
  if (start >= listLength) start = listLength - 1;
  if (start < -1) start = -1;

  if (direction === "down") {
    if (start === -1) return 0;
    return (start + 1) % listLength;
  }
  // up
  if (start === -1) return listLength - 1;
  return (start - 1 + listLength) % listLength;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CountryCombobox({
  value,
  onChange,
  placeholder = "Выберите страну…",
  clearable = true,
  disabled = false,
  ariaLabel,
  className,
  listMaxHeight = 256,
  displayLocale = "ru",
}: CountryComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const listRef = useRef<HTMLDivElement | null>(null);

  const selected = findCountryByCode(value);
  const triggerLabel = selected
    ? displayLocale === "en"
      ? selected.nameEn
      : selected.nameRu
    : placeholder;

  const filtered = useMemo(() => filterCountries(COUNTRIES, search), [search]);

  // Reset the search box and focused item whenever the popover opens, so the
  // next open starts from a clean slate (mirrors column-filter.tsx behavior).
  useEffect(() => {
    if (open) {
      setSearch("");
      setFocusedIndex(-1);
    }
  }, [open]);

  // Keep focusedIndex in range as the filtered list shrinks past it.
  useEffect(() => {
    if (focusedIndex >= filtered.length) {
      setFocusedIndex(filtered.length > 0 ? filtered.length - 1 : -1);
    }
  }, [filtered.length, focusedIndex]);

  // Scroll the currently focused option into view for keyboard navigation.
  useEffect(() => {
    if (focusedIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(
      `[data-country-index="${focusedIndex}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [focusedIndex]);

  function commitSelection(code: string) {
    onChange(code);
    setOpen(false);
  }

  function handleClear(e: React.PointerEvent<HTMLElement>) {
    // Fire on pointerdown so we commit BEFORE the trigger's own click handler
    // opens the popover. preventDefault blocks the trigger from receiving
    // focus, stopPropagation keeps Radix/Base UI from interpreting this as a
    // trigger-open event.
    e.preventDefault();
    e.stopPropagation();
    onChange(null);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((prev) =>
        computeNextFocusedIndex(prev, "down", filtered.length),
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((prev) =>
        computeNextFocusedIndex(prev, "up", filtered.length),
      );
    } else if (e.key === "Enter") {
      if (focusedIndex >= 0 && focusedIndex < filtered.length) {
        e.preventDefault();
        commitSelection(filtered[focusedIndex].code);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const showClear = clearable && selected != null && !disabled;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            disabled={disabled}
            aria-label={ariaLabel}
            className={cn(
              "inline-flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-2.5 py-1 text-sm transition-colors",
              "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
              "disabled:pointer-events-none disabled:opacity-50",
              "aria-expanded:bg-muted",
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
      <PopoverContent className="w-72 p-0" side="bottom" align="start">
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
                onKeyDown={handleSearchKeyDown}
                placeholder="Поиск страны..."
                className="h-7 pl-7 text-xs"
                autoFocus
                aria-label="Поиск страны"
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
            {COUNTRIES.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Страна не найдена
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Ничего не найдено
              </div>
            ) : (
              filtered.map((country, index) => {
                const isSelected = country.code === value;
                const isFocused = index === focusedIndex;
                return (
                  <button
                    type="button"
                    key={country.code}
                    data-country-index={index}
                    onClick={() => commitSelection(country.code)}
                    onMouseEnter={() => setFocusedIndex(index)}
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
                      <span className="text-foreground">{country.nameRu}</span>
                      <span className="text-muted-foreground"> · </span>
                      <span className="text-muted-foreground">
                        {country.nameEn}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {country.code}
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
