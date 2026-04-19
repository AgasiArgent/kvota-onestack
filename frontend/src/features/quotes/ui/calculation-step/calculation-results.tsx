"use client";

import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Info } from "lucide-react";
import type { QuoteDetailRow } from "@/entities/quote/queries";

/**
 * Phase 5d Task 12 — narrow composed-item shape for the calc-results table.
 *
 * Migration 284 moves `base_price_vat` from `quote_items` to `invoice_items`.
 * The calc engine writes the per-unit VAT-inclusive price into the selected
 * invoice's invoice_items rows, and the parent page composes a flat list
 * (via composition_service.get_composed_items) for this renderer. Only the
 * fields actually rendered in the table are in this shape.
 */
export interface CalculationResultsItem {
  id: string;
  product_name: string;
  brand: string | null;
  quantity: number | null;
  base_price_vat: number | null;
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
};

function fmt(value: number | null, currency: string): string {
  if (value == null) return "\u2014";
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function fmtPct(value: number | null): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(1)}%`;
}

function ext<T>(row: unknown): T {
  return row as T;
}

interface CalculationResultsProps {
  quote: QuoteDetailRow;
  items: CalculationResultsItem[];
}

export function CalculationResults({ quote, items }: CalculationResultsProps) {
  const currency = quote.currency ?? "USD";
  // Python calc writes to total_quote_currency (with VAT total in quote currency)
  const totalWithVat =
    ext<{ total_quote_currency?: number | null }>(quote).total_quote_currency ??
    null;
  const revenueNoVat =
    ext<{ revenue_no_vat_quote_currency?: number | null }>(quote)
      .revenue_no_vat_quote_currency ?? null;
  const profit = quote.profit_quote_currency ?? null;
  const cogs =
    ext<{ cogs_quote_currency?: number | null }>(quote).cogs_quote_currency ??
    null;

  const marginPercent =
    profit != null && revenueNoVat != null && revenueNoVat !== 0
      ? (profit / revenueNoVat) * 100
      : null;

  const hasCalculation = totalWithVat != null;

  if (!hasCalculation) {
    return (
      <Card>
        <CardContent className="py-8 flex flex-col items-center gap-3 text-center">
          <Info size={24} className="text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Расчёт ещё не выполнен. Заполните параметры и нажмите
            &laquo;Рассчитать&raquo;.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <SummaryCard
          label="Сумма без НДС"
          value={fmt(revenueNoVat, currency)}
        />
        <SummaryCard
          label="Сумма с НДС"
          value={fmt(totalWithVat, currency)}
        />
        <SummaryCard label="Профит" value={fmt(profit, currency)} accent />
        <SummaryCard label="Маржа" value={fmtPct(marginPercent)} accent />
      </div>

      {/* Per-item table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Наименование</TableHead>
                <TableHead className="text-xs text-right w-20">
                  Кол-во
                </TableHead>
                <TableHead className="text-xs text-right w-32">
                  Цена (с НДС)
                </TableHead>
                <TableHead className="text-xs text-right w-36">
                  Итого (с НДС)
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const priceVat = item.base_price_vat;
                const qty = item.quantity ?? 0;
                const lineTotal =
                  priceVat != null ? priceVat * qty : null;

                return (
                  <TableRow key={item.id}>
                    <TableCell className="text-sm">
                      <div>
                        {item.product_name}
                        {item.brand && (
                          <span className="ml-1 text-xs text-muted-foreground">
                            ({item.brand})
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {qty}
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {fmt(priceVat, currency)}
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {fmt(lineTotal, currency)}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* COGS breakdown if available */}
      {cogs != null && (
        <div className="flex items-center justify-between px-1 text-xs text-muted-foreground">
          <span>Себестоимость</span>
          <span className="tabular-nums">{fmt(cogs, currency)}</span>
        </div>
      )}
    </div>
  );
}

function SummaryCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <Card size="sm">
      <CardContent className="py-3 px-4">
        <p className="text-[11px] uppercase tracking-wide text-muted-foreground mb-1">
          {label}
        </p>
        <p
          className={`text-base font-semibold tabular-nums ${accent ? "text-accent" : ""}`}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
