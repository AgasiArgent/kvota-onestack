"use client";

import { AlertTriangle } from "lucide-react";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import { sumInCurrency, type FxRateMap } from "@/shared/lib/fx-convert";
import { cn } from "@/lib/utils";

/**
 * RouteTotalsCard — footer summary (transit days, main cost, extras, total).
 *
 * Per-segment currency support (РОЛ Тест 07 #3.7): each segment and each
 * expense carries its own `currencyCode`. Totals are converted into
 * `displayCurrency` using `ratesToRub` (foreign→RUB cache from
 * kvota.exchange_rates) — see {@link sumInCurrency}.
 *
 * When a rate is missing (e.g. exotic currency that hasn't been cached
 * yet) the card flags the affected codes inline rather than silently
 * undercount the total at zero. Matches the wireframe stats-strip
 * (02-route-constructor.html).
 */

interface RouteTotalsCardProps {
  segments: LogisticsSegment[];
  /**
   * Display currency for the totals row. Defaults to RUB to preserve
   * legacy behaviour. The parent (logistics-step) passes the parent
   * quote's currency so totals match the rest of the quote header.
   */
  displayCurrency?: string;
  /** foreign-currency → RUB rate map. RUB is implicit (1.0). */
  ratesToRub?: FxRateMap;
  className?: string;
}

export function RouteTotalsCard({
  segments,
  displayCurrency = "RUB",
  ratesToRub = {},
  className,
}: RouteTotalsCardProps) {
  const days = segments.reduce((a, s) => a + (s.transitDays ?? 0), 0);

  const main = sumInCurrency(
    segments.map((s) => ({
      amount: s.mainCostRub ?? 0,
      currency: s.currencyCode,
    })),
    displayCurrency,
    ratesToRub,
  );
  const extra = sumInCurrency(
    segments.flatMap((s) =>
      s.expenses.map((e) => ({
        amount: e.costRub ?? 0,
        currency: e.currencyCode,
      })),
    ),
    displayCurrency,
    ratesToRub,
  );
  const total = main.total + extra.total;
  const missing = Array.from(
    new Set([...main.missing, ...extra.missing]),
  ).sort();
  const count = segments.length;

  const fmt = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: displayCurrency,
    maximumFractionDigits: 0,
  });

  return (
    <section
      className={cn(
        "rounded-lg border border-border-light bg-card p-4",
        className,
      )}
      aria-label="Итого по маршруту"
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Итого по маршруту</h3>
        <span className="text-xs text-text-subtle tabular-nums">
          {count} {count === 1 ? "сегмент" : "сегментов"}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <TotalItem label="Транзит" value={`${days} дн`} />
        <TotalItem label="Основная стоимость" value={fmt.format(main.total)} />
        <TotalItem label="Доп. расходы" value={fmt.format(extra.total)} />
        <TotalItem label="Всего" value={fmt.format(total)} emphasise />
      </dl>
      {missing.length > 0 && (
        <p
          className="mt-3 flex items-start gap-1.5 rounded-md border border-warning/30 bg-warning-bg/40 px-2.5 py-1.5 text-xs text-warning-foreground"
          data-testid="route-totals-missing-rates"
        >
          <AlertTriangle
            size={12}
            strokeWidth={2}
            aria-hidden
            className="mt-0.5 shrink-0 text-warning"
          />
          <span>
            Курс не найден для: {missing.join(", ")}. Эти суммы исключены из
            итога — обновите справочник курсов или выберите другую валюту
            сегмента.
          </span>
        </p>
      )}
    </section>
  );
}

function TotalItem({
  label,
  value,
  emphasise,
}: {
  label: string;
  value: string;
  emphasise?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs text-text-muted">{label}</dt>
      <dd
        className={cn(
          "text-lg font-semibold tabular-nums",
          emphasise ? "text-accent" : "text-text",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
