"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

import { cn } from "@/lib/utils";

import { ColumnFilter } from "./column-filter";
import { RangeFilter } from "./range-filter";
import type {
  DataTableColumn,
  FilterOption,
  FilterValue,
  SortState,
} from "./types";

interface ColumnHeaderProps<T> {
  column: DataTableColumn<T>;
  sortState: SortState | null;
  onSortChange: (key: string) => void;
  filterValue: FilterValue | undefined;
  onFilterChange: (key: string, value: FilterValue | null) => void;
  /** Options for multi-select filters — ignored for range filters. */
  options?: readonly FilterOption[];
}

/**
 * Per-column header cell.
 *
 * Composes the column label with an optional sort toggle and an optional
 * filter trigger. Filter trigger delegates rendering to ColumnFilter
 * (multi-select) or RangeFilter (range) based on the column's filter config.
 *
 * The component is purely presentational — it emits sort and filter changes
 * via callbacks; the parent (DataTable) wires those to useTableState.
 */
export function ColumnHeader<T>({
  column,
  sortState,
  onSortChange,
  filterValue,
  onFilterChange,
  options,
}: ColumnHeaderProps<T>) {
  const sortKey = column.sortKey ?? column.key;
  const isActiveSortColumn = sortState?.key === sortKey;
  const sortDirection = isActiveSortColumn ? sortState?.direction : null;

  const alignment =
    column.align === "right"
      ? "justify-end"
      : column.align === "center"
        ? "justify-center"
        : "justify-start";

  function renderSortIcon() {
    if (!column.sortable) return null;
    if (sortDirection === "asc") return <ArrowUp size={12} />;
    if (sortDirection === "desc") return <ArrowDown size={12} />;
    return <ArrowUpDown size={12} className="opacity-40" />;
  }

  function renderFilter() {
    if (!column.filter) return null;

    if (column.filter.kind === "multi-select") {
      const selected =
        filterValue?.kind === "multi-select" ? filterValue.values : [];
      return (
        <ColumnFilter
          columnKey={column.key}
          title={column.label}
          options={options ?? []}
          selected={selected}
          onApply={(values) =>
            onFilterChange(
              column.key,
              values.length > 0 ? { kind: "multi-select", values } : null
            )
          }
          onReset={() => onFilterChange(column.key, null)}
        />
      );
    }

    if (column.filter.kind === "range") {
      const range =
        filterValue?.kind === "range"
          ? { min: filterValue.min, max: filterValue.max }
          : undefined;
      return (
        <RangeFilter
          columnKey={column.key}
          title={column.label}
          unit={column.filter.unit}
          value={range}
          onApply={(value) =>
            onFilterChange(
              column.key,
              value.min === undefined && value.max === undefined
                ? null
                : { kind: "range", ...value }
            )
          }
          onReset={() => onFilterChange(column.key, null)}
        />
      );
    }

    return null;
  }

  const labelNode = column.sortable ? (
    <button
      type="button"
      onClick={() => onSortChange(sortKey)}
      className="inline-flex items-center gap-1 hover:text-foreground transition-colors"
    >
      {column.label}
      {renderSortIcon()}
    </button>
  ) : (
    <span>{column.label}</span>
  );

  return (
    <div className={cn("flex items-center gap-1", alignment)}>
      {labelNode}
      {renderFilter()}
    </div>
  );
}
