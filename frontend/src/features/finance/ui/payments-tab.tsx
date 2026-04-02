"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/shared/ui/pagination";
import { PlanFactSheet } from "@/features/plan-fact/ui/plan-fact-sheet";
import { PlanFactCreateDialog } from "@/features/plan-fact/ui/plan-fact-create-dialog";
import type {
  PaymentRecord,
  PaymentTotals,
  PaymentsFilterParams,
  PlanFactItem,
  PlanFactCurrency,
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

/**
 * Convert a PaymentRecord (from server query) to a PlanFactItem (needed by PlanFactSheet).
 * PaymentRecord is a flattened view; PlanFactItem has nested category and additional fields.
 */
function paymentToPlanFactItem(payment: PaymentRecord): PlanFactItem {
  return {
    id: payment.id,
    deal_id: payment.deal_id,
    category: {
      id: payment.category_id,
      code: payment.category_slug,
      name: payment.category_name,
      is_income: payment.is_income,
    },
    description: payment.description ?? "",
    planned_amount: payment.planned_amount ?? 0,
    planned_currency: (payment.planned_currency as PlanFactCurrency) ?? "RUB",
    planned_date: payment.planned_date ?? "",
    actual_amount: payment.actual_amount,
    actual_currency: payment.actual_currency as PlanFactCurrency | null,
    actual_date: payment.actual_date,
    variance_amount: null,
    payment_document: null,
    notes: null,
    attachment_url: null,
    created_at: "",
  };
}

export function PaymentsTab({
  payments,
  totals,
  total,
  page,
  pageSize,
  filters,
}: PaymentsTabProps) {
  const router = useRouter();
  const totalPages = Math.ceil(total / pageSize);

  // Sheet state (record actual payment)
  const [sheetItem, setSheetItem] = useState<PlanFactItem | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Create dialog state
  const [createOpen, setCreateOpen] = useState(false);

  function handleRowClick(payment: PaymentRecord) {
    if (payment.actual_amount !== null) return;
    setSheetItem(paymentToPlanFactItem(payment));
    setSheetOpen(true);
  }

  function handleMutationSuccess() {
    router.refresh();
  }

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

      {/* Stats + create button */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          Всего записей: {total}
        </span>
        <Button
          size="sm"
          onClick={() => setCreateOpen(true)}
          className="bg-accent text-white hover:bg-accent-hover"
        >
          <Plus size={14} />
          Новый платёж
        </Button>
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
            <TableRow
              key={payment.id}
              className={
                payment.actual_amount === null
                  ? "cursor-pointer hover:bg-muted/50"
                  : ""
              }
              onClick={() => handleRowClick(payment)}
            >
              <TableCell className="text-muted-foreground tabular-nums">
                {formatDate(payment.planned_date)}
              </TableCell>
              <TableCell className="truncate">
                <span className="text-accent font-medium">
                  {payment.deal_number}
                </span>
              </TableCell>
              <TableCell
                className="truncate max-w-[160px]"
                title={payment.customer_name ?? ""}
              >
                {payment.customer_name ?? "---"}
              </TableCell>
              <TableCell className="overflow-hidden">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${
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

      {/* Record actual payment sheet */}
      {sheetItem && (
        <PlanFactSheet
          item={sheetItem}
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          onSuccess={handleMutationSuccess}
        />
      )}

      {/* Create new payment dialog */}
      <PlanFactCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={handleMutationSuccess}
        showQuoteSearch
      />
    </div>
  );
}
