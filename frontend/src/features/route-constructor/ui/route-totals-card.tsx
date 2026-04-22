"use client";

import type { LogisticsSegment } from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";

/**
 * RouteTotalsCard — footer summary (transit days, main cost, extras, total).
 * Matches the stats-strip in the wireframe (02-route-constructor.html).
 */

const rubFmt = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

interface RouteTotalsCardProps {
  segments: LogisticsSegment[];
  className?: string;
}

export function RouteTotalsCard({ segments, className }: RouteTotalsCardProps) {
  const days = segments.reduce((a, s) => a + (s.transitDays ?? 0), 0);
  const main = segments.reduce((a, s) => a + (s.mainCostRub ?? 0), 0);
  const extra = segments.reduce(
    (a, s) => a + s.expenses.reduce((x, e) => x + (e.costRub ?? 0), 0),
    0,
  );
  const total = main + extra;
  const count = segments.length;

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
        <TotalItem label="Основная стоимость" value={rubFmt.format(main)} />
        <TotalItem label="Доп. расходы" value={rubFmt.format(extra)} />
        <TotalItem
          label="Всего"
          value={rubFmt.format(total)}
          emphasise
        />
      </dl>
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
