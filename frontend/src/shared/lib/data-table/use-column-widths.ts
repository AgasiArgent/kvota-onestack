"use client";

import { useCallback, useEffect, useState } from "react";

import type { DataTableColumn } from "@/shared/ui/data-table/types";

const WIDTH_STORAGE_PREFIX = "oneStack.dataTable";
const MIN_COLUMN_WIDTH = 60;
const MAX_COLUMN_WIDTH = 800;

function widthStorageKey(tableKey: string): string {
  return `${WIDTH_STORAGE_PREFIX}.${tableKey}.columnWidths`;
}

function readWidthsFromStorage(tableKey: string): Record<string, number> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(widthStorageKey(tableKey));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null) return {};
    const result: Record<string, number> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "number" && Number.isFinite(value)) {
        result[key] = value;
      }
    }
    return result;
  } catch {
    return {};
  }
}

function writeWidthsToStorage(
  tableKey: string,
  widths: Record<string, number>
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      widthStorageKey(tableKey),
      JSON.stringify(widths)
    );
  } catch {
    // Storage unavailable — silently ignore.
  }
}

/**
 * Parse a CSS width string like "140px" into a plain number.
 * Returns undefined for values we can't parse (percentages, auto, etc.).
 */
function parseCssWidth(raw: string | undefined): number | undefined {
  if (!raw) return undefined;
  const match = raw.match(/^(\d+(?:\.\d+)?)px$/);
  if (!match) return undefined;
  return Number.parseFloat(match[1]);
}

interface UseColumnWidthsArgs<T> {
  tableKey: string;
  columns: readonly DataTableColumn<T>[];
}

interface UseColumnWidthsResult {
  /** Map of column key → current width in pixels. */
  widths: Record<string, number>;
  /** Set a single column's width. Persists to localStorage. */
  setWidth: (columnKey: string, widthPx: number) => void;
  /** Clear all overrides for this table (reverts to column config defaults). */
  resetWidths: () => void;
}

/**
 * Hook managing per-column width overrides with localStorage persistence.
 *
 * Initial widths come from column config (`column.width: "140px"`). User
 * drags override those and are stored in localStorage keyed by tableKey.
 * On mount, stored overrides merge over config defaults — unknown keys
 * from stored state (referring to removed columns) are silently dropped.
 *
 * Width constraints: MIN_COLUMN_WIDTH <= width <= MAX_COLUMN_WIDTH.
 */
export function useColumnWidths<T>({
  tableKey,
  columns,
}: UseColumnWidthsArgs<T>): UseColumnWidthsResult {
  // Start with config defaults parsed from column.width strings.
  const configDefaults: Record<string, number> = {};
  for (const column of columns) {
    const parsed = parseCssWidth(column.width);
    if (parsed !== undefined) {
      configDefaults[column.key] = parsed;
    }
  }

  const [widths, setWidths] = useState<Record<string, number>>(configDefaults);

  // Merge stored overrides on mount (client-side only to avoid SSR mismatch).
  useEffect(() => {
    const stored = readWidthsFromStorage(tableKey);
    const known = new Set(columns.map((c) => c.key));
    const merged: Record<string, number> = { ...configDefaults };
    for (const [key, value] of Object.entries(stored)) {
      if (known.has(key)) {
        merged[key] = Math.max(MIN_COLUMN_WIDTH, Math.min(MAX_COLUMN_WIDTH, value));
      }
    }
    setWidths(merged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableKey]);

  const setWidth = useCallback(
    (columnKey: string, widthPx: number) => {
      const clamped = Math.max(
        MIN_COLUMN_WIDTH,
        Math.min(MAX_COLUMN_WIDTH, Math.round(widthPx))
      );
      setWidths((prev) => {
        const next = { ...prev, [columnKey]: clamped };
        // Persist only the user overrides (we store everything for simplicity —
        // extraction of only "non-default" values would add complexity without
        // payoff since the total stored object is tiny).
        writeWidthsToStorage(tableKey, next);
        return next;
      });
    },
    [tableKey]
  );

  const resetWidths = useCallback(() => {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(widthStorageKey(tableKey));
      } catch {
        // Ignore storage errors.
      }
    }
    setWidths(configDefaults);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tableKey]);

  return { widths, setWidth, resetWidths };
}
