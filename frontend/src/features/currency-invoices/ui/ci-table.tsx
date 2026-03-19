"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CurrencyInvoice, CIFilterParams } from "@/entities/currency-invoice/types";
import {
  SEGMENT_COLORS,
  STATUS_LABELS,
  STATUS_COLORS,
} from "@/entities/currency-invoice/types";

interface CITableProps {
  invoices: CurrencyInvoice[];
  total: number;
  page: number;
  pageSize: number;
  filters: CIFilterParams;
}

const STATUS_PILLS = [
  { value: "draft", label: "Черновик" },
  { value: "verified", label: "Подтверждён" },
  { value: "exported", label: "Экспортирован" },
];

const SEGMENT_PILLS = [
  { value: "EURTR", label: "EURTR" },
  { value: "TRRU", label: "TRRU" },
];

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null, currency: string): string {
  if (amount === null || amount === undefined) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function buildFilterUrl(
  baseFilters: CIFilterParams,
  overrides: Partial<CIFilterParams>
): string {
  const merged = { ...baseFilters, ...overrides };
  const params = new URLSearchParams();
  if (merged.status) params.set("status", merged.status);
  if (merged.segment) params.set("segment", merged.segment);
  if (merged.page && merged.page > 1) params.set("page", String(merged.page));
  const qs = params.toString();
  return qs ? `/currency-invoices?${qs}` : "/currency-invoices";
}

function FilterPills({
  items,
  activeValue,
  filterKey,
  filters,
}: {
  items: { value: string; label: string }[];
  activeValue: string | undefined;
  filterKey: "status" | "segment";
  filters: CIFilterParams;
}) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      <Link
        href={buildFilterUrl(filters, { [filterKey]: undefined, page: 1 })}
        className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-colors ${
          !activeValue
            ? "bg-foreground text-background"
            : "bg-muted text-muted-foreground hover:bg-muted/80"
        }`}
      >
        Все
      </Link>
      {items.map((item) => (
        <Link
          key={item.value}
          href={buildFilterUrl(filters, {
            [filterKey]: activeValue === item.value ? undefined : item.value,
            page: 1,
          })}
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            activeValue === item.value
              ? "bg-foreground text-background"
              : "bg-muted text-muted-foreground hover:bg-muted/80"
          }`}
        >
          {item.label}
        </Link>
      ))}
    </div>
  );
}

export function CITable({
  invoices,
  total,
  page,
  pageSize,
  filters,
}: CITableProps) {
  const router = useRouter();
  const totalPages = Math.ceil(total / pageSize);

  function handleRowClick(id: string) {
    router.push(`/currency-invoices/${id}`);
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-medium w-16">Статус:</span>
          <FilterPills
            items={STATUS_PILLS}
            activeValue={filters.status}
            filterKey="status"
            filters={filters}
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-medium w-16">Сегмент:</span>
          <FilterPills
            items={SEGMENT_PILLS}
            activeValue={filters.segment}
            filterKey="segment"
            filters={filters}
          />
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
            <TableHead className="w-[90px]">Дата</TableHead>
            <TableHead className="w-[140px]">Номер</TableHead>
            <TableHead className="w-[80px]">Сегмент</TableHead>
            <TableHead className="w-[120px]">КП</TableHead>
            <TableHead className="w-[160px]">Клиент</TableHead>
            <TableHead className="w-[140px]">Продавец</TableHead>
            <TableHead className="w-[140px]">Покупатель</TableHead>
            <TableHead className="text-right w-[120px]">Сумма</TableHead>
            <TableHead className="w-[110px]">Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((ci) => (
            <TableRow
              key={ci.id}
              className="cursor-pointer"
              onClick={() => handleRowClick(ci.id)}
            >
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(ci.created_at)}
              </TableCell>
              <TableCell>
                <span className="text-accent font-medium">{ci.invoice_number}</span>
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    SEGMENT_COLORS[ci.segment] ?? "bg-slate-100 text-slate-700"
                  }`}
                >
                  {ci.segment}
                </span>
              </TableCell>
              <TableCell className="text-muted-foreground truncate" title={ci.quote_idn ?? ""}>
                {ci.quote_idn ?? "\u2014"}
              </TableCell>
              <TableCell className="truncate max-w-[160px]" title={ci.customer_name ?? ""}>
                {ci.customer_name ?? "\u2014"}
              </TableCell>
              <TableCell className="truncate max-w-[140px]" title={ci.seller_name ?? ""}>
                {ci.seller_name ?? "\u2014"}
              </TableCell>
              <TableCell className="truncate max-w-[140px]" title={ci.buyer_name ?? ""}>
                {ci.buyer_name ?? "\u2014"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatAmount(ci.total_amount, ci.currency)}
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    STATUS_COLORS[ci.status] ?? "bg-slate-100 text-slate-700"
                  }`}
                >
                  {STATUS_LABELS[ci.status] ?? ci.status}
                </span>
              </TableCell>
            </TableRow>
          ))}
          {invoices.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={9}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет валютных инвойсов</p>
                  {(filters.status || filters.segment) && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/currency-invoices"
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
                &larr; Назад
              </Link>
            )}
            {page < totalPages && (
              <Link
                href={buildFilterUrl(filters, { page: page + 1 })}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Вперёд &rarr;
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
