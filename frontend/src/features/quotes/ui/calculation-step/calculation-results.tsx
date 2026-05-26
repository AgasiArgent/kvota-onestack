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
 *
 * Testing 2 row 87: items refused by procurement (`is_unavailable=true`) or
 * disallowed by customs (`import_banned=true`) are excluded from the calc
 * engine but MUST still appear in this table as greyed-out «Исключено» rows
 * — МОП needs to see what was filtered and why. Both flags are carried on
 * the item shape; the renderer disables totals for excluded rows.
 */
export interface CalculationResultsItem {
  id: string;
  product_name: string;
  brand: string | null;
  quantity: number | null;
  base_price_vat: number | null;
  is_unavailable?: boolean | null;
  import_banned?: boolean | null;
  import_ban_reason?: string | null;
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

  return (
    <div className="space-y-4">
      {/* Pre-calc info banner — shows above the items table when no calc yet,
          so the user still sees their positions while being told to run calc. */}
      {!hasCalculation && (
        <Card>
          <CardContent className="py-3 px-4 flex items-center gap-2 text-sm text-muted-foreground">
            <Info size={16} className="shrink-0" />
            <span>
              Расчёт ещё не выполнен. Заполните параметры и нажмите
              &laquo;Рассчитать&raquo;.
            </span>
          </CardContent>
        </Card>
      )}

      {/* Summary cards — only after a successful calc */}
      {hasCalculation && (
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
      )}

      {/* Per-item table — always rendered. fmt() prints «—» for null prices. */}
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
                // Testing 2 row 87 — excluded items (МОП refused or customs
                // banned) are shown in the table for visibility but do not
                // participate in totals and are visually de-emphasised.
                const excluded =
                  item.is_unavailable === true || item.import_banned === true;
                const exclusionReason = item.is_unavailable
                  ? "Отказались МОП/МОЗ — нет в КПП"
                  : item.import_banned
                    ? item.import_ban_reason
                      ? `Запрет ввоза на таможне: ${item.import_ban_reason}`
                      : "Запрет ввоза на таможне"
                    : null;
                const priceVat = excluded ? null : item.base_price_vat;
                const qty = item.quantity ?? 0;
                const lineTotal =
                  priceVat != null ? priceVat * qty : null;

                return (
                  <TableRow
                    key={item.id}
                    className={excluded ? "text-muted-foreground" : undefined}
                  >
                    <TableCell className="text-sm">
                      <div className="flex items-center gap-2">
                        <span className={excluded ? "line-through" : undefined}>
                          {item.product_name}
                          {item.brand && (
                            <span className="ml-1 text-xs text-muted-foreground">
                              ({item.brand})
                            </span>
                          )}
                        </span>
                        {excluded && (
                          <span
                            className="inline-flex items-center rounded border border-muted-foreground/30 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground"
                            title={exclusionReason ?? undefined}
                          >
                            Исключено
                          </span>
                        )}
                      </div>
                      {excluded && exclusionReason && (
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          {exclusionReason}
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {qty}
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {excluded ? "—" : fmt(priceVat, currency)}
                    </TableCell>
                    <TableCell className="text-sm text-right tabular-nums">
                      {excluded ? "—" : fmt(lineTotal, currency)}
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
