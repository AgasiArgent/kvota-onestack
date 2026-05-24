"use client";

import {
  useRouter,
  usePathname,
  useSearchParams,
  type ReadonlyURLSearchParams,
} from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * URL-backed filter state primitives (Testing 2 rows 64-66).
 *
 * Filters live in the URL query string so they survive navigation (back/forward,
 * full page reloads, deep links). The hook exposes:
 *  - `params` — the current ReadonlyURLSearchParams (re-rendered on change).
 *  - `getMulti(key)` — read a comma-separated list value as `string[]`.
 *  - `getSingle(key)` — read a single value (or `null`).
 *  - `setMulti(key, values)` — replace the list (clears the key when empty).
 *  - `setSingle(key, value)` — set / clear (use `null` to clear).
 *  - `setMany(updates)` — atomic multi-key update (one router.replace call).
 *  - `clearAll(preserveKeys?)` — wipe all filter params, optionally preserving
 *     non-filter keys like `?step=...` already in the URL.
 *
 * Persistence is via `router.replace` to avoid stacking history entries on
 * every keystroke / chip-click. Server components read `searchParams` from
 * page props; this hook is for the client side.
 */

const LIST_SEPARATOR = ",";

export function parseMulti(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(LIST_SEPARATOR)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export function serializeMulti(values: readonly string[]): string {
  return values
    .map((v) => v.trim())
    .filter((v) => v.length > 0)
    .join(LIST_SEPARATOR);
}

export interface FilterStateApi {
  params: ReadonlyURLSearchParams;
  getMulti: (key: string) => string[];
  getSingle: (key: string) => string | null;
  setMulti: (key: string, values: readonly string[]) => void;
  setSingle: (key: string, value: string | null) => void;
  setMany: (
    updates: Record<string, string | readonly string[] | null>
  ) => void;
  clearAll: (preserveKeys?: readonly string[]) => void;
}

export function useFilterState(): FilterStateApi {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // useSearchParams() can be null in some build environments; treat that as an
  // empty param set so consumers never have to null-check.
  const params = useMemo<ReadonlyURLSearchParams>(
    () =>
      searchParams ??
      (new URLSearchParams() as unknown as ReadonlyURLSearchParams),
    [searchParams]
  );

  const writeParams = useCallback(
    (next: URLSearchParams) => {
      const qs = next.toString();
      // usePathname() can theoretically be null during the initial hydration
      // tick; fall back to "" so we never push "null?qs" into the URL.
      const base = pathname ?? "";
      const target = qs.length > 0 ? `${base}?${qs}` : base;
      router.replace(target, { scroll: false });
    },
    [pathname, router]
  );

  const getMulti = useCallback(
    (key: string) => parseMulti(params.get(key)),
    [params]
  );

  const getSingle = useCallback(
    (key: string) => {
      const value = params.get(key);
      return value && value.length > 0 ? value : null;
    },
    [params]
  );

  const setMulti = useCallback(
    (key: string, values: readonly string[]) => {
      const next = new URLSearchParams(params.toString());
      const serialized = serializeMulti(values);
      if (serialized.length === 0) {
        next.delete(key);
      } else {
        next.set(key, serialized);
      }
      writeParams(next);
    },
    [params, writeParams]
  );

  const setSingle = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (!value || value.length === 0) {
        next.delete(key);
      } else {
        next.set(key, value);
      }
      writeParams(next);
    },
    [params, writeParams]
  );

  const setMany = useCallback(
    (updates: Record<string, string | readonly string[] | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value == null) {
          next.delete(key);
        } else if (Array.isArray(value)) {
          const serialized = serializeMulti(value as readonly string[]);
          if (serialized.length === 0) next.delete(key);
          else next.set(key, serialized);
        } else if (typeof value === "string") {
          if (value.length === 0) next.delete(key);
          else next.set(key, value);
        }
      }
      writeParams(next);
    },
    [params, writeParams]
  );

  const clearAll = useCallback(
    (preserveKeys: readonly string[] = []) => {
      const next = new URLSearchParams();
      for (const key of preserveKeys) {
        const value = params.get(key);
        if (value != null && value.length > 0) next.set(key, value);
      }
      writeParams(next);
    },
    [params, writeParams]
  );

  return {
    params,
    getMulti,
    getSingle,
    setMulti,
    setSingle,
    setMany,
    clearAll,
  };
}
