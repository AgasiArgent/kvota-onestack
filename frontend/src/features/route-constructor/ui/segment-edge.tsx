"use client";

import { ChevronRight, Clock } from "lucide-react";
import type { LogisticsSegment } from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";

/**
 * SegmentEdge — the visual connector between two SegmentNodes in the
 * timeline. Shows the segment's main cost (₽), transit days and a count
 * of extra expenses (pill).
 *
 * Read-only renderer; interaction lives on the parent timeline row.
 */

const rubFmt = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

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
        {hasCost ? rubFmt.format(segment.mainCostRub) : "—"}
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
