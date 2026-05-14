"use client";

import { ChevronRight, Clock } from "lucide-react";
import type { LogisticsSegment, SegmentCurrency } from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";

/**
 * SegmentEdge — the visual connector between two SegmentNodes in the
 * timeline. Shows the segment's main cost (in the segment's own currency,
 * not always RUB — Testing 2 row 30), transit days and a count of extra
 * expenses (pill).
 *
 * Read-only renderer; interaction lives on the parent timeline row.
 */

// Cache formatters per currency code — Intl.NumberFormat construction is
// non-trivial and would otherwise run on every render.
const CURRENCY_FMT_CACHE = new Map<string, Intl.NumberFormat>();

function formatSegmentCost(amount: number, code: SegmentCurrency): string {
  let fmt = CURRENCY_FMT_CACHE.get(code);
  if (!fmt) {
    fmt = new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 0,
    });
    CURRENCY_FMT_CACHE.set(code, fmt);
  }
  return fmt.format(amount);
}

interface SegmentEdgeProps {
  segment: LogisticsSegment;
  className?: string;
}

export function SegmentEdge({ segment, className }: SegmentEdgeProps) {
  const extraCount = segment.expenses?.length ?? 0;
  const hasCost = segment.mainCostRub > 0;
  const days = segment.transitDays ?? 0;

  return (
    <div
      className={cn(
        "flex items-center gap-2 text-xs text-text-muted tabular-nums",
        className,
      )}
    >
      <ChevronRight size={12} strokeWidth={2} className="text-text-subtle" aria-hidden />
      <span
        className={cn(
          "font-semibold",
          hasCost ? "text-text" : "text-text-subtle",
        )}
      >
        {hasCost
          ? formatSegmentCost(segment.mainCostRub, segment.currencyCode)
          : "—"}
      </span>
      {days > 0 && (
        <span className="inline-flex items-center gap-1">
          <Clock size={11} strokeWidth={2} aria-hidden />
          {days} дн
        </span>
      )}
      {extraCount > 0 && (
        <span className="inline-flex items-center rounded-sm border border-border-light bg-sidebar px-1.5 py-0.5 text-[11px] font-medium text-text-muted">
          +{extraCount} расх.
        </span>
      )}
    </div>
  );
}
