"use client";

import { Badge } from "@/components/ui/badge";

import {
  paymentTypeLabel,
  type ResolvedRate,
} from "../model/types";

export interface RateBreakdownProps {
  rates: ResolvedRate[];
  /** Phase 1: always null. When non-null, renders the итого row. */
  totalRub: number | null;
  source: string;
}

/**
 * Format a single rate as a short human-readable string.
 *
 * Examples:
 *  - {value_1_number: 10, value_1_unit: 'percent'}                     → "10%"
 *  - {value_1_number: 0.04, value_1_unit: '166', value_1_currency:EUR} → "0.04 EUR/166"
 *  - raw_value_string takes precedence when set (best fidelity).
 */
export function formatRate(rate: ResolvedRate): string {
  if (rate.raw_value_string) return rate.raw_value_string;
  if (rate.value_1_unit === "percent" && rate.value_1_number != null) {
    return `${rate.value_1_number}%`;
  }
  if (rate.value_1_number != null) {
    const cur = rate.value_1_currency ? ` ${rate.value_1_currency}` : "";
    const unit = rate.value_1_unit ? `/${rate.value_1_unit}` : "";
    return `${rate.value_1_number}${cur}${unit}`;
  }
  return "—";
}

/**
 * Display a rate breakdown for a resolved customs query.
 *
 * Phase 1 limitation: backend cannot compute RUB amounts because the
 * `/resolve-rates` request body lacks customs_value/weight/quantity inputs.
 * When `totalRub` is null we surface that explicitly so users don't think
 * the missing total is a UI bug.
 */
export function RateBreakdown({ rates, totalRub, source }: RateBreakdownProps) {
  if (rates.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        Ставки не найдены для этой комбинации.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-card p-3 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-xs font-medium text-foreground">
          Расчёт пошлин и налогов
        </div>
        <Badge variant="secondary" className="text-[10px]">
          {source}
        </Badge>
      </div>

      <ul className="flex flex-col gap-1.5">
        {rates.map((rate, idx) => {
          const label = paymentTypeLabel(rate.payment_type);
          const display = formatRate(rate);
          const tooltip = rate.raw_value_string ?? display;
          return (
            <li
              key={`${rate.payment_type}-${idx}`}
              className="flex items-center justify-between gap-3"
              title={tooltip}
            >
              <span className="truncate text-foreground">{label}</span>
              <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                {display}
              </span>
            </li>
          );
        })}
      </ul>

      {totalRub != null ? (
        <div className="mt-3 flex items-center justify-between border-t border-border pt-2">
          <span className="text-sm font-semibold text-foreground">Итого</span>
          <span className="font-mono text-sm font-semibold tabular-nums text-foreground">
            {totalRub.toLocaleString("ru-RU", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
            {" ₽"}
          </span>
        </div>
      ) : (
        <div className="mt-3 rounded-md bg-muted/50 px-2 py-1.5 text-[11px] text-muted-foreground">
          Расчёт сумм недоступен — введите таможенную стоимость, массу и
          количество в строке для получения итога.
        </div>
      )}
    </div>
  );
}
