"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Search, X } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Pagination } from "@/shared/ui/pagination";
import { useTableState } from "@/shared/lib/data-table";
import { useColumnWidths } from "@/shared/lib/data-table/use-column-widths";
import type { TableView } from "@/entities/table-view";

import { ColumnHeader } from "./column-header";
import { ColumnVisibility } from "./column-visibility";
import { ViewSelector } from "./view-selector";
import type {
  DataTableColumn,
  FilterOptions,
  FilterValue,
} from "./types";

export interface DataTableProps<T> {
  /** Identifier for views scope and localStorage key, e.g. "quotes". */
  tableKey: string;

  /** Rows to render (server-paginated — the parent owns the query). */
  rows: readonly T[];
  total: number;
  page: number;
  pageSize: number;
  rowKey: (row: T) => string;

  /** Column config and filter option lookups. */
  columns: readonly DataTableColumn<T>[];
  filterOptions?: FilterOptions;

  /** Default filters applied when URL has no filters set. */
  defaultFilters?: Record<string, FilterValue>;
  /** Default sort applied when URL omits sort. Format: "-amount" or "created_at". */
  defaultSort?: string;

  /** Navigate on row click. */
  onRowClick?: (row: T) => void;

  /** Search input config. */
  search?: {
    placeholder?: string;
  };

  /** Row grouping: matching rows are rendered above the rest with a labeled header. */
  rowGrouping?: {
    label: string;
    predicate: (row: T) => boolean;
  };

  /** Top-bar slot on the right (e.g., "Create new" button). */
  topBarActions?: React.ReactNode;

  /** Empty state content when rows.length === 0. */
  emptyState?: React.ReactNode;

  /** Enable saved views selector in the top bar. Requires currentUserId. */
  viewsEnabled?: boolean;
  currentUserId?: string;

  /** URL path for building pagination href, e.g. "/quotes". Required for pagination. */
  basePath: string;
}

const SEARCH_DEBOUNCE_MS = 300;

/**
 * Reusable DataTable shell.
 *
 * Wraps table rendering, top bar (search + view selector + column visibility +
 * custom actions), per-column filter/sort headers, row grouping, pagination,
 * and empty state. State lives in the URL via useTableState; the consumer is
 * responsible for fetching rows based on that state.
 */
export function DataTable<T>({
  tableKey,
  rows,
  total,
  page,
  pageSize,
  rowKey,
  columns,
  filterOptions = {},
  defaultFilters,
  defaultSort,
  onRowClick,
  search,
  rowGrouping,
  topBarActions,
  emptyState,
  viewsEnabled = false,
  currentUserId,
  basePath,
}: DataTableProps<T>) {
  // Cast columns to the untyped variant for useTableState — the hook uses
  // column.key/filter config but does not touch the row type.
  const untypedColumns = columns as unknown as readonly DataTableColumn<unknown>[];

  const state = useTableState({
    columns: untypedColumns,
    tableKey,
    defaultFilters,
    defaultSort,
  });

  // Column widths with localStorage persistence
  const { widths, setWidth } = useColumnWidths({ tableKey, columns });

  // Resize state
  const [resizingKey, setResizingKey] = useState<string | null>(null);
  const resizeStateRef = useRef<{
    columnKey: string;
    startX: number;
    startWidth: number;
  } | null>(null);

  const handleResizePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>, columnKey: string) => {
      e.preventDefault();
      e.stopPropagation();
      const currentWidth = widths[columnKey] ?? 100;
      resizeStateRef.current = {
        columnKey,
        startX: e.clientX,
        startWidth: currentWidth,
      };
      setResizingKey(columnKey);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [widths]
  );

  const handleResizePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const resizeState = resizeStateRef.current;
      if (!resizeState) return;
      const delta = e.clientX - resizeState.startX;
      const nextWidth = resizeState.startWidth + delta;
      setWidth(resizeState.columnKey, nextWidth);
    },
    [setWidth]
  );

  const handleResizePointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      if (resizeStateRef.current) {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
        resizeStateRef.current = null;
        setResizingKey(null);
      }
    },
    []
  );

  // Debounced search
  const [searchInput, setSearchInput] = useState(state.search);
  const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync local search input when URL changes externally (browser back, view load).
  useEffect(() => {
    setSearchInput(state.search);
  }, [state.search]);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchInput(value);
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
      searchTimerRef.current = setTimeout(() => {
        state.setSearch(value);
      }, SEARCH_DEBOUNCE_MS);
    },
    [state]
  );

  // Filter visible columns
  const visibleColumns = useMemo(() => {
    const visibleSet = new Set(state.visibleColumns);
    return columns.filter((c) => c.alwaysVisible || visibleSet.has(c.key));
  }, [columns, state.visibleColumns]);

  // Row grouping: split into action rows and rest
  const { actionRows, otherRows } = useMemo(() => {
    if (!rowGrouping) {
      return { actionRows: [] as T[], otherRows: [...rows] };
    }
    const action: T[] = [];
    const other: T[] = [];
    for (const row of rows) {
      if (rowGrouping.predicate(row)) action.push(row);
      else other.push(row);
    }
    return { actionRows: action, otherRows: other };
  }, [rows, rowGrouping]);

  const totalPages = Math.ceil(total / pageSize);
  const colSpan = visibleColumns.length;

  function buildPageHref(p: number): string {
    const sp = new URLSearchParams();
    // Preserve current filter/sort/view URL params (read from useTableState indirectly via window location).
    if (typeof window !== "undefined") {
      const current = new URLSearchParams(window.location.search);
      for (const [k, v] of current.entries()) {
        if (k !== "page") sp.set(k, v);
      }
    }
    if (p > 1) sp.set("page", String(p));
    const qs = sp.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  }

  // Serialize current state for view detection
  const serializedState = state.serializeCurrent();

  // View loading handler
  const handleLoadView = useCallback(
    (view: TableView) => {
      // Clear existing URL, then populate from view + set ?view= param
      const sp = new URLSearchParams();

      // Apply filter params from view
      for (const [key, value] of Object.entries(view.filters)) {
        if (value.kind === "multi-select") {
          if (value.values.length > 0) sp.set(key, value.values.join(","));
        } else if (value.kind === "range") {
          if (value.min !== undefined) sp.set(`${key}__min`, String(value.min));
          if (value.max !== undefined) sp.set(`${key}__max`, String(value.max));
        }
      }

      if (view.sort) sp.set("sort", view.sort);
      sp.set("view", view.id);

      // Persist visibility to localStorage via setVisibleColumns
      state.setVisibleColumns(view.visibleColumns);

      const qs = sp.toString();
      const url = qs ? `${basePath}?${qs}` : basePath;
      if (typeof window !== "undefined") {
        window.history.replaceState({}, "", url);
        window.location.reload();
      }
    },
    [basePath, state]
  );

  const handleClearView = useCallback(() => {
    state.setView(null);
  }, [state]);

  const hasActiveFilters = Object.keys(state.filters).length > 0;
  const showClearFilters = hasActiveFilters || state.search.length > 0;

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            size={16}
          />
          <Input
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder={search?.placeholder ?? "Поиск..."}
            className="pl-9 pr-8"
          />
          {searchInput.length > 0 && (
            <button
              type="button"
              onClick={() => handleSearchChange("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Очистить поиск"
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Saved views selector */}
        {viewsEnabled && currentUserId && (
          <ViewSelector
            tableKey={tableKey}
            currentUserId={currentUserId}
            activeViewId={state.viewId}
            currentState={serializedState}
            onLoadView={handleLoadView}
            onClearView={handleClearView}
          />
        )}

        {/* Column visibility */}
        <ColumnVisibility
          columns={columns}
          visibleKeys={state.visibleColumns}
          onChange={state.setVisibleColumns}
        />

        {/* Custom top-bar actions slot (e.g., New KP button) */}
        {topBarActions && <div className="ml-auto">{topBarActions}</div>}
      </div>

      {/* Stats row + clear filters */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Всего: {total}</span>
        {showClearFilters && (
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              state.clearAllFilters();
            }}
          >
            <X size={12} />
            Очистить фильтры
          </Button>
        )}
      </div>

      {/* Table */}
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            {visibleColumns.map((column) => (
              <TableHead
                key={column.key}
                style={
                  widths[column.key]
                    ? { width: widths[column.key], minWidth: widths[column.key] }
                    : undefined
                }
                className={cn(
                  "relative select-none",
                  column.align === "right" && "text-right",
                  column.align === "center" && "text-center"
                )}
              >
                <ColumnHeader
                  column={column}
                  sortState={state.sort}
                  onSortChange={state.setSort}
                  filterValue={state.filters[column.key]}
                  onFilterChange={state.setFilter}
                  options={filterOptions[column.key]}
                />
                {/* Column resize handle — 4px hit area, 1px visual line on hover */}
                <div
                  role="separator"
                  aria-orientation="vertical"
                  aria-label={`Изменить ширину колонки ${column.label}`}
                  onPointerDown={(e) => handleResizePointerDown(e, column.key)}
                  onPointerMove={handleResizePointerMove}
                  onPointerUp={handleResizePointerUp}
                  className={cn(
                    "absolute top-0 right-0 h-full w-1 cursor-col-resize group/resize",
                    "hover:bg-accent/40 transition-colors",
                    resizingKey === column.key && "bg-accent"
                  )}
                />
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {/* Action row group */}
          {rowGrouping && actionRows.length > 0 && (
            <>
              <TableRow className="hover:bg-transparent bg-accent-subtle/50">
                <TableCell colSpan={colSpan} className="py-3 px-0">
                  <div className="border-l-4 border-accent pl-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                    <AlertCircle size={16} className="text-accent shrink-0" />
                    {rowGrouping.label} ({actionRows.length})
                  </div>
                </TableCell>
              </TableRow>
              {actionRows.map((row) => (
                <DataTableRow
                  key={rowKey(row)}
                  row={row}
                  columns={visibleColumns}
                  onClick={onRowClick}
                />
              ))}
              {otherRows.length > 0 && (
                <>
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={colSpan} className="py-2 px-0">
                      <div className="border-t border-border" />
                    </TableCell>
                  </TableRow>
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={colSpan} className="py-2 px-0">
                      <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                        Остальные
                      </span>
                    </TableCell>
                  </TableRow>
                </>
              )}
            </>
          )}

          {/* Other rows */}
          {otherRows.map((row) => (
            <DataTableRow
              key={rowKey(row)}
              row={row}
              columns={visibleColumns}
              onClick={onRowClick}
            />
          ))}

          {/* Empty state */}
          {rows.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={colSpan}
                className="text-center py-12 text-muted-foreground"
              >
                {emptyState ?? <div>Нет записей</div>}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      <Pagination
        currentPage={page}
        totalPages={totalPages}
        totalItems={total}
        buildHref={buildPageHref}
      />
    </div>
  );
}

/**
 * Single row renderer — extracted so hook invocations in the row don't
 * leak into the parent render loop.
 */
function DataTableRow<T>({
  row,
  columns,
  onClick,
}: {
  row: T;
  columns: readonly DataTableColumn<T>[];
  onClick?: (row: T) => void;
}) {
  return (
    <TableRow
      className={onClick ? "cursor-pointer" : undefined}
      onClick={onClick ? () => onClick(row) : undefined}
    >
      {columns.map((column) => (
        <TableCell
          key={column.key}
          className={
            column.align === "right"
              ? "text-right"
              : column.align === "center"
                ? "text-center"
                : undefined
          }
        >
          {column.accessor(row)}
        </TableCell>
      ))}
    </TableRow>
  );
}
