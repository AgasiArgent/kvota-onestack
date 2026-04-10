/**
 * Pure functions to parse and serialize DataTable filter state to/from URL parameters.
 *
 * URL format conventions:
 *  - Multi-select filters:  ?<column>=v1,v2,v3  (comma-separated)
 *  - Range filters:         ?<column>__min=100&<column>__max=5000
 *  - Sort:                  ?sort=-<column> (desc) or ?sort=<column> (asc)
 *  - Page:                  ?page=<N> (1-based)
 *  - Search:                ?search=<term>
 *  - Saved view id:         ?view=<uuid>
 *
 * Unknown column keys are silently dropped during parsing (no throw), per R8.8.
 */

import type {
  DataTableColumn,
  FilterValue,
  ParsedTableState,
  SerializedTableState,
} from "@/shared/ui/data-table/types";

const RANGE_MIN_SUFFIX = "__min";
const RANGE_MAX_SUFFIX = "__max";
const RESERVED_KEYS = new Set(["sort", "page", "search", "view"]);

/**
 * Parse a URLSearchParams instance into typed table state.
 *
 * Only filter values for columns present in the column config are retained.
 * This prevents stale URL params (from a removed column) from polluting state.
 */
export function parseFilterParams(
  searchParams: URLSearchParams,
  columns: readonly DataTableColumn<unknown>[]
): ParsedTableState {
  const filters: Record<string, FilterValue> = {};

  for (const column of columns) {
    if (!column.filter) continue;

    if (column.filter.kind === "multi-select") {
      const raw = searchParams.get(column.key);
      if (raw !== null && raw.length > 0) {
        const values = raw
          .split(",")
          .map((v) => v.trim())
          .filter((v) => v.length > 0);
        if (values.length > 0) {
          filters[column.key] = { kind: "multi-select", values };
        }
      }
    } else if (column.filter.kind === "range") {
      const minRaw = searchParams.get(`${column.key}${RANGE_MIN_SUFFIX}`);
      const maxRaw = searchParams.get(`${column.key}${RANGE_MAX_SUFFIX}`);
      const min = parseNumeric(minRaw);
      const max = parseNumeric(maxRaw);
      if (min !== undefined || max !== undefined) {
        filters[column.key] = { kind: "range", min, max };
      }
    }
  }

  const sort = searchParams.get("sort");
  const pageRaw = searchParams.get("page");
  const page = pageRaw ? Math.max(1, Number.parseInt(pageRaw, 10) || 1) : 1;
  const search = searchParams.get("search") ?? "";
  const viewId = searchParams.get("view");

  return {
    filters,
    sort: sort && sort.length > 0 ? sort : null,
    page,
    search,
    viewId: viewId && viewId.length > 0 ? viewId : null,
  };
}

/**
 * Serialize filter values into a URLSearchParams instance (without pagination, sort, etc.).
 *
 * Empty filter values and empty multi-select arrays are omitted entirely.
 */
export function serializeFilters(
  filters: Record<string, FilterValue>
): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (RESERVED_KEYS.has(key)) continue;

    if (value.kind === "multi-select") {
      if (value.values.length === 0) continue;
      params.set(key, value.values.join(","));
    } else if (value.kind === "range") {
      if (value.min !== undefined) {
        params.set(`${key}${RANGE_MIN_SUFFIX}`, String(value.min));
      }
      if (value.max !== undefined) {
        params.set(`${key}${RANGE_MAX_SUFFIX}`, String(value.max));
      }
    }
  }
  return params;
}

/**
 * Produce a canonical string representation of serialized table state.
 *
 * Two states that are logically equivalent (same filters, same sort, same visible columns)
 * produce the same canonical string, regardless of key/value insertion order.
 *
 * Used to detect modifications from an active saved view without false positives.
 */
export function canonicalizeState(state: SerializedTableState): string {
  const canonicalFilters: Record<string, unknown> = {};
  const keys = Object.keys(state.filters).sort();
  for (const key of keys) {
    const value = state.filters[key];
    if (value.kind === "multi-select") {
      canonicalFilters[key] = {
        kind: "multi-select",
        values: [...value.values].sort(),
      };
    } else if (value.kind === "range") {
      canonicalFilters[key] = {
        kind: "range",
        min: value.min ?? null,
        max: value.max ?? null,
      };
    }
  }

  const canonical = {
    filters: canonicalFilters,
    sort: state.sort ?? null,
    visibleColumns: [...state.visibleColumns].sort(),
  };

  return JSON.stringify(canonical);
}

function parseNumeric(raw: string | null): number | undefined {
  if (raw === null || raw.length === 0) return undefined;
  const n = Number(raw);
  return Number.isFinite(n) ? n : undefined;
}

/**
 * Parse a URL-format sort string like "-amount" or "created_at" into structured form.
 * Returns null when the sort string is empty or invalid.
 */
export function parseSortString(sort: string | null): { key: string; direction: "asc" | "desc" } | null {
  if (!sort || sort.length === 0) return null;
  if (sort.startsWith("-")) {
    const key = sort.slice(1);
    if (key.length === 0) return null;
    return { key, direction: "desc" };
  }
  return { key: sort, direction: "asc" };
}

/**
 * Serialize a structured sort into a URL-format sort string.
 */
export function serializeSortString(sort: { key: string; direction: "asc" | "desc" } | null): string | null {
  if (!sort) return null;
  return sort.direction === "desc" ? `-${sort.key}` : sort.key;
}

/**
 * Compute the next sort state given the current state and a clicked column key.
 * Tri-state cycle: null → asc → desc → null.
 */
export function cycleSortState(
  current: { key: string; direction: "asc" | "desc" } | null,
  clickedKey: string
): { key: string; direction: "asc" | "desc" } | null {
  if (!current || current.key !== clickedKey) {
    return { key: clickedKey, direction: "asc" };
  }
  if (current.direction === "asc") {
    return { key: clickedKey, direction: "desc" };
  }
  return null;
}
