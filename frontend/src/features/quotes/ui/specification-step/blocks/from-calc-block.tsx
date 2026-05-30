"use client";

import { Card } from "@/components/ui/card";

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  RUB: "₽",
  CNY: "¥",
};

function formatMoney(value: number | null, currency: string): string {
  if (value == null) return "—";
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function formatRate(value: number | null): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

export interface FromCalcBlockProps {
  currency: string;
  total: number | null;
  totalWithVat: number | null;
  profitUsd: number | null;
  fxToUsd: number | null;
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span className="text-xs text-muted-foreground">{label}</span>
      <p className="text-sm font-medium">{children}</p>
    </div>
  );
}

/**
 * Block «Из расчёта» (read-only) — Req 1.1–1.4.
 *
 * Mirrors the figures the calculation engine produced for the quote. Read
 * straight from the `quote` prop (canonical columns — never `total_amount_quote`,
 * which was dropped). When every figure is absent we show «нет данных расчёта».
 */
export function FromCalcBlock({
  currency,
  total,
  totalWithVat,
  profitUsd,
  fxToUsd,
}: FromCalcBlockProps) {
  const hasData =
    total != null ||
    totalWithVat != null ||
    profitUsd != null ||
    fxToUsd != null;

  return (
    <Card className="p-4 space-y-3">
      <h4 className="text-sm font-semibold">Из расчёта</h4>
      {hasData ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Metric label="Сумма">{formatMoney(total, currency)}</Metric>
          <Metric label="Сумма с НДС">{formatMoney(totalWithVat, currency)}</Metric>
          <Metric label="Прибыль">{formatMoney(profitUsd, "USD")}</Metric>
          <Metric label="Курс к USD">{formatRate(fxToUsd)}</Metric>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">нет данных расчёта</p>
      )}
    </Card>
  );
}
