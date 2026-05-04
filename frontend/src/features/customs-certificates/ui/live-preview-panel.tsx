"use client";

/**
 * Live preview of how a certificate / expense cost will distribute across
 * the currently selected positions (REQ-7 AC#5, REQ-10 AC#2 — sub-component
 * shared between `CertificateModal` and `ExpenseModal`).
 *
 * Pure render — recalculates the proportional shares on every prop change.
 * Math runs through `splitCostBatch` (REQ-3, parity-tested vs the Python
 * sister) so the preview kopek-matches what the server will compute on
 * `POST /api/customs/certificates`.
 *
 * Per design.md §4.8 + REQ-7 AC#5:
 *   - Header «Распределение стоимости»
 *   - Per-row «№N {name} → {share_rub} ₽ ({share_percent}%)»
 *   - Footer «Всего: {certCost} ₽»
 *   - Empty state «Выберите позиции для распределения»
 *
 * Test framework constraint (no jsdom): pure helpers
 * (`computePreviewRows`, `formatPercent`) are exported and unit-tested
 * directly. JSX is exercised via SSR snapshots.
 */

import { useMemo } from "react";

import { cn } from "@/lib/utils";

import type { QuoteItemForSelect } from "../model/types";
import { formatRub } from "../lib/format-rub";
import { splitCostBatch } from "../lib/cost-split";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit testing.
// ---------------------------------------------------------------------------

/** One pre-computed row in the preview list — shape consumed by JSX. */
export interface PreviewRow {
  /** UUID of the `quote_items` row this preview entry refers to. */
  id: string;
  /** 1-based ordinal within the quote — rendered as «№N». */
  position: number;
  /** Display name of the position. */
  name: string;
  /** Kopek-exact share of `certCost` for this position. */
  share_rub: number;
  /** Percentage share (0..100) — informational only. */
  share_percent: number;
}

/**
 * Format a share percentage to a stable, human-readable string.
 *
 *  - `1` → `"1%"` for whole-number shares (cleaner UI density).
 *  - `33.33333…` → `"33.3%"` (one fractional digit, banker's rounding via
 *    `toFixed`). The percentage is informational; the kopek-exact share
 *    in `share_rub` is the authoritative number.
 *  - Non-finite values (e.g. when `certCost === 0`) → `"0%"`.
 */
export function formatPercent(value: number): string {
  if (!Number.isFinite(value) || value === 0) {
    return "0%";
  }
  // Whole numbers — render without decimals to match mockup typography.
  if (Number.isInteger(value)) {
    return `${value}%`;
  }
  return `${value.toFixed(1)}%`;
}

/**
 * Compute preview rows from selected items + cert cost.
 *
 *  - Empty input → `[]` (UI renders the empty state instead).
 *  - `certCost === 0` → all shares 0; percentages also 0 (avoids ÷0).
 *  - Otherwise → uses `splitCostBatch` with each item's `rub_basis`,
 *    then computes `share_percent = share_rub / certCost × 100`.
 *
 * Pure — never mutates inputs. Order of returned rows matches input.
 */
export function computePreviewRows(
  selectedItems: readonly QuoteItemForSelect[],
  certCost: number,
): PreviewRow[] {
  if (selectedItems.length === 0) {
    return [];
  }
  const itemValues = selectedItems.map((i) => i.rub_basis);
  const shares = splitCostBatch(itemValues, certCost);
  return selectedItems.map((item, idx) => {
    const share = shares[idx] ?? 0;
    const percent = certCost > 0 ? (share / certCost) * 100 : 0;
    return {
      id: item.id,
      position: item.position,
      name: item.name,
      share_rub: share,
      share_percent: percent,
    };
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface LivePreviewPanelProps {
  /** Positions currently selected in the parent multi-select (controlled). */
  selectedItems: QuoteItemForSelect[];
  /** Certificate / expense cost in RUB — drives the proportional split. */
  certCost: number;
  /** Optional className passed to the outer container for layout overrides. */
  className?: string;
}

export function LivePreviewPanel({
  selectedItems,
  certCost,
  className,
}: LivePreviewPanelProps) {
  const rows = useMemo(
    () => computePreviewRows(selectedItems, certCost),
    [selectedItems, certCost],
  );

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-lg border border-border bg-card p-3",
        className,
      )}
      data-slot="live-preview-panel"
    >
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Распределение стоимости
      </div>

      {rows.length === 0 ? (
        <div className="py-6 text-center text-xs text-muted-foreground">
          Выберите позиции для распределения
        </div>
      ) : (
        <>
          <div className="flex flex-col" data-slot="preview-rows">
            {rows.map((row) => (
              <div
                key={row.id}
                className="flex items-baseline justify-between gap-2 py-1 text-xs"
                data-slot="preview-row"
                data-item-id={row.id}
              >
                <span className="flex-1 truncate text-foreground">
                  <span className="font-medium">{`№${row.position}`}</span>
                  <span className="text-muted-foreground"> · </span>
                  {row.name}
                </span>
                <span className="shrink-0 tabular-nums text-foreground">
                  {formatRub(row.share_rub)}
                  <span className="ml-1 text-muted-foreground">
                    {`(${formatPercent(row.share_percent)})`}
                  </span>
                </span>
              </div>
            ))}
          </div>
          <div className="flex items-baseline justify-between gap-2 border-t border-border pt-2 text-xs font-medium">
            <span className="text-muted-foreground">Всего:</span>
            <span className="tabular-nums text-foreground">
              {formatRub(certCost)}
            </span>
          </div>
        </>
      )}
    </div>
  );
}
