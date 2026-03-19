"use client";

import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  SupplierInvoiceItem,
  CurrencyTotal,
  SupplierInvoicesFilterParams,
} from "@/entities/finance/types";
import {
  SUPPLIER_INVOICE_STATUS_LABELS,
  SUPPLIER_INVOICE_STATUS_COLORS,
} from "@/entities/finance/types";

interface SupplierInvoicesTabProps {
  invoices: SupplierInvoiceItem[];
  currencyTotals: CurrencyTotal[];
  total: number;
  page: number;
  pageSize: number;
  filters: SupplierInvoicesFilterParams;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "---";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null, currency: string): string {
  if (amount === null || amount === undefined) return "---";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function buildFilterUrl(
  baseFilters: SupplierInvoicesFilterParams,
  overrides: Partial<SupplierInvoicesFilterParams>
): string {
  const merged = { ...baseFilters, ...overrides };
  const params = new URLSearchParams();
  params.set("tab", "invoices");
  if (merged.page && merged.page > 1) params.set("page", String(merged.page));
  return `/finance?${params.toString()}`;
}

export function SupplierInvoicesTab({
  invoices,
  currencyTotals,
  total,
  page,
  pageSize,
  filters,
}: SupplierInvoicesTabProps) {
  const totalPages = Math.ceil(total / pageSize);

  function handleRowClick(id: string) {
    window.location.href = `https://kvotaflow.ru/supplier-invoices/${id}`;
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>Всего: {total}</span>
      </div>

      {/* Table */}
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]">№</TableHead>
            <TableHead className="w-[140px]">Номер инвойса</TableHead>
            <TableHead className="w-[200px]">Поставщик</TableHead>
            <TableHead className="w-[100px]">Дата</TableHead>
            <TableHead className="text-right w-[130px]">Сумма</TableHead>
            <TableHead className="w-[70px]">Валюта</TableHead>
            <TableHead className="w-[100px]">Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((invoice, index) => (
            <TableRow
              key={invoice.id}
              className="cursor-pointer"
              onClick={() => handleRowClick(invoice.id)}
            >
              <TableCell className="text-muted-foreground tabular-nums">
                {(page - 1) * pageSize + index + 1}
              </TableCell>
              <TableCell>
                <span className="text-accent font-medium whitespace-nowrap">
                  {invoice.invoice_number}
                </span>
              </TableCell>
              <TableCell
                className="truncate max-w-[200px]"
                title={invoice.supplier_name ?? ""}
              >
                {invoice.supplier_name ?? "---"}
              </TableCell>
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(invoice.date)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatAmount(invoice.amount, invoice.currency)}
              </TableCell>
              <TableCell>
                <span className="text-xs font-medium text-muted-foreground">
                  {invoice.currency}
                </span>
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    SUPPLIER_INVOICE_STATUS_COLORS[invoice.status] ??
                    "bg-slate-100 text-slate-700"
                  }`}
                >
                  {SUPPLIER_INVOICE_STATUS_LABELS[invoice.status] ?? invoice.status}
                </span>
              </TableCell>
            </TableRow>
          ))}
          {invoices.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={7}
                className="text-center py-12 text-muted-foreground"
              >
                Нет инвойсов поставщиков
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Footer totals by currency */}
      {currencyTotals.length > 0 && (
        <div className="rounded-lg border bg-muted/30 p-4">
          <div className="flex flex-wrap gap-6 text-sm">
            {currencyTotals.map((ct) => (
              <div key={ct.currency}>
                <span className="text-muted-foreground">
                  Итого ({ct.currency}):
                </span>{" "}
                <span className="font-medium tabular-nums">
                  {formatAmount(ct.total, ct.currency)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

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
