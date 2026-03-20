"use client";

import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/shared/ui/pagination";
import type {
  PaymentRecord,
  PaymentTotals,
  PaymentsFilterParams,
} from "@/entities/finance/types";

interface PaymentsTabProps {
  payments: PaymentRecord[];
  totals: PaymentTotals;
  total: number;
  page: number;
  pageSize: number;
  filters: PaymentsFilterParams;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "---";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null, currency?: string): string {
  if (amount === null || amount === undefined) return "---";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: currency ?? "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatTotalAmount(amount: number): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function buildFilterUrl(
  baseFilters: PaymentsFilterParams,
  overrides: Partial<PaymentsFilterParams>
): string {
  const merged = { ...baseFilters, ...overrides };
  const params = new URLSearchParams();
  params.set("tab", "payments");
  if (merged.grouping) params.set("grouping", merged.grouping);
  if (merged.type) params.set("type", merged.type);
  if (merged.payment_status) params.set("payment_status", merged.payment_status);
  if (merged.date_from) params.set("date_from", merged.date_from);
  if (merged.date_to) params.set("date_to", merged.date_to);
  if (merged.page && merged.page > 1) params.set("page", String(merged.page));
  return `/finance?${params.toString()}`;
}

function FilterPills({
  items,
  activeValue,
  filterKey,
  filters,
}: {
  items: { value: string | undefined; label: string }[];
  activeValue: string | undefined;
  filterKey: keyof PaymentsFilterParams;
  filters: PaymentsFilterParams;
}) {
  return (
    <div className="flex gap-1.5 flex-wrap">
      {items.map((item) => (
        <Link
          key={item.label}
          href={buildFilterUrl(filters, {
            [filterKey]: item.value,
            page: 1,
          })}
          className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            activeValue === item.value ||
            (!activeValue && item.value === undefined)
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

const TYPE_PILLS = [
  { value: undefined, label: "Все" },
  { value: "income", label: "Приход" },
  { value: "expense", label: "Расход" },
] as const;

const STATUS_PILLS = [
  { value: undefined, label: "Все" },
  { value: "plan", label: "План" },
  { value: "paid", label: "Оплачено" },
  { value: "overdue", label: "Просрочено" },
] as const;

export function PaymentsTab({
  payments,
  totals,
  total,
  page,
  pageSize,
  filters,
}: PaymentsTabProps) {
  const totalPages = Math.ceil(total / pageSize);

  function handleDateChange(field: "date_from" | "date_to", value: string) {
    const url = buildFilterUrl(filters, { [field]: value || undefined, page: 1 });
    window.location.href = url;
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-medium w-20 shrink-0">
            Тип:
          </span>
          <FilterPills
            items={[...TYPE_PILLS]}
            activeValue={filters.type}
            filterKey="type"
            filters={filters}
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-medium w-20 shrink-0">
            Статус:
          </span>
          <FilterPills
            items={[...STATUS_PILLS]}
            activeValue={filters.payment_status}
            filterKey="payment_status"
            filters={filters}
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground font-medium w-20 shrink-0">
            Период:
          </span>
          <div className="flex items-center gap-2">
            <label className="text-xs text-muted-foreground">С:</label>
            <input
              type="date"
              defaultValue={filters.date_from ?? ""}
              className="h-8 rounded-md border px-2 text-xs"
              onChange={(e) => handleDateChange("date_from", e.target.value)}
            />
            <label className="text-xs text-muted-foreground">По:</label>
            <input
              type="date"
              defaultValue={filters.date_to ?? ""}
              className="h-8 rounded-md border px-2 text-xs"
              onChange={(e) => handleDateChange("date_to", e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>Всего записей: {total}</span>
      </div>

      {/* Table */}
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[100px]">План. дата</TableHead>
            <TableHead className="w-[100px]">Сделка</TableHead>
            <TableHead className="w-[160px]">Клиент</TableHead>
            <TableHead className="w-[140px]">Категория</TableHead>
            <TableHead className="w-[180px]">Описание</TableHead>
            <TableHead className="text-right w-[120px]">Сумма план</TableHead>
            <TableHead className="text-right w-[120px]">Сумма факт</TableHead>
            <TableHead className="w-[100px]">Дата факт</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {payments.map((payment) => (
            <TableRow key={payment.id}>
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(payment.planned_date)}
              </TableCell>
              <TableCell>
                <span className="text-accent font-medium whitespace-nowrap">
                  {payment.deal_number}
                </span>
              </TableCell>
              <TableCell
                className="truncate max-w-[160px]"
                title={payment.customer_name ?? ""}
              >
                {payment.customer_name ?? "---"}
              </TableCell>
              <TableCell>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    payment.is_income
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {payment.category_name}
                </span>
              </TableCell>
              <TableCell
                className="truncate max-w-[180px] text-sm"
                title={payment.description ?? ""}
              >
                {payment.description ?? "---"}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatAmount(payment.planned_amount, payment.planned_currency)}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {payment.actual_amount !== null ? (
                  <span className="text-green-600">
                    {formatAmount(payment.actual_amount, payment.planned_currency)}
                  </span>
                ) : (
                  "---"
                )}
              </TableCell>
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(payment.actual_date)}
              </TableCell>
            </TableRow>
          ))}
          {payments.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={8}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет платёжных записей</p>
                  {(filters.type || filters.payment_status || filters.date_from || filters.date_to) && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/finance?tab=payments"
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

      {/* Footer totals */}
      <div className="rounded-lg border bg-muted/30 p-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">Поступления план:</span>
            <div className="font-medium tabular-nums">
              {formatTotalAmount(totals.planned_income)}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Поступления факт:</span>
            <div className="font-medium text-green-600 tabular-nums">
              {formatTotalAmount(totals.actual_income)}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Выплаты план:</span>
            <div className="font-medium tabular-nums">
              {formatTotalAmount(totals.planned_expense)}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Выплаты факт:</span>
            <div className="font-medium text-red-600 tabular-nums">
              {formatTotalAmount(totals.actual_expense)}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Баланс:</span>
            <div
              className={`font-bold tabular-nums ${
                totals.balance >= 0 ? "text-green-600" : "text-red-600"
              }`}
            >
              {formatTotalAmount(totals.balance)}
            </div>
          </div>
        </div>
      </div>

      {/* Pagination */}
      <Pagination
        currentPage={page}
        totalPages={totalPages}
        totalItems={total}
        itemLabel="записей"
        buildHref={(p) => buildFilterUrl(filters, { page: p })}
      />
    </div>
  );
}
