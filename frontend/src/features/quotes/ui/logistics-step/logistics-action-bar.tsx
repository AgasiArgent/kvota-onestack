"use client";

import { CheckCircle, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import { sumInCurrency, type FxRateMap } from "@/shared/lib/fx-convert";

/**
 * LogisticsActionBar — sticky header with the per-invoice
 * «Завершить логистику» CTA, mirroring CustomsActionBar in shape.
 *
 * Strict gate (per design Q2): the button is disabled until every
 * segment has both from + to locations AND a positive cost. The
 * tooltip lists the missing pieces so the logistician knows exactly
 * what to fill in. Empty route is its own case ("Маршрут пуст").
 *
 * Behavioural states:
 *   - alreadyCompleted: button shows "Логистика готова ✓" disabled.
 *   - needsReview: amber state telling the user procurement made
 *     smart-delta changes; they must re-check before completing again.
 *   - canEdit=false: button shown disabled with "Нет прав" tooltip
 *     (matches CustomsActionBar's pattern of always rendering the bar).
 *   - default: enabled when the strict gate passes; clicking fires
 *     onComplete which the parent handles (server action + toast).
 *
 * Currency-aware totals (РОЛ Тест 07 #5c review, W1): segments now carry
 * their own `currencyCode` (Combo-3). The summary at the right summed
 * `mainCostRub` blindly across mixed-currency segments and labelled it
 * RUB — wrong. Now we convert each segment's amount into the parent
 * quote's `displayCurrency` via {@link sumInCurrency}; codes without an
 * FX rate are surfaced via a quiet AlertCircle so the figure is never
 * silently misleading.
 */

interface MissingItem {
  segmentNumber: number;
  field: "from" | "to" | "cost";
}

interface LogisticsActionBarProps {
  segments: LogisticsSegment[];
  alreadyCompleted: boolean;
  needsReview: boolean;
  canEdit: boolean;
  completing?: boolean;
  onComplete: () => void;
  /** Display currency for the totals strip — typically the parent quote's currency. */
  displayCurrency: string;
  /** foreign-currency → RUB rate map. RUB is implicit (1.0). */
  fxRates: FxRateMap;
}

function findMissing(segments: LogisticsSegment[]): MissingItem[] {
  if (segments.length === 0) {
    // Sentinel: zero segments is a single "empty route" case
    return [{ segmentNumber: 0, field: "from" }];
  }
  const missing: MissingItem[] = [];
  for (const seg of segments) {
    if (!seg.fromLocation) {
      missing.push({ segmentNumber: seg.sequenceOrder, field: "from" });
    }
    if (!seg.toLocation) {
      missing.push({ segmentNumber: seg.sequenceOrder, field: "to" });
    }
    // Currency-agnostic: > 0 holds for any currency, just not yet filled in.
    if (!(seg.mainCostRub > 0)) {
      missing.push({ segmentNumber: seg.sequenceOrder, field: "cost" });
    }
  }
  return missing;
}

function formatMissingTooltip(items: MissingItem[]): string {
  if (items.length === 1 && items[0].segmentNumber === 0) {
    return "Маршрут пуст — добавьте хотя бы один сегмент.";
  }
  const fieldLabel: Record<MissingItem["field"], string> = {
    from: "укажите «Откуда»",
    to: "укажите «Куда»",
    cost: "укажите стоимость > 0",
  };
  const lines = items.slice(0, 5).map(
    (m) => `• Сегмент ${m.segmentNumber}: ${fieldLabel[m.field]}`,
  );
  if (items.length > 5) {
    lines.push(`• …и ещё ${items.length - 5}`);
  }
  return "Заполните перед завершением:\n" + lines.join("\n");
}

export function LogisticsActionBar({
  segments,
  alreadyCompleted,
  needsReview,
  canEdit,
  completing = false,
  onComplete,
  displayCurrency,
  fxRates,
}: LogisticsActionBarProps) {
  const missing = findMissing(segments);
  const { total: totalCost, missing: missingRates } = sumInCurrency(
    segments.map((s) => ({
      amount: s.mainCostRub ?? 0,
      currency: s.currencyCode,
    })),
    displayCurrency,
    fxRates,
  );
  const totalDays = segments.reduce((sum, s) => sum + (s.transitDays ?? 0), 0);

  const totalFmt = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: displayCurrency,
    maximumFractionDigits: 0,
  });
  const totalLabel = missingRates.length > 0
    ? `≈ ${totalFmt.format(totalCost)}`
    : totalFmt.format(totalCost);

  // Why the button is disabled (in priority order)
  const disabledReason: string | null = !canEdit
    ? "Нет прав на завершение логистики."
    : alreadyCompleted
      ? "Логистика уже завершена для этого инвойса."
      : needsReview
        ? "Закупки изменили позиции после прошлого завершения. Пересмотрите маршрут и подтвердите изменения."
        : missing.length > 0
          ? formatMissingTooltip(missing)
          : null;

  const isReady = disabledReason === null;
  const buttonLabel = alreadyCompleted
    ? "Логистика готова"
    : "Завершить логистику";

  const button = (
    <Button
      size="sm"
      className={
        alreadyCompleted
          ? "bg-success/20 text-success hover:bg-success/20 cursor-default"
          : "bg-success text-white hover:bg-success/90"
      }
      disabled={!isReady || completing}
      onClick={onComplete}
      aria-label={buttonLabel}
    >
      {completing ? (
        <Loader2 size={14} className="animate-spin" aria-hidden />
      ) : alreadyCompleted ? (
        <CheckCircle size={14} aria-hidden />
      ) : needsReview ? (
        <AlertCircle size={14} aria-hidden />
      ) : (
        <CheckCircle size={14} aria-hidden />
      )}
      {buttonLabel}
    </Button>
  );

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      {disabledReason ? (
        <Tooltip>
          <TooltipTrigger render={<span className="inline-block" />}>
            {button}
          </TooltipTrigger>
          <TooltipContent
            side="bottom"
            className="max-w-xs whitespace-pre-line text-xs"
          >
            {disabledReason}
          </TooltipContent>
        </Tooltip>
      ) : (
        button
      )}

      <span
        className="ml-auto text-sm text-muted-foreground tabular-nums flex items-center gap-1.5"
        data-testid="logistics-action-bar-totals"
      >
        {segments.length}{" "}
        {segments.length === 1 ? "сегмент" : "сегментов"}
        {" · "}
        {totalLabel}
        {totalDays > 0 ? ` · ${totalDays} дн` : ""}
        {missingRates.length > 0 && (
          <Tooltip>
            <TooltipTrigger render={<span className="inline-flex" />}>
              <AlertCircle
                size={12}
                strokeWidth={2}
                aria-hidden
                className="text-warning"
                data-testid="logistics-action-bar-missing-rates"
              />
            </TooltipTrigger>
            <TooltipContent side="bottom" className="max-w-xs text-xs">
              {`Курс не найден для: ${missingRates.join(", ")}. Эти суммы исключены из итога.`}
            </TooltipContent>
          </Tooltip>
        )}
      </span>
    </div>
  );
}
