"use client";

import { useCallback, useMemo } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

import type {
  DataTableColumn,
  FilterValue,
  SerializedTableState,
  SortState,
} from "@/shared/ui/data-table/types";

import {
  canonicalizeState,
  cycleSortState,
  parseFilterParams,
  parseSortString,
  serializeSortString,
} from "./filter-serialize";

interface UseTableStateArgs {
  columns: readonly DataTableColumn<unknown>[];
  tableKey: string;
  /** Default filters applied when the URL has no filter params. */
  defaultFilters?: Record<string, FilterValue>;
  /** Default sort applied when the URL has no sort param. */
  defaultSort?: string;
  /** Default visible columns. Falls back to all non-hidden columns if omitted. */
  defaultVisibleColumns?: readonly string[];
}

interface UseTableStateResult {
  // Parsed current state
  filters: Record<string, FilterValue>;
  sort: SortState | null;
  page: number;
  search: string;
  viewId: string | null;
  visibleColumns: readonly string[];

  // Mutators (each updates the URL via router.replace)
  setFilter: (key: string, value: FilterValue | null) => void;
  setSort: (key: string) => void;
  setPage: (page: number) => void;
  setSearch: (term: string) => void;
  setView: (viewId: string | null) => void;
  setVisibleColumns: (keys: readonly string[]) => void;
  clearAllFilters: () => void;

  // Utilities
  serializeCurrent: () => SerializedTableState;
  isModifiedFromView: (viewState: SerializedTableState) => boolean;
}

const VISIBILITY_STORAGE_PREFIX = "oneStack.dataTable";

function visibilityStorageKey(tableKey: string): string {
  return `${VISIBILITY_STORAGE_PREFIX}.${tableKey}.visibleColumns`;
}

function readVisibilityFromStorage(tableKey: string): readonly string[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(visibilityStorageKey(tableKey));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((v): v is string => typeof v === "string");
  } catch {
    return null;
  }
}

function writeVisibilityToStorage(tableKey: string, keys: readonly string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(visibilityStorageKey(tableKey), JSON.stringify(keys));
  } catch {
    // Storage may be unavailable (Safari private mode, quota exceeded) — silently ignore.
  }
}

/**
 * Default visible columns from the column config: all columns whose
 * `defaultVisible` is not explicitly false.
 */
function columnsDefaultVisible(
  columns: readonly DataTableColumn<unknown>[]
): readonly string[] {
  return columns.filter((c) => c.defaultVisible !== false).map((c) => c.key);
}

/**
 * Filter out stale column keys that are no longer present in the column config.
 * Ensures that removed columns don't linger in persisted state (per R5.6).
 */
function reconcileVisibleColumns(
  persisted: readonly string[],
  columns: readonly DataTableColumn<unknown>[]
): readonly string[] {
  const known = new Set(columns.map((c) => c.key));
  return persisted.filter((key) => known.has(key));
}

/**
 * Hook encapsulating URL ↔ filter/sort/view/page/visibility state for the DataTable.
 *
 * - URL is the source of truth for filters, sort, page, search, view id.
 * - Column visibility is sourced from localStorage when no view is active.
 * - Every mutator updates the URL via router.replace (no history pollution).
 * - Filter changes reset page to 1.
 */
export function useTableState({
  columns,
  tableKey,
  defaultFilters = {},
  defaultSort,
  defaultVisibleColumns,
}: UseTableStateArgs): UseTableStateResult {
  const router = useRouter();
  const pathname = usePathname() ?? "/";
  const searchParams = useSearchParams();

  const parsed = useMemo(() => {
    const sp = new URLSearchParams(searchParams?.toString() ?? "");
    const result = parseFilterParams(sp, columns);

    // Apply defaults only when URL has no filters set at all.
    const hasAnyFilter = Object.keys(result.filters).length > 0;
    if (!hasAnyFilter) {
      result.filters = { ...defaultFilters };
    }

    // Apply default sort only when URL omits it.
    if (result.sort === null && defaultSort) {
      result.sort = defaultSort;
    }

    return result;
  }, [searchParams, columns, defaultFilters, defaultSort]);

  const sort = useMemo(() => parseSortString(parsed.sort), [parsed.sort]);

  const visibleColumns = useMemo<readonly string[]>(() => {
    // When a view is active, the parent is expected to sync visibility into
    // localStorage via setVisibleColumns. When no view is active, read from localStorage.
    const stored = readVisibilityFromStorage(tableKey);
    if (stored) {
      return reconcileVisibleColumns(stored, columns);
    }
    return defaultVisibleColumns ?? columnsDefaultVisible(columns);
  }, [tableKey, columns, defaultVisibleColumns]);

  const navigate = useCallback(
    (mutator: (sp: URLSearchParams) => void) => {
      const sp = new URLSearchParams(searchParams?.toString() ?? "");
      mutator(sp);
      const qs = sp.toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      router.replace(url, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  const setFilter = useCallback(
    (key: string, value: FilterValue | null) => {
      navigate((sp) => {
        sp.delete(key);
        sp.delete(`${key}__min`);
        sp.delete(`${key}__max`);
        sp.delete("page");

        if (value === null) return;
        if (value.kind === "multi-select") {
          if (value.values.length === 0) return;
          sp.set(key, value.values.join(","));
        } else if (value.kind === "range") {
          if (value.min !== undefined) sp.set(`${key}__min`, String(value.min));
          if (value.max !== undefined) sp.set(`${key}__max`, String(value.max));
        }
      });
    },
    [navigate]
  );

  const setSort = useCallback(
    (key: string) => {
      navigate((sp) => {
        const next = cycleSortState(sort, key);
        const serialized = serializeSortString(next);
        if (serialized === null) {
          sp.delete("sort");
        } else {
          sp.set("sort", serialized);
        }
      });
    },
    [navigate, sort]
  );

  const setPage = useCallback(
    (nextPage: number) => {
      navigate((sp) => {
        if (nextPage <= 1) {
          sp.delete("page");
        } else {
          sp.set("page", String(nextPage));
        }
      });
    },
    [navigate]
  );

  const setSearch = useCallback(
    (term: string) => {
      navigate((sp) => {
        sp.delete("page");
        if (term.trim().length === 0) {
          sp.delete("search");
        } else {
          sp.set("search", term);
        }
      });
    },
    [navigate]
  );

  const setView = useCallback(
    (nextViewId: string | null) => {
      navigate((sp) => {
        if (nextViewId === null) {
          sp.delete("view");
        } else {
          sp.set("view", nextViewId);
        }
      });
    },
    [navigate]
  );

  const setVisibleColumns = useCallback(
    (keys: readonly string[]) => {
      const reconciled = reconcileVisibleColumns(keys, columns);
      writeVisibilityToStorage(tableKey, reconciled);
      // No URL update — visibility is a local preference unless stored in a view.
      router.refresh();
    },
    [columns, tableKey, router]
  );

  const clearAllFilters = useCallback(() => {
    navigate((sp) => {
      // Delete all filter params defined by the columns
      for (const column of columns) {
        if (!column.filter) continue;
        sp.delete(column.key);
        sp.delete(`${column.key}__min`);
        sp.delete(`${column.key}__max`);
      }
      sp.delete("search");
      sp.delete("page");
    });
  }, [columns, navigate]);

  const serializeCurrent = useCallback((): SerializedTableState => {
    return {
      filters: parsed.filters,
      sort: parsed.sort,
      visibleColumns,
    };
  }, [parsed.filters, parsed.sort, visibleColumns]);

  const isModifiedFromView = useCallback(
    (viewState: SerializedTableState): boolean => {
      const current = canonicalizeState({
        filters: parsed.filters,
        sort: parsed.sort,
        visibleColumns,
      });
      const view = canonicalizeState(viewState);
      return current !== view;
    },
    [parsed.filters, parsed.sort, visibleColumns]
  );

  return {
    filters: parsed.filters,
    sort,
    page: parsed.page,
    search: parsed.search,
    viewId: parsed.viewId,
    visibleColumns,
    setFilter,
    setSort,
    setPage,
    setSearch,
    setView,
    setVisibleColumns,
    clearAllFilters,
    serializeCurrent,
    isModifiedFromView,
  };
}
