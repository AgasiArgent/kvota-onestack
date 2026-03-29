"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { MetricCard } from "./metric-card";
import type {
  QuotesMetrics,
  ProposalsMetrics,
  DealsMetrics,
} from "./queries";

const PERIODS = [
  { key: "week", label: "Неделя" },
  { key: "month", label: "Месяц" },
  { key: "quarter", label: "Квартал" },
  { key: "year", label: "Год" },
] as const;

const numberFmt = new Intl.NumberFormat("ru-RU");
const currencyFmt = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function formatDays(days: number | null): string {
  if (days === null) return "--";
  return `${days} дн.`;
}

interface DashboardContentProps {
  period: string;
  quotes: QuotesMetrics;
  proposals: ProposalsMetrics;
  deals: DealsMetrics;
}

function DashboardContentInner({
  period,
  quotes,
  proposals,
  deals,
}: DashboardContentProps) {
  const router = useRouter();
  const searchParams = useSearchParams();

  function handlePeriodChange(newPeriod: string) {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    params.set("period", newPeriod);
    router.push(`/dashboard?${params.toString()}`);
  }

  return (
    <div className="space-y-6">
      {/* Period switcher */}
      <div className="flex gap-1 rounded-lg bg-muted p-1 w-fit">
        {PERIODS.map((p) => (
          <button
            key={p.key}
            onClick={() => handlePeriodChange(p.key)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              period === p.key
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Section 1: Quotes */}
      <Card>
        <CardHeader>
          <CardTitle>Заявки</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <MetricCard
              value={numberFmt.format(quotes.created)}
              label="Создано КП"
            />
            <MetricCard
              value={numberFmt.format(quotes.processed)}
              label="Обработано закупкой"
            />
            <MetricCard
              value={`${quotes.processedPct}%`}
              label="% обработанных"
              variant={quotes.processedPct >= 80 ? "accent" : "default"}
            />
            <MetricCard
              value={formatDays(quotes.medianProcessingDays)}
              label="Медиана обработки"
            />
          </div>
        </CardContent>
      </Card>

      {/* Section 2: Proposals */}
      <Card>
        <CardHeader>
          <CardTitle>Коммерческие предложения</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <MetricCard
              value={numberFmt.format(proposals.count)}
              label="Кол-во КП"
            />
            <MetricCard
              value={currencyFmt.format(proposals.totalUsd)}
              label="Сумма"
            />
            <MetricCard
              value={currencyFmt.format(proposals.profitUsd)}
              label="Валовая прибыль"
              variant="accent"
            />
            <MetricCard
              value={`${proposals.conversionPct}%`}
              label="Конверсия КП -> Сделка"
            />
          </div>
        </CardContent>
      </Card>

      {/* Section 3: Deals */}
      <Card>
        <CardHeader>
          <CardTitle>Сделки</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6 sm:grid-cols-5">
            <MetricCard
              value={numberFmt.format(deals.count)}
              label="Кол-во сделок"
            />
            <MetricCard
              value={currencyFmt.format(deals.totalAmount)}
              label="Сумма"
            />
            <MetricCard
              value={currencyFmt.format(deals.paidAmount)}
              label="Оплачено"
              variant="accent"
            />
            <MetricCard
              value={currencyFmt.format(deals.plannedAmount)}
              label="План"
            />
            <MetricCard
              value={numberFmt.format(deals.overdueCount)}
              label="Просрочки"
              variant={deals.overdueCount > 0 ? "warning" : "default"}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function DashboardContent(props: DashboardContentProps) {
  return (
    <Suspense>
      <DashboardContentInner {...props} />
    </Suspense>
  );
}
