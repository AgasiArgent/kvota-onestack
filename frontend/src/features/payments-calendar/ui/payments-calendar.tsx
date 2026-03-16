"use client";

import { useState, useMemo } from "react";
import {
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface PaymentRecord {
  id: string;
  specification_id: string;
  payment_number: number;
  days_term: number | null;
  calculation_variant: string | null;
  expected_payment_date: string | null;
  actual_payment_date: string | null;
  payment_amount: number | null;
  payment_currency: string | null;
  payment_purpose: string | null;
  comment: string | null;
  specification_number: string | null;
}

interface PaymentsCalendarProps {
  payments: PaymentRecord[];
}

const PURPOSE_LABELS: Record<string, string> = {
  advance: "Аванс",
  additional: "Доплата",
  final: "Закрывающий",
};

const VARIANT_LABELS: Record<string, string> = {
  from_order_date: "от даты заказа",
  from_agreement_date: "от даты согласования",
  from_shipment_date: "от даты отгрузки",
  until_shipment_date: "до даты отгрузки",
};

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

type PaymentStatus = "overdue" | "upcoming" | "completed" | "future";

function getPaymentStatus(payment: PaymentRecord): PaymentStatus {
  if (payment.actual_payment_date) return "completed";
  if (!payment.expected_payment_date) return "future";

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expected = new Date(payment.expected_payment_date);
  expected.setHours(0, 0, 0, 0);

  if (expected < today) return "overdue";

  const weekFromNow = new Date(today);
  weekFromNow.setDate(weekFromNow.getDate() + 7);
  if (expected <= weekFromNow) return "upcoming";

  return "future";
}

const STATUS_STYLES: Record<PaymentStatus, { dot: string; badge: string; text: string }> = {
  overdue: {
    dot: "bg-[var(--error)]",
    badge: "bg-[var(--error-bg)] text-[var(--error)]",
    text: "Просрочен",
  },
  upcoming: {
    dot: "bg-[var(--warning)]",
    badge: "bg-[var(--warning-bg)] text-[var(--warning)]",
    text: "Скоро",
  },
  completed: {
    dot: "bg-[var(--success)]",
    badge: "bg-[var(--success-bg)] text-[var(--success)]",
    text: "Оплачен",
  },
  future: {
    dot: "bg-gray-300 dark:bg-gray-600",
    badge: "bg-gray-100 dark:bg-gray-800 text-[var(--text-muted)]",
    text: "Запланирован",
  },
};

function getMonthDays(year: number, month: number) {
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  // Monday = 0, Sunday = 6
  const startOffset = (firstDay.getDay() + 6) % 7;
  const totalDays = lastDay.getDate();

  const days: (number | null)[] = [];
  for (let i = 0; i < startOffset; i++) days.push(null);
  for (let d = 1; d <= totalDays; d++) days.push(d);
  // Pad to complete the last week
  while (days.length % 7 !== 0) days.push(null);

  return days;
}

function sameDay(dateStr: string, year: number, month: number, day: number): boolean {
  const d = new Date(dateStr);
  return d.getFullYear() === year && d.getMonth() === month && d.getDate() === day;
}

export function PaymentsCalendar({ payments }: PaymentsCalendarProps) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  const monthPayments = useMemo(
    () =>
      payments.filter((p) => {
        const dateStr = p.expected_payment_date ?? p.actual_payment_date;
        if (!dateStr) return false;
        const d = new Date(dateStr);
        return d.getFullYear() === year && d.getMonth() === month;
      }),
    [payments, year, month]
  );

  const summary = useMemo(() => {
    let totalDue = 0;
    let overdueCount = 0;
    let completedCount = 0;

    for (const p of monthPayments) {
      totalDue += p.payment_amount ?? 0;
      const status = getPaymentStatus(p);
      if (status === "overdue") overdueCount++;
      if (status === "completed") completedCount++;
    }

    return { totalDue, overdueCount, completedCount };
  }, [monthPayments]);

  const days = useMemo(() => getMonthDays(year, month), [year, month]);

  const dayPaymentsMap = useMemo(() => {
    const map = new Map<number, PaymentRecord[]>();
    for (const p of monthPayments) {
      const dateStr = p.expected_payment_date ?? p.actual_payment_date;
      if (!dateStr) continue;
      const d = new Date(dateStr);
      if (d.getFullYear() === year && d.getMonth() === month) {
        const day = d.getDate();
        const arr = map.get(day) ?? [];
        arr.push(p);
        map.set(day, arr);
      }
    }
    return map;
  }, [monthPayments, year, month]);

  const filteredPayments = useMemo(() => {
    if (selectedDay === null) return monthPayments;
    return monthPayments.filter((p) => {
      const dateStr = p.expected_payment_date ?? p.actual_payment_date;
      if (!dateStr) return false;
      return sameDay(dateStr, year, month, selectedDay);
    });
  }, [monthPayments, selectedDay, year, month]);

  const monthLabel = new Date(year, month).toLocaleDateString("ru-RU", {
    month: "long",
    year: "numeric",
  });

  function navigateMonth(delta: number) {
    const d = new Date(year, month + delta, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth());
    setSelectedDay(null);
  }

  const todayDay = today.getFullYear() === year && today.getMonth() === month ? today.getDate() : null;

  if (payments.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CalendarDays className="h-7 w-7 text-[var(--accent)]" />
          Календарь платежей
        </h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Плановые и фактические платежи по спецификациям
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="text-center py-2">
            <div className="text-xl font-bold text-[var(--accent)]">
              {formatMoney(summary.totalDue, "USD")}
            </div>
            <div className="text-sm text-[var(--text-muted)]">К оплате</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-2">
            <div className="text-3xl font-bold text-[var(--error)]">
              {summary.overdueCount}
            </div>
            <div className="text-sm text-[var(--text-muted)]">Просрочено</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="text-center py-2">
            <div className="text-3xl font-bold text-[var(--success)]">
              {summary.completedCount}
            </div>
            <div className="text-sm text-[var(--text-muted)]">Оплачено</div>
          </CardContent>
        </Card>
      </div>

      {/* Month navigation */}
      <div className="flex items-center justify-between">
        <Button variant="outline" size="icon" onClick={() => navigateMonth(-1)}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="text-lg font-semibold capitalize">{monthLabel}</span>
        <Button variant="outline" size="icon" onClick={() => navigateMonth(1)}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* Calendar grid — hidden on small screens */}
      <div className="hidden md:block">
        <CalendarGrid
          days={days}
          dayPaymentsMap={dayPaymentsMap}
          todayDay={todayDay}
          selectedDay={selectedDay}
          onSelectDay={setSelectedDay}
        />
      </div>

      {/* Payment list */}
      <div>
        <h2 className="text-lg font-semibold mb-3">
          {selectedDay !== null
            ? `Платежи за ${selectedDay} ${monthLabel}`
            : `Все платежи за ${monthLabel}`}
          {selectedDay !== null && (
            <Button
              variant="link"
              size="sm"
              className="ml-2 text-[var(--accent)]"
              onClick={() => setSelectedDay(null)}
            >
              Показать все
            </Button>
          )}
        </h2>
        {filteredPayments.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-[var(--text-muted)]">
              Нет платежей за выбранный период
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {filteredPayments.map((p) => (
              <PaymentCard key={p.id} payment={p} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function CalendarGrid({
  days,
  dayPaymentsMap,
  todayDay,
  selectedDay,
  onSelectDay,
}: {
  days: (number | null)[];
  dayPaymentsMap: Map<number, PaymentRecord[]>;
  todayDay: number | null;
  selectedDay: number | null;
  onSelectDay: (day: number | null) => void;
}) {
  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Weekday headers */}
      <div className="grid grid-cols-7 bg-gray-50 dark:bg-gray-800/50">
        {WEEKDAYS.map((wd) => (
          <div
            key={wd}
            className="py-2 text-center text-xs font-medium text-[var(--text-muted)]"
          >
            {wd}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7">
        {days.map((day, i) => {
          if (day === null) {
            return (
              <div
                key={`empty-${i}`}
                className="min-h-[72px] border-t border-r last:border-r-0 bg-gray-50/50 dark:bg-gray-900/20"
              />
            );
          }

          const dayP = dayPaymentsMap.get(day) ?? [];
          const isToday = day === todayDay;
          const isSelected = day === selectedDay;

          return (
            <button
              key={day}
              type="button"
              onClick={() => onSelectDay(isSelected ? null : day)}
              className={`min-h-[72px] border-t border-r p-1.5 text-left transition-colors
                ${isSelected ? "bg-[var(--accent-subtle)] ring-1 ring-[var(--accent)]" : "hover:bg-gray-50 dark:hover:bg-gray-800/30"}
              `}
            >
              <span
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium
                  ${isToday ? "bg-[var(--accent)] text-white" : ""}
                `}
              >
                {day}
              </span>
              {dayP.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {dayP.slice(0, 3).map((p) => {
                    const status = getPaymentStatus(p);
                    return (
                      <span
                        key={p.id}
                        className={`h-2 w-2 rounded-full ${STATUS_STYLES[status].dot}`}
                        title={`${p.specification_number ?? "N/A"} - ${formatMoney(p.payment_amount ?? 0, p.payment_currency ?? "USD")}`}
                      />
                    );
                  })}
                  {dayP.length > 3 && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      +{dayP.length - 3}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PaymentCard({ payment }: { payment: PaymentRecord }) {
  const status = getPaymentStatus(payment);
  const style = STATUS_STYLES[status];
  const specNumber = payment.specification_number ?? "N/A";
  const amount = payment.payment_amount ?? 0;
  const currency = payment.payment_currency ?? "USD";
  const purpose = payment.payment_purpose
    ? PURPOSE_LABELS[payment.payment_purpose] ?? payment.payment_purpose
    : null;
  const variant = payment.calculation_variant
    ? VARIANT_LABELS[payment.calculation_variant] ?? payment.calculation_variant
    : null;

  const StatusIcon =
    status === "overdue"
      ? AlertCircle
      : status === "completed"
        ? CheckCircle2
        : Clock;

  return (
    <Card
      className={`border-l-4 ${
        status === "overdue"
          ? "border-l-[var(--error)]"
          : status === "upcoming"
            ? "border-l-[var(--warning)]"
            : status === "completed"
              ? "border-l-[var(--success)]"
              : "border-l-gray-300 dark:border-l-gray-600"
      }`}
    >
      <CardContent className="space-y-2">
        {/* Header row */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold">{specNumber}</span>
            <Badge className={`${style.badge} border-0 text-xs`}>
              <StatusIcon className="h-3 w-3 mr-1" />
              {style.text}
            </Badge>
            {purpose && (
              <span className="text-xs text-[var(--text-muted)]">
                {purpose}
              </span>
            )}
          </div>
          <span className="text-base font-bold">{formatMoney(amount, currency)}</span>
        </div>

        {/* Details row */}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-[var(--text-muted)]">
          {payment.expected_payment_date && (
            <span>
              Ожидается: {formatDate(payment.expected_payment_date)}
            </span>
          )}
          {payment.actual_payment_date && (
            <span>
              Оплачен: {formatDate(payment.actual_payment_date)}
            </span>
          )}
          {payment.days_term != null && (
            <span>Срок: {payment.days_term} дн.</span>
          )}
          {variant && <span>{variant}</span>}
        </div>

        {/* Comment */}
        {payment.comment && (
          <p className="text-sm text-[var(--text-muted)] bg-gray-50 dark:bg-gray-800/30 rounded px-2 py-1">
            {payment.comment}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function EmptyState() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <CalendarDays className="h-7 w-7 text-[var(--accent)]" />
          Календарь платежей
        </h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Плановые и фактические платежи по спецификациям
        </p>
      </div>
      <Card>
        <CardContent className="flex flex-col items-center py-10 text-center">
          <CalendarDays className="h-12 w-12 text-[var(--text-muted)] mb-3" />
          <h3 className="text-lg font-semibold mb-1">Нет платежей</h3>
          <p className="text-sm text-[var(--text-muted)]">
            Календарь платежей пуст. Платежи появятся после создания графика в
            спецификациях.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
