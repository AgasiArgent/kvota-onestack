"use client";

import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
};

interface CalcSummaryRowProps {
  totalPurchase: number | null;
  totalCogs: number | null;
  totalLogistics: number | null;
  totalSaleWithVat: number | null;
  marginPercent: number | null;
  currency: string;
  quoteId: string;
}

function formatMoney(value: number | null, currency: string): string {
  if (value == null) return "\u2014";
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function formatPercent(value: number | null): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(1)}%`;
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1 text-center">
      <span className="block text-xs text-muted-foreground">{label}</span>
      <span className="block text-sm font-semibold text-foreground">{children}</span>
    </div>
  );
}

export function CalcSummaryRow({
  totalPurchase,
  totalCogs,
  totalLogistics,
  totalSaleWithVat,
  marginPercent,
  currency,
  quoteId,
}: CalcSummaryRowProps) {
  const allNull =
    totalPurchase == null &&
    totalCogs == null &&
    totalLogistics == null &&
    totalSaleWithVat == null &&
    marginPercent == null;

  return (
    <Card>
      <CardContent>
        {allNull ? (
          <p className="py-2 text-center text-sm text-muted-foreground">
            Расчёт не выполнен
          </p>
        ) : (
          <div className="flex flex-wrap items-end justify-between gap-4">
            <Metric label="Закупка">{formatMoney(totalPurchase, currency)}</Metric>
            <Metric label="Себестоимость">{formatMoney(totalCogs, currency)}</Metric>
            <Metric label="Логистика">{formatMoney(totalLogistics, currency)}</Metric>
            <Metric label="Продажа с НДС">
              {formatMoney(totalSaleWithVat, currency)}
            </Metric>
            <Metric label="Маржа">{formatPercent(marginPercent)}</Metric>
            <Link
              href={`/quotes/${quoteId}?step=cost-analysis`}
              className="shrink-0 text-xs font-medium text-accent hover:text-accent-hover hover:underline"
            >
              Подробнее &rarr;
            </Link>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
