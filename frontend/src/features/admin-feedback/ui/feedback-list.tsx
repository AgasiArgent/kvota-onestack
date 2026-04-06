"use client";

import { Fragment, useState, useRef, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { ExternalLink, Search } from "lucide-react";
import { Pagination } from "@/shared/ui/pagination";
import { useFilterNavigation } from "@/shared/lib/use-filter-navigation";
import { toast } from "sonner";
import type { FeedbackItem } from "@/entities/admin/types";
import {
  FEEDBACK_TYPE_LABELS,
  FEEDBACK_TYPE_COLORS,
  FEEDBACK_STATUS_LABELS,
  FEEDBACK_STATUS_COLORS,
} from "@/entities/admin/types";
import { updateFeedbackStatus, bulkUpdateFeedbackStatus } from "@/entities/admin/mutations";
import {
  useReactTable,
  getCoreRowModel,
  getExpandedRowModel,
  flexRender,
  type ColumnDef,
  type ExpandedState,
  type RowSelectionState,
} from "@tanstack/react-table";
import { FeedbackExpandedRow } from "./feedback-expanded-row";

interface FeedbackListProps {
  items: FeedbackItem[];
  total: number;
  page: number;
  pageSize: number;
  activeStatus: string | null;
  searchQuery: string;
}

const STATUS_TABS = [
  { value: null, label: "Все" },
  { value: "new", label: "Новые" },
  { value: "in_progress", label: "В работе" },
  { value: "resolved", label: "Решено" },
  { value: "closed", label: "Закрыто" },
] as const;

const STATUS_OPTIONS = ["new", "in_progress", "resolved", "closed"] as const;

const PAGE_SIZE_OPTIONS = [
  { value: "25", label: "25" },
  { value: "50", label: "50" },
  { value: "100", label: "100" },
] as const;

const DEFAULT_PAGE_SIZE = 50;

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function buildUrl(
  status: string | null,
  search: string,
  page?: number,
  pageSize?: number
): string {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (search) params.set("search", search);
  if (page && page > 1) params.set("page", String(page));
  if (pageSize && pageSize !== DEFAULT_PAGE_SIZE) params.set("pageSize", String(pageSize));
  const qs = params.toString();
  return qs ? `/admin/feedback?${qs}` : "/admin/feedback";
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function FeedbackList({
  items,
  total,
  page,
  pageSize,
  activeStatus,
  searchQuery,
}: FeedbackListProps) {
  const router = useRouter();
  const totalPages = Math.ceil(total / pageSize);
  const [searchValue, setSearchValue] = useState(searchQuery);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined
  );
  const { navigate } = useFilterNavigation();

  // Optimistic status state: shortId -> pending status
  const [optimisticStatuses, setOptimisticStatuses] = useState<
    Map<string, string>
  >(new Map());

  // TanStack state
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});

  // Bulk toolbar state
  const [bulkTargetStatus, setBulkTargetStatus] = useState<string | null>(null);
  const [bulkUpdating, setBulkUpdating] = useState(false);

  // Derive items with optimistic statuses applied
  const displayItems = useMemo(() => {
    if (optimisticStatuses.size === 0) return items;
    return items.map((item) => {
      const pending = optimisticStatuses.get(item.short_id);
      if (pending) {
        return { ...item, status: pending as FeedbackItem["status"] };
      }
      return item;
    });
  }, [items, optimisticStatuses]);

  const handleStatusChange = useCallback(
    async (shortId: string, newStatus: string) => {
      // Optimistic update
      setOptimisticStatuses((prev) => {
        const next = new Map(prev);
        next.set(shortId, newStatus);
        return next;
      });

      try {
        await updateFeedbackStatus(shortId, newStatus);
        // On success, clear from optimistic state and refresh server data
        setOptimisticStatuses((prev) => {
          const next = new Map(prev);
          next.delete(shortId);
          return next;
        });
        router.refresh();
      } catch {
        // Revert
        setOptimisticStatuses((prev) => {
          const next = new Map(prev);
          next.delete(shortId);
          return next;
        });
        toast.error("Ошибка при обновлении статуса");
      }
    },
    [router]
  );

  const columns: ColumnDef<FeedbackItem>[] = useMemo(
    () => [
      // Checkbox column
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            onCheckedChange={(value) =>
              table.toggleAllPageRowsSelected(!!value)
            }
            aria-label="Выбрать все"
            onClick={(e) => e.stopPropagation()}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(value) => row.toggleSelected(!!value)}
            aria-label={`Выбрать ${row.original.short_id}`}
            onClick={(e) => e.stopPropagation()}
          />
        ),
        size: 40,
        enableSorting: false,
      },
      // ID
      {
        accessorKey: "short_id",
        header: "ID",
        cell: ({ row }) => (
          <span className="font-mono text-xs">{row.original.short_id}</span>
        ),
        size: 100,
      },
      // Type badge
      {
        accessorKey: "feedback_type",
        header: "Тип",
        cell: ({ row }) => {
          const typeColor =
            FEEDBACK_TYPE_COLORS[row.original.feedback_type] ??
            "bg-slate-100 text-slate-700";
          return (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeColor}`}
            >
              {FEEDBACK_TYPE_LABELS[row.original.feedback_type] ??
                row.original.feedback_type}
            </span>
          );
        },
        size: 90,
      },
      // Description (truncated)
      {
        accessorKey: "description",
        header: "Описание",
        cell: ({ row }) => (
          <span
            className="max-w-[300px] truncate block"
            title={row.original.description}
          >
            {truncate(row.original.description, 80)}
          </span>
        ),
      },
      // User
      {
        id: "user",
        header: "Пользователь",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground truncate max-w-[180px] block">
            {row.original.user_email ?? row.original.user_name ?? "\u2014"}
          </span>
        ),
        size: 180,
      },
      // Status dropdown
      {
        accessorKey: "status",
        header: "Статус",
        cell: ({ row }) => {
          const displayStatus =
            optimisticStatuses.get(row.original.short_id) ??
            row.original.status;
          const statusColor =
            FEEDBACK_STATUS_COLORS[displayStatus] ??
            "bg-slate-100 text-slate-700";
          return (
            <div onClick={(e) => e.stopPropagation()}>
              <Select
                value={displayStatus}
                onValueChange={(v) => {
                  if (v && v !== displayStatus) {
                    handleStatusChange(row.original.short_id, v);
                  }
                }}
              >
                <SelectTrigger
                  size="sm"
                  className={`h-7 text-xs font-medium border-0 ${statusColor}`}
                >
                  <SelectValue>
                    {FEEDBACK_STATUS_LABELS[displayStatus] ?? displayStatus}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((s) => (
                    <SelectItem key={s} value={s}>
                      {FEEDBACK_STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          );
        },
        size: 140,
      },
      // ClickUp link
      {
        id: "clickup",
        header: "ClickUp",
        cell: ({ row }) =>
          row.original.clickup_task_id ? (
            <a
              href={`https://app.clickup.com/t/${row.original.clickup_task_id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:text-accent-hover"
              onClick={(e) => e.stopPropagation()}
              title="Открыть в ClickUp"
            >
              <ExternalLink size={14} />
            </a>
          ) : (
            <span className="text-muted-foreground">{"\u2014"}</span>
          ),
        size: 90,
      },
      // Date
      {
        accessorKey: "created_at",
        header: "Дата",
        cell: ({ row }) => (
          <span className="text-muted-foreground tabular-nums">
            {formatDate(row.original.created_at)}
          </span>
        ),
        size: 100,
      },
    ],
    [optimisticStatuses, handleStatusChange]
  );

  const table = useReactTable({
    data: displayItems,
    columns,
    state: {
      expanded,
      rowSelection,
    },
    onExpandedChange: setExpanded,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    getRowId: (row) => row.short_id,
    enableRowSelection: true,
  });

  const selectedCount = Object.keys(rowSelection).length;

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      navigate({ search: value || undefined });
    }, 300);
  }

  function handleRowClick(rowId: string, event: React.MouseEvent) {
    // Skip if clicking interactive elements
    const target = event.target as HTMLElement;
    if (
      target.closest("a") ||
      target.closest("button") ||
      target.closest('[data-slot="checkbox"]') ||
      target.closest('[data-slot="select-trigger"]') ||
      target.closest('[data-slot="select-content"]')
    ) {
      return;
    }

    setExpanded((prev) => {
      const isCurrentlyExpanded =
        typeof prev === "object" && (prev as Record<string, boolean>)[rowId];
      if (isCurrentlyExpanded) {
        return {};
      }
      return { [rowId]: true };
    });
  }

  function handleRowKeyDown(rowId: string, event: React.KeyboardEvent) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setExpanded((prev) => {
        const isCurrentlyExpanded =
          typeof prev === "object" && (prev as Record<string, boolean>)[rowId];
        if (isCurrentlyExpanded) {
          return {};
        }
        return { [rowId]: true };
      });
    }
  }

  async function handleBulkUpdate() {
    if (!bulkTargetStatus || selectedCount === 0) return;

    const selectedShortIds = Object.keys(rowSelection);
    setBulkUpdating(true);

    try {
      await bulkUpdateFeedbackStatus(
        selectedShortIds,
        bulkTargetStatus as "new" | "in_progress" | "resolved" | "closed"
      );
      setRowSelection({});
      setBulkTargetStatus(null);
      toast.success(`Обновлено ${selectedShortIds.length} обращений`);
      router.refresh();
    } catch {
      toast.error("Ошибка при массовом обновлении");
    } finally {
      setBulkUpdating(false);
    }
  }

  function handlePageSizeChange(newSize: string | null) {
    if (!newSize) return;
    setRowSelection({});
    navigate({ pageSize: newSize === String(DEFAULT_PAGE_SIZE) ? undefined : newSize });
  }

  function buildPaginationHref(p: number): string {
    return buildUrl(activeStatus, searchQuery, p, pageSize);
  }

  const columnCount = columns.length;

  return (
    <div className="space-y-4">
      {/* Status filter tabs */}
      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => {
          const isActive =
            tab.value === activeStatus ||
            (tab.value === null && !activeStatus);
          return (
            <Link
              key={tab.value ?? "all"}
              href={buildUrl(tab.value, searchQuery, undefined, pageSize)}
              className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Search */}
      <div className="flex gap-2 max-w-md">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по описанию, email или ID..."
            className="pl-9"
          />
        </div>
      </div>

      {/* Stats */}
      <div className="text-sm text-muted-foreground">Всего: {total}</div>

      {/* Bulk action toolbar */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg border">
          <span className="text-sm font-medium">
            {selectedCount} выбрано
          </span>
          <Select
            value={bulkTargetStatus ?? undefined}
            onValueChange={(v) => setBulkTargetStatus(v || null)}
          >
            <SelectTrigger size="sm" className="w-[160px]">
              <SelectValue placeholder="Выберите статус" />
            </SelectTrigger>
            <SelectContent>
              {STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {FEEDBACK_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            onClick={handleBulkUpdate}
            disabled={!bulkTargetStatus || bulkUpdating}
          >
            {bulkUpdating ? "Обновление..." : "Применить"}
          </Button>
          <button
            type="button"
            className="text-sm text-muted-foreground hover:text-foreground"
            onClick={() => {
              setRowSelection({});
              setBulkTargetStatus(null);
            }}
          >
            Снять выделение
          </button>
        </div>
      )}

      {/* Table */}
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead
                  key={header.id}
                  style={{ width: header.getSize() }}
                >
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.length > 0 ? (
            table.getRowModel().rows.map((row) => (
              <Fragment key={row.id}>
                <TableRow
                  className="cursor-pointer"
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  tabIndex={0}
                  onClick={(e) => handleRowClick(row.id, e)}
                  onKeyDown={(e) => handleRowKeyDown(row.id, e)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
                {row.getIsExpanded() && (
                  <TableRow>
                    <TableCell colSpan={columnCount} className="p-0">
                      <FeedbackExpandedRow shortId={row.original.short_id} />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            ))
          ) : (
            <TableRow>
              <TableCell
                colSpan={columnCount}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет обращений</p>
                  {(activeStatus || searchQuery) && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/admin/feedback"
                        className="text-accent hover:underline"
                      >
                        сбросить фильтры
                      </Link>
                    </p>
                  )}
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination + page size */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>Показывать:</span>
          <Select
            value={String(pageSize)}
            onValueChange={handlePageSizeChange}
          >
            <SelectTrigger size="sm" className="w-[70px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PAGE_SIZE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          totalItems={total}
          itemLabel="обращений"
          buildHref={buildPaginationHref}
        />
      </div>
    </div>
  );
}
