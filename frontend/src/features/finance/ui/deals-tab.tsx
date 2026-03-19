"use client";

import { useState } from "react";
import Link from "next/link";
import { Download } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  DealListItem,
  DealSummary,
  DealsFilterParams,
} from "@/entities/finance/types";
import {
  DEAL_STATUS_LABELS,
  DEAL_STATUS_COLORS,
} from "@/entities/finance/types";

interface DealsTabProps {
  deals: DealListItem[];
  summary: DealSummary;
  total: number;
  page: number;
  pageSize: number;
  filters: DealsFilterParams;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "---";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return "---";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatProfit(profit: number | null): {
  text: string;
  className: string;
} {
  if (profit === null || profit === undefined || profit === 0) {
    return { text: "---", className: "text-muted-foreground" };
  }
  const text = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(profit);
  if (profit > 0) return { text, className: "text-green-600" };
  return { text, className: "text-red-600" };
}

function buildFilterUrl(
  baseFilters: DealsFilterParams,
  overrides: Partial<DealsFilterParams & { view?: string }>
): string {
  const merged = { ...baseFilters, ...overrides };
  const params = new URLSearchParams();
  params.set("tab", "deals");
  if (merged.status) params.set("status", merged.status);
  if (merged.page && merged.page > 1) params.set("page", String(merged.page));
  return `/finance?${params.toString()}`;
}

const STATUS_PILLS = [
  { value: undefined, label: "Все" },
  { value: "active", label: "В работе" },
  { value: "completed", label: "Завершённые" },
  { value: "cancelled", label: "Отменённые" },
] as const;

function SummaryCard({
  label,
  count,
  total,
  color,
}: {
  label: string;
  count: number;
  total: number;
  color: string;
}) {
  return (
    <div className={`rounded-lg border p-4 ${color}`}>
      <div className="text-sm text-muted-foreground">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{count}</div>
      <div className="text-sm text-muted-foreground tabular-nums">
        {formatAmount(total)}
      </div>
    </div>
  );
}

export function DealsTab({
  deals,
  summary,
  total,
  page,
  pageSize,
  filters,
}: DealsTabProps) {
  const [viewMode, setViewMode] = useState<"compact" | "expanded">("compact");
  const totalPages = Math.ceil(total / pageSize);

  function handleRowClick(dealId: string) {
    window.location.href = `https://kvotaflow.ru/finance/${dealId}`;
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard
          label="В работе"
          count={summary.active_count}
          total={summary.active_total}
          color="border-blue-200 bg-blue-50"
        />
        <SummaryCard
          label="Завершено"
          count={summary.completed_count}
          total={summary.completed_total}
          color="border-green-200 bg-green-50"
        />
        <SummaryCard
          label="Отменено"
          count={summary.cancelled_count}
          total={summary.cancelled_total}
          color="border-red-200 bg-red-50"
        />
        <SummaryCard
          label="Всего"
          count={summary.total_count}
          total={summary.total_amount}
          color="border-slate-200 bg-slate-50"
        />
      </div>

      {/* Filter bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex gap-1.5 flex-wrap">
          {STATUS_PILLS.map((pill) => (
            <Link
              key={pill.label}
              href={buildFilterUrl(filters, {
                status: pill.value,
                page: 1,
              })}
              className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                filters.status === pill.value ||
                (!filters.status && pill.value === undefined)
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {pill.label}
            </Link>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex rounded-md border">
            <button
              type="button"
              className={`px-3 py-1 text-xs font-medium rounded-l-md transition-colors ${
                viewMode === "compact"
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
              onClick={() => setViewMode("compact")}
            >
              Компактный
            </button>
            <button
              type="button"
              className={`px-3 py-1 text-xs font-medium rounded-r-md transition-colors ${
                viewMode === "expanded"
                  ? "bg-foreground text-background"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
              onClick={() => setViewMode("expanded")}
            >
              Расширенный
            </button>
          </div>

          {/* Export button */}
          <a
            href="https://kvotaflow.ru/finance?export=1"
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            <Download size={14} className="mr-1" />
            Выгрузить данные
          </a>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>Всего: {total}</span>
      </div>

      {/* Table */}
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[110px]">№ сделки</TableHead>
            <TableHead className="w-[130px]">№ спец.</TableHead>
            <TableHead className="w-[180px]">Клиент</TableHead>
            <TableHead className="text-right w-[120px]">Сумма USD</TableHead>
            <TableHead className="w-[100px]">Дата</TableHead>
            <TableHead className="w-[100px]">Статус</TableHead>
            {viewMode === "expanded" && (
              <>
                <TableHead className="text-right w-[100px]">Профит USD</TableHead>
                <TableHead className="w-[120px]">Условия оплаты</TableHead>
                <TableHead className="text-right w-[110px]">Оплачено USD</TableHead>
                <TableHead className="text-right w-[110px]">Остаток USD</TableHead>
                <TableHead className="w-[100px]">Крайний срок</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {deals.map((deal) => {
            const profit = formatProfit(deal.profit_usd);
            return (
              <TableRow
                key={deal.id}
                className="cursor-pointer"
                onClick={() => handleRowClick(deal.id)}
              >
                <TableCell>
                  <span className="text-accent font-medium whitespace-nowrap">
                    {deal.deal_number}
                  </span>
                </TableCell>
                <TableCell
                  className="truncate"
                  title={deal.spec_number ?? ""}
                >
                  {deal.spec_number ?? "---"}
                </TableCell>
                <TableCell
                  className="truncate max-w-[180px]"
                  title={deal.customer_name ?? ""}
                >
                  {deal.customer_name ?? "---"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatAmount(deal.total_amount_usd)}
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  {formatDate(deal.sign_date)}
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      DEAL_STATUS_COLORS[deal.status] ?? "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {DEAL_STATUS_LABELS[deal.status] ?? deal.status}
                  </span>
                </TableCell>
                {viewMode === "expanded" && (
                  <>
                    <TableCell className={`text-right tabular-nums ${profit.className}`}>
                      {profit.text}
                    </TableCell>
                    <TableCell
                      className="truncate max-w-[120px] text-sm"
                      title={deal.payment_terms ?? ""}
                    >
                      {deal.payment_terms ?? "---"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatAmount(deal.total_paid_usd)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {deal.remaining_usd !== null ? (
                        <span
                          className={
                            deal.remaining_usd > 0
                              ? "text-amber-600"
                              : "text-green-600"
                          }
                        >
                          {formatAmount(deal.remaining_usd)}
                        </span>
                      ) : (
                        "---"
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground tabular-nums">
                      {formatDate(deal.deadline)}
                    </TableCell>
                  </>
                )}
              </TableRow>
            );
          })}
          {deals.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={viewMode === "expanded" ? 11 : 6}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет сделок</p>
                  {filters.status && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/finance?tab=deals"
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Страница {page} из {totalPages}
          </span>
          <div className="flex gap-2">
            {page > 1 && (
              <Link
                href={buildFilterUrl(filters, { page: page - 1 })}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                ← Назад
              </Link>
            )}
            {page < totalPages && (
              <Link
                href={buildFilterUrl(filters, { page: page + 1 })}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Вперёд →
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
