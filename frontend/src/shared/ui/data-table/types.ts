import type { ReactNode } from "react";

/**
 * Discriminated union of filter shapes that the DataTable understands.
 * Stored in URL as comma-separated values (multi-select, grouped-multi-select)
 * or __min/__max suffixes (range). The optional __logic suffix controls
 * AND/OR semantics for grouped filters.
 */
export type FilterValue =
  | { kind: "multi-select"; values: readonly string[] }
  | { kind: "range"; min?: number; max?: number }
  | {
      kind: "grouped-multi-select";
      /** Composite values in the form "<group>:<id>". */
      values: readonly string[];
      /** Default "or" — any participant match wins. "and" requires all selected to match. */
      logic?: "or" | "and";
    };

/**
 * Declares the type of filter a column supports.
 * Options for multi-select filters come from DataTableProps.filterOptions
 * keyed by the column's `key`.
 */
export type ColumnFilterType =
  | { kind: "multi-select" }
  | { kind: "range"; unit?: string }
  | {
      kind: "grouped-multi-select";
      /**
       * Map of group key → human-readable label. The filter popover renders
       * one collapsible section per group; option.group decides membership.
       */
      groups: Record<string, string>;
    };

export interface FilterOption {
  value: string;
  label: string;
  /** Group key — matches a key in ColumnFilterType.groups for grouped filters. */
  group?: string;
}

export type FilterOptions = Record<string, readonly FilterOption[]>;

/**
 * Column descriptor. Consumers declare one per visible column.
 * Generic `T` is the row type.
 */
export interface DataTableColumn<T> {
  /** Unique key — also the URL query param name for this column's filter and sort. */
  key: string;
  /** Header label displayed to users. */
  label: string;
  /** Returns the cell content for a given row. Keep it pure. */
  accessor: (row: T) => ReactNode;
  /** When true, the header is clickable to cycle sort direction. */
  sortable?: boolean;
  /** Database column key for ORDER BY; defaults to `key` if omitted. */
  sortKey?: string;
  /** Enables a column filter popover on this column's header. */
  filter?: ColumnFilterType;
  /** CSS width hint for the column. */
  width?: string;
  /** Text alignment within cells. */
  align?: "left" | "center" | "right";
  /** Reserved for future role-based column hiding. Not enforced in current release. */
  allowedRoles?: readonly string[];
  /** When false, the column is hidden by default for new users. Defaults to true. */
  defaultVisible?: boolean;
  /** When true, the column cannot be toggled via the column visibility popover. */
  alwaysVisible?: boolean;
}

/**
 * Serialized table state suitable for persistence (saved views) and for comparing
 * the active view against the current URL state to detect modifications.
 */
export interface SerializedTableState {
  filters: Record<string, FilterValue>;
  sort: string | null; // URL-format e.g. "-amount" or "created_at"
  visibleColumns: readonly string[];
}

export interface SortState {
  key: string;
  direction: "asc" | "desc";
}

/**
 * Shape of the parsed table state read from a URL.
 * Includes pagination and search which are not stored in saved views directly
 * but are still part of the live URL.
 */
export interface ParsedTableState {
  filters: Record<string, FilterValue>;
  sort: string | null;
  page: number;
  search: string;
  viewId: string | null;
}
