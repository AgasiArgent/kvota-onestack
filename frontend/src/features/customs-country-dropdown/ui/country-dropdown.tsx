"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, ChevronsUpDown, Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import {
  fetchOksmCountries,
  type OksmCountry,
} from "../api/fetch-countries";

export interface CustomsCountryDropdownProps {
  /** ОКСМ digital code, or null when no country is selected. */
  value: number | null;
  /** Invoked with the newly picked OKSM digital code or null on clear. */
  onChange: (oksm: number | null) => void;
  placeholder?: string;
  clearable?: boolean;
  disabled?: boolean;
  ariaLabel?: string;
  className?: string;
  /** Default 256px upper bound on the scrollable list height. */
  listMaxHeight?: number;
}

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing without a DOM environment.
// ---------------------------------------------------------------------------

/**
 * Case-insensitive substring search across name_ru, iso_alpha2, and
 * oksm_digital (string form).
 */
export function filterOksmCountries(
  countries: readonly OksmCountry[],
  query: string
): readonly OksmCountry[] {
  const needle = query.trim().toLowerCase();
  if (needle.length === 0) return countries;
  return countries.filter(
    (c) =>
      c.name_ru.toLowerCase().includes(needle) ||
      c.iso_alpha2.toLowerCase().includes(needle) ||
      String(c.oksm_digital).includes(needle)
  );
}

/**
 * Compute the next focused index for ArrowUp/ArrowDown keyboard navigation.
 * Wraps at boundaries; returns -1 for empty lists.
 */
export function computeNextFocusedIndex(
  current: number,
  direction: "up" | "down",
  listLength: number
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

export function CustomsCountryDropdown({
  value,
  onChange,
  placeholder = "Выберите страну происхождения",
  clearable = true,
  disabled = false,
  ariaLabel,
  className,
  listMaxHeight = 256,
}: CustomsCountryDropdownProps) {
  const [countries, setCountries] = useState<OksmCountry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const listRef = useRef<HTMLDivElement | null>(null);

  // One-time fetch of the small (~250 row) reference set.
  useEffect(() => {
    let cancelled = false;
    fetchOksmCountries()
      .then((rows) => {
        if (cancelled) return;
        setCountries(rows);
        setLoading(false);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => countries.find((c) => c.oksm_digital === value) ?? null,
    [countries, value]
  );
  const filtered = useMemo(
    () => filterOksmCountries(countries, search),
    [countries, search]
  );

  // Clamp focusedIndex without triggering a cascading setState — derive the
  // effective index for rendering, and keep the underlying state untouched.
  const effectiveFocusedIndex =
    filtered.length === 0
      ? -1
      : focusedIndex >= filtered.length
        ? filtered.length - 1
        : focusedIndex;

  // Reset search/focus when the popover opens. Using a ref-keyed counter
  // pattern keeps the effect dependent on a single value transition.
  const prevOpenRef = useRef(false);
  useEffect(() => {
    if (open && !prevOpenRef.current) {
      // Defer to a microtask so we don't synchronously cascade renders.
      queueMicrotask(() => {
        setSearch("");
        setFocusedIndex(-1);
      });
    }
    prevOpenRef.current = open;
  }, [open]);

  // Scroll focused option into view.
  useEffect(() => {
    if (effectiveFocusedIndex < 0 || !listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(
      `[data-country-index="${effectiveFocusedIndex}"]`
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [effectiveFocusedIndex]);

  function commitSelection(oksm: number) {
    onChange(oksm);
    setOpen(false);
  }

  function handleClear(e: React.PointerEvent<HTMLElement>) {
    e.preventDefault();
    e.stopPropagation();
    onChange(null);
  }

  function handleSearchKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((prev) =>
        computeNextFocusedIndex(prev, "down", filtered.length)
      );
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((prev) =>
        computeNextFocusedIndex(prev, "up", filtered.length)
      );
    } else if (e.key === "Enter") {
      if (focusedIndex >= 0 && focusedIndex < filtered.length) {
        e.preventDefault();
        commitSelection(filtered[focusedIndex].oksm_digital);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const showClear = clearable && selected != null && !disabled;
  const triggerLabel = selected ? selected.name_ru : placeholder;

  return (
    <div className="flex flex-col gap-1">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger
          render={
            <button
              type="button"
              disabled={disabled || loading}
              aria-label={ariaLabel}
              className={cn(
                "inline-flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-2.5 py-1 text-sm transition-colors",
                "hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
                "disabled:pointer-events-none disabled:opacity-50",
                "aria-expanded:bg-muted",
                className
              )}
            >
              <span
                className={cn(
                  "truncate",
                  selected ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {loading ? "Загрузка стран…" : triggerLabel}
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
                          event as unknown as React.PointerEvent<HTMLElement>
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
                  placeholder="Поиск по названию…"
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
              {loadError ? (
                <div className="px-3 py-4 text-center text-xs text-destructive">
                  {loadError}
                </div>
              ) : countries.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                  Список пуст
                </div>
              ) : filtered.length === 0 ? (
                <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                  Не найдено
                </div>
              ) : (
                filtered.map((country, index) => {
                  const isSelected = country.oksm_digital === value;
                  const isFocused = index === effectiveFocusedIndex;
                  return (
                    <button
                      type="button"
                      key={country.oksm_digital}
                      data-country-index={index}
                      onClick={() => commitSelection(country.oksm_digital)}
                      onMouseEnter={() => setFocusedIndex(index)}
                      className={cn(
                        "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs",
                        "hover:bg-muted/50",
                        isFocused && "bg-muted/50"
                      )}
                    >
                      <span className="flex w-3 shrink-0 justify-center text-accent">
                        {isSelected && <Check size={12} />}
                      </span>
                      <span className="flex-1 truncate">
                        <span className="text-foreground">
                          {country.name_ru}
                        </span>
                        {country.is_unfriendly && (
                          <span
                            className="ml-1.5 text-[10px] text-destructive"
                            title="Недружественная страна (ПП 430-р)"
                          >
                            ⚠
                          </span>
                        )}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                        {country.iso_alpha2}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {selected?.is_unfriendly && (
        <div
          role="status"
          className="rounded-md border border-destructive/30 bg-destructive/5 px-2 py-1 text-[11px] text-destructive"
        >
          ⚠️ Недружественная страна (ПП 430-р)
        </div>
      )}
    </div>
  );
}
