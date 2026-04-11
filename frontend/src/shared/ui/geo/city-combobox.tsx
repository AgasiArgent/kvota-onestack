"use client";

import { useEffect, useRef, useState } from "react";
import { Loader2, Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

// ============================================================================
// Public types
// ============================================================================

export interface CityComboboxValue {
  city: string;
  country_code: string;
  country_name_ru: string;
  country_name_en: string;
  display: string;
}

export interface CityComboboxProps {
  value: CityComboboxValue | null;
  onChange: (next: CityComboboxValue | null) => void;
  /**
   * Optional callback fired alongside `onChange` so a sibling CountryCombobox
   * can stay in sync with the selected city's country (REQ 2.10).
   */
  onCountryChange?: (countryCode: string | null) => void;
  placeholder?: string;
  disabled?: boolean;
  /** Debounce delay in milliseconds (default 300). */
  debounceMs?: number;
  /** Minimum trimmed query length before a fetch is issued (default 2). */
  minQueryLength?: number;
  className?: string;
}

/** Discriminated union tracked by the component while the popover is open. */
export type CitySearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; items: CityComboboxValue[] }
  | { kind: "error" };

// ============================================================================
// Pure helpers (tested in isolation by city-combobox.test.tsx)
// ============================================================================

/**
 * Gate for whether a query should trigger a network fetch.
 *
 * Returns false when the trimmed query is shorter than `minQueryLength`
 * (including the empty / whitespace-only case).
 *
 * This is extracted as a pure function so the debounce and min-length rules
 * can be tested without rendering the component (the workspace has no DOM
 * testing environment — see country-combobox.test.tsx for rationale).
 */
export function shouldIssueFetch(query: string, minQueryLength: number): boolean {
  return query.trim().length >= minQueryLength;
}

/** Result of a single `fetchCitySearch` call. */
export type CitySearchFetchResult =
  | { ok: true; data: CityComboboxValue[] }
  | { ok: false };

/**
 * Fetch wrapper for `GET /api/geo/cities/search`.
 *
 * Returns a tagged result object so callers don't need try/catch plumbing:
 *   - `{ ok: true, data: [...] }` on any 2xx with a well-formed envelope
 *     (including an empty array, which represents "no matches")
 *   - `{ ok: false }` on any non-ok HTTP status, network failure, abort,
 *     or malformed body — the component surfaces these uniformly as
 *     "Поиск недоступен" (REQ 2.8).
 *
 * `credentials: "include"` forwards the legacy FastHTML session cookie so
 * the dual-auth path works without requiring a JWT. AI agents will supply
 * a Supabase JWT via the standard Authorization header — this browser
 * helper uses the cookie path exclusively.
 */
export async function fetchCitySearch(
  query: string,
  limit: number,
  signal?: AbortSignal,
): Promise<CitySearchFetchResult> {
  const trimmed = query.trim();
  const params = new URLSearchParams();
  params.set("q", trimmed);
  params.set("limit", String(limit));

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
    // Trust the server's shape — the endpoint validates before serializing.
    return { ok: true, data: body.data as CityComboboxValue[] };
  } catch {
    return { ok: false };
  }
}

// ============================================================================
// Component
// ============================================================================

const DEFAULT_PLACEHOLDER = "Начните печатать название города…";
const DEFAULT_DEBOUNCE_MS = 300;
const DEFAULT_MIN_QUERY_LENGTH = 2;
const RESULT_LIMIT = 10;

export function CityCombobox({
  value,
  onChange,
  onCountryChange,
  placeholder = DEFAULT_PLACEHOLDER,
  disabled = false,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  minQueryLength = DEFAULT_MIN_QUERY_LENGTH,
  className,
}: CityComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [state, setState] = useState<CitySearchState>({ kind: "idle" });

  // AbortController for the in-flight fetch — so a new keystroke during
  // debounce can cancel a slower, earlier request and avoid out-of-order
  // success messages overwriting the latest list.
  const abortRef = useRef<AbortController | null>(null);

  // Reset the search state whenever the popover re-opens so stale results
  // from a prior session don't flash before the user starts typing.
  useEffect(() => {
    if (open) {
      setQuery("");
      setState({ kind: "idle" });
    } else {
      // Popover closed — cancel any in-flight request.
      abortRef.current?.abort();
      abortRef.current = null;
    }
  }, [open]);

  // Debounced fetch effect. Runs whenever the query changes, with a
  // `debounceMs` grace period. If the query fails the min-length gate
  // we immediately reset to idle instead of issuing a request.
  useEffect(() => {
    if (!open) return;

    if (!shouldIssueFetch(query, minQueryLength)) {
      setState({ kind: "idle" });
      return;
    }

    const timer = setTimeout(() => {
      // Cancel any prior in-flight fetch before starting a new one.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setState({ kind: "loading" });
      fetchCitySearch(query, RESULT_LIMIT, controller.signal).then((result) => {
        // If the controller was aborted between the fetch start and now,
        // the promise may still resolve — ignore stale results.
        if (controller.signal.aborted) return;
        if (result.ok) {
          setState({ kind: "success", items: result.data });
        } else {
          setState({ kind: "error" });
        }
      });
    }, debounceMs);

    return () => {
      clearTimeout(timer);
    };
  }, [query, open, debounceMs, minQueryLength]);

  function handleSelect(item: CityComboboxValue) {
    onChange(item);
    if (onCountryChange) {
      onCountryChange(item.country_code || null);
    }
    setOpen(false);
  }

  const triggerLabel = value?.display || placeholder;
  const triggerIsPlaceholder = !value;

  return (
    <Popover open={open} onOpenChange={disabled ? undefined : setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            disabled={disabled}
            aria-label="Поиск города"
            className={cn(
              "inline-flex h-8 w-full items-center justify-between rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors",
              "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
              "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
              triggerIsPlaceholder ? "text-muted-foreground" : "text-foreground",
              className,
            )}
          >
            <span className="truncate">{triggerLabel}</span>
          </button>
        }
      />
      <PopoverContent className="w-80 p-0" side="bottom" align="start">
        <div className="flex flex-col">
          {/* Search input + loading spinner */}
          <div className="border-b border-border p-2">
            <div className="relative">
              <Search
                className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
                size={14}
              />
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Введите минимум 2 символа"
                className="h-8 pl-7 pr-7 text-sm"
                autoFocus
              />
              {state.kind === "loading" && (
                <Loader2
                  className="absolute right-2 top-1/2 -translate-y-1/2 animate-spin text-muted-foreground"
                  size={14}
                  aria-label="Поиск..."
                />
              )}
            </div>
          </div>

          {/* State-driven result pane */}
          <div className="max-h-64 overflow-y-auto py-1">
            {state.kind === "idle" && query.trim().length < minQueryLength && (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Введите минимум {minQueryLength} символа
              </div>
            )}
            {state.kind === "loading" && (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Поиск…
              </div>
            )}
            {state.kind === "success" && state.items.length === 0 && (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Ничего не найдено
              </div>
            )}
            {state.kind === "success" &&
              state.items.length > 0 &&
              state.items.map((item, idx) => (
                <button
                  type="button"
                  key={`${item.city}-${item.country_code}-${idx}`}
                  onClick={() => handleSelect(item)}
                  className="flex w-full items-start justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-muted/50"
                >
                  <span className="flex-1">
                    <span className="block truncate font-medium text-foreground">
                      {item.city}
                    </span>
                    <span className="block truncate text-muted-foreground">
                      {item.country_name_ru}
                    </span>
                  </span>
                  <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground/70">
                    {item.country_code}
                  </span>
                </button>
              ))}
            {state.kind === "error" && (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Поиск недоступен
              </div>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
