"use client";

import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useDebounce } from "@/shared/lib/use-debounce";

export interface SearchInputFilterProps {
  /** Currently committed value from the URL (or null when unset). */
  value: string | null;
  /** Commit a new debounced search value. Called with `null` when cleared. */
  onChange: (next: string | null) => void;
  /** Placeholder copy — defaults to «Поиск по IDN…». */
  placeholder?: string;
  /** ARIA-label for screen readers. */
  ariaLabel?: string;
  /** Debounce delay in ms (default 300). */
  debounceMs?: number;
  /** Optional extra class on the wrapper. */
  className?: string;
}

/**
 * Debounced URL-backed text search filter (Testing 2 row 66).
 *
 * Mirrors the visual treatment of the other filter chips in `FilterBar` —
 * a 32px high input with a leading search icon and a trailing clear ✕. The
 * local input value is what the user types; the parent only sees the
 * debounced value once typing pauses for `debounceMs` (default 300ms),
 * preventing a router.replace on every keystroke.
 *
 * The component is fully controlled: the URL is the source of truth, so an
 * external URL change (e.g. «Сбросить все») resets the visible input too.
 */
export function SearchInputFilter({
  value,
  onChange,
  placeholder = "Поиск по IDN…",
  ariaLabel,
  debounceMs = 300,
  className,
}: SearchInputFilterProps) {
  const [local, setLocal] = useState<string>(value ?? "");

  // Sync local state when the URL value changes from outside (e.g. browser
  // back/forward or «Сбросить все»). Only resync when the *committed* value
  // differs from local — comparing trimmed forms keeps the cursor stable while
  // the user is mid-typing.
  useEffect(() => {
    const committed = (value ?? "").trim();
    const localTrimmed = local.trim();
    if (committed !== localTrimmed) {
      setLocal(value ?? "");
    }
    // Intentionally exclude `local` from deps — we only want to react to URL
    // changes, not the typing churn that produces them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const debounced = useDebounce(local, debounceMs);

  // Push the debounced value upstream when it stabilises. `null` for empty so
  // the URL key is dropped (clean URLs).
  useEffect(() => {
    const trimmed = debounced.trim();
    const committed = (value ?? "").trim();
    if (trimmed === committed) return;
    onChange(trimmed.length === 0 ? null : trimmed);
    // `onChange` and `value` are stable per render in practice; keeping them
    // out of deps avoids loops when the parent re-creates the callback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  function handleClear() {
    setLocal("");
    onChange(null);
  }

  const isActive = (value ?? "").trim().length > 0;

  return (
    <div
      className={cn(
        "relative inline-flex h-8 w-56 items-center",
        className
      )}
    >
      <Search
        size={14}
        className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        type="search"
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        placeholder={placeholder}
        aria-label={ariaLabel ?? placeholder}
        className={cn(
          "h-8 pl-7 text-xs",
          isActive ? "border-accent" : undefined,
          local.length > 0 ? "pr-7" : undefined
        )}
      />
      {local.length > 0 && (
        <button
          type="button"
          onClick={handleClear}
          aria-label="Очистить поиск"
          className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
}
