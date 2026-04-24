"use client";

/**
 * CityAutocomplete — text-input-shaped city picker that filters suggestions
 * by a sibling country selection.
 *
 * - Accepts the city as a plain `string` value (REQ 2.1) — unlike
 *   CityCombobox which binds to a structured {city, country_code, …} object.
 * - Filters by `countryCode`: when null the input is disabled and a hint
 *   guides the user to pick a country first (REQ 2.1 parent-child rule).
 * - Selection writes the canonical city name returned by the server, not
 *   the free text the user typed (REQ 2.4).
 * - On backend error, silently falls back to free-text mode — the user's
 *   typing is preserved in `value` so they can still submit the form
 *   (graceful degradation).
 *
 * The component proxies its request through `/api/geo/cities/search` which
 * dispatches to DaData (RU) or HERE Geocode (everything else). Client-side
 * filtering by `country_code` keeps results scoped to the selected country
 * when the backend returns broader matches.
 */

import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// ============================================================================
// Public types
// ============================================================================

export interface CityAutocompleteProps {
  /** Current city name (canonical after a successful pick, free text otherwise). */
  value: string;
  /** Receives the chosen city name — canonical when picked from the list. */
  onChange: (city: string) => void;
  /**
   * ISO 3166-1 alpha-2 of the sibling country selection. When null the
   * autocomplete disables itself and prompts the user to pick a country.
   */
  countryCode: string | null;
  placeholder?: string;
  ariaLabel?: string;
  disabled?: boolean;
  /** Debounce delay in milliseconds (default 300). */
  debounceMs?: number;
  /** Minimum trimmed query length before a fetch is issued (default 2). */
  minQueryLength?: number;
  className?: string;
}

export interface CityAutocompleteItem {
  city: string;
  country_code: string;
  country_name_ru: string;
  country_name_en: string;
  display: string;
}

/** Result of a single `fetchCityAutocomplete` call. */
export type CityAutocompleteFetchResult =
  | { ok: true; data: CityAutocompleteItem[] }
  | { ok: false };

// ============================================================================
// Pure helpers (tested in isolation by city-autocomplete.test.tsx)
// ============================================================================

/**
 * Returns true when a query is long enough to warrant a network fetch.
 * Extracted so the debounce-and-min-length rules can be verified without
 * rendering the component.
 */
export function shouldIssueFetch(
  query: string,
  minQueryLength: number,
): boolean {
  return query.trim().length >= minQueryLength;
}

/**
 * Keep only suggestions whose `country_code` matches the parent country.
 *
 * The backend may return cities from other countries (DaData returns only
 * RU entries so it's a no-op there; HERE Geocode without a country filter
 * returns global matches). Filtering client-side keeps UX consistent and
 * future-proofs the component against backend filter changes.
 */
export function filterByCountryCode(
  items: CityAutocompleteItem[],
  countryCode: string,
): CityAutocompleteItem[] {
  const normalized = countryCode.trim().toUpperCase();
  if (normalized.length === 0) return items;
  return items.filter(
    (i) => (i.country_code || "").toUpperCase() === normalized,
  );
}

/**
 * Fetch wrapper for `GET /api/geo/cities/search`.
 *
 * Returns a tagged result so callers don't plumb try/catch. The `countryCode`
 * is forwarded as a query param; current backend ignores it (RU via DaData
 * returns Russia-only suggestions; non-RU via HERE returns global) but we
 * client-filter via `filterByCountryCode` regardless.
 *
 * `credentials: "include"` forwards the legacy FastHTML session cookie so
 * the dual-auth path works without requiring a JWT.
 */
export async function fetchCityAutocomplete(
  query: string,
  countryCode: string,
  limit: number,
  signal?: AbortSignal,
): Promise<CityAutocompleteFetchResult> {
  const trimmed = query.trim();
  const params = new URLSearchParams();
  params.set("q", trimmed);
  params.set("limit", String(limit));
  if (countryCode) {
    params.set("country_code", countryCode);
  }

  try {
    const response = await fetch(
      `/api/geo/cities/search?${params.toString()}`,
      {
        method: "GET",
        credentials: "include",
        signal,
      },
    );
    if (!response.ok) {
      return { ok: false };
    }
    const body = (await response.json()) as {
      success?: boolean;
      data?: unknown;
    };
    if (body.success !== true || !Array.isArray(body.data)) {
      return { ok: false };
    }
    return { ok: true, data: body.data as CityAutocompleteItem[] };
  } catch {
    return { ok: false };
  }
}

// ============================================================================
// Component
// ============================================================================

const DEFAULT_PLACEHOLDER = "Начните печатать название города…";
const DISABLED_PLACEHOLDER = "Выберите страну";
const DEFAULT_DEBOUNCE_MS = 300;
const DEFAULT_MIN_QUERY_LENGTH = 2;
const RESULT_LIMIT = 10;

export function CityAutocomplete({
  value,
  onChange,
  countryCode,
  placeholder = DEFAULT_PLACEHOLDER,
  ariaLabel,
  disabled = false,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  minQueryLength = DEFAULT_MIN_QUERY_LENGTH,
  className,
}: CityAutocompleteProps) {
  const isDisabled = disabled || !countryCode;

  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CityAutocompleteItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  // AbortController for the in-flight fetch — cancel stale requests so
  // out-of-order responses don't overwrite the latest list.
  const abortRef = useRef<AbortController | null>(null);
  // Track whether the last list change came from a user selection (so we
  // don't immediately re-fetch and re-open the dropdown after a pick).
  const justPickedRef = useRef(false);

  // Close the dropdown and cancel pending requests when the country
  // selection changes (REQ 2.1 — country is the filter key, changing it
  // invalidates any cached city list). Same pattern as CityCombobox's
  // open/close reset effect.
  useEffect(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setItems([]);
    setOpen(false);
    setFocusedIndex(-1);
  }, [countryCode]);

  // Debounced fetch effect. Only runs while the input is focused/open so a
  // programmatic value change (e.g., form reset) doesn't trigger a search.
  useEffect(() => {
    if (isDisabled) return;
    if (!open) return;
    if (justPickedRef.current) {
      justPickedRef.current = false;
      return;
    }
    if (!shouldIssueFetch(value, minQueryLength)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setItems([]);
      setLoading(false);
      return;
    }

    const timer = setTimeout(() => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setLoading(true);
      fetchCityAutocomplete(
        value,
        countryCode ?? "",
        RESULT_LIMIT,
        controller.signal,
      ).then((result) => {
        if (controller.signal.aborted) return;
        setLoading(false);
        if (result.ok) {
          const filtered = countryCode
            ? filterByCountryCode(result.data, countryCode)
            : result.data;
          setItems(filtered);
          setFocusedIndex(-1);
        } else {
          // Graceful degradation — log once and fall back to free-text mode
          // (REQ 2 error-handling: don't block the user).
          console.warn("[city-autocomplete] fetch failed");
          setItems([]);
        }
      });
    }, debounceMs);

    return () => {
      clearTimeout(timer);
    };
  }, [value, countryCode, isDisabled, open, debounceMs, minQueryLength]);

  function handleChange(next: string) {
    onChange(next);
    if (!open) setOpen(true);
  }

  function handlePick(item: CityAutocompleteItem) {
    justPickedRef.current = true;
    onChange(item.city);
    setItems([]);
    setOpen(false);
    setFocusedIndex(-1);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || items.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIndex((prev) => (prev + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIndex((prev) => (prev - 1 + items.length) % items.length);
    } else if (e.key === "Enter") {
      if (focusedIndex >= 0 && focusedIndex < items.length) {
        e.preventDefault();
        handlePick(items[focusedIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  }

  const resolvedPlaceholder = !countryCode
    ? DISABLED_PLACEHOLDER
    : placeholder;
  const showList = open && items.length > 0 && !isDisabled;

  return (
    <div className={cn("relative", className)}>
      <div className="relative">
        <Input
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => !isDisabled && setOpen(true)}
          onBlur={() => {
            // Delay so a click on a result lands before the dropdown closes.
            setTimeout(() => setOpen(false), 150);
          }}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          placeholder={resolvedPlaceholder}
          aria-label={ariaLabel}
          aria-autocomplete="list"
          aria-expanded={showList}
          className={cn(loading ? "pr-8" : undefined)}
        />
        {loading && (
          <Loader2
            className="absolute right-2 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground"
            size={14}
            aria-label="Поиск…"
          />
        )}
      </div>

      {showList && (
        <div
          role="listbox"
          className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-border bg-background py-1 shadow-md"
        >
          {items.map((item, idx) => {
            const isFocused = idx === focusedIndex;
            return (
              <button
                type="button"
                key={`${item.city}-${item.country_code}-${idx}`}
                role="option"
                aria-selected={isFocused}
                onMouseEnter={() => setFocusedIndex(idx)}
                onMouseDown={(e) => {
                  // mousedown fires before blur — prevent the input from
                  // losing focus before we commit the selection.
                  e.preventDefault();
                  handlePick(item);
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-xs",
                  "hover:bg-muted/50",
                  isFocused && "bg-muted/50",
                )}
              >
                <span className="truncate font-medium text-foreground">
                  {item.city}
                </span>
                <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground/70">
                  {item.country_code}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
