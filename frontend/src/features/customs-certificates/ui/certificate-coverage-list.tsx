"use client";

/**
 * CertificateCoverageList — Phase B Task 7e / REQ-9.
 *
 * Read-only, per-quote-item view of every certificate (and "Свой расход"
 * row) currently attached to a single position. Mounted inside
 * `customs-item-dialog.tsx` (Wave 4 Task 10) under the «Сертификация»
 * section.
 *
 * Cards stack vertically, sorted `created_at DESC`. Two visual variants:
 *
 *   • emerald-bordered — `is_custom_expense=false`. Top row: a success
 *     `<Badge>` with `cert.type` and the copy «Покрыта общим
 *     сертификатом» (mockup `customs-after-phases.html` line 890). Sub-row
 *     prints `№{number} · доля {share_rub} ₽ ({share_percent}%
 *     пропорционально стоимости {item_value} / {total_value})`. Footer
 *     buttons: «Открыть сертификат» + «Отвязать» (the latter only when
 *     `canUnbind === true`).
 *
 *   • gray-bordered — `is_custom_expense=true`. Top row: a neutral
 *     `<Badge variant="secondary">` with copy «Расход» + `display_name`.
 *     Sub-row prints `доля {share_rub} ₽ ({share_percent}%)` (no
 *     proportional-to-cost suffix per REQ-9 AC#3). Footer buttons:
 *     «Подробнее» + «Отвязать» (role-gated).
 *
 *   • RED-bordered (priority OVER emerald) — when `cert.valid_until`
 *     falls on/before today (REQ-4 AC#3 / REQ-9 AC#5).
 *
 * Empty state is the caller's concern — when `attachedCerts` is empty we
 * render `null` and the per-item dialog falls through to the amber
 * «Привязать к существующему» / «Создать новый» card from REQ-8 / REQ-9
 * AC#8 (Task 7d / Task 7c).
 *
 * All numbers come pre-rounded from the API — this component never calls
 * `splitCostBatch`. Item-value / total-value come from `itemRubBasis` and
 * `totalRubBasis` which the parent derives once via `deriveRubBasis(...)`
 * and passes down for the proportional copy.
 */

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { formatRub } from "../lib/format-rub";
import type { Certificate } from "../model/types";

/**
 * One pre-computed share, paired with the certificate it covers.
 * Derived upstream — the list never re-runs `splitCostBatch`.
 */
export interface AttachedCertView {
  /** Full certificate row. */
  cert: Certificate;
  /** Kopek-exact RUB share for the *current* item. */
  share_rub: number;
  /** Percentage share (0..100) for the *current* item. */
  share_percent: number;
}

export interface CertificateCoverageListProps {
  /** UUID of the `quote_items` row whose attachments we render. */
  itemId: string;
  /**
   * Already-derived attachment payload, sorted in render order.
   * Sorting `created_at DESC` is the caller's responsibility (REQ-9 AC#4).
   */
  attachedCerts: AttachedCertView[];
  /** Total number of `quote_items` in the parent quote (informational copy). */
  totalQuoteItems: number;
  /**
   * RUB basis of the *current* item — used in the proportional-to-cost
   * copy «… пропорционально стоимости {itemRubBasis} / {totalRubBasis}».
   * Derived upstream via `deriveRubBasis(item)`.
   */
  itemRubBasis?: number;
  /** Sum of all `quote_items` RUB bases for the parent quote. */
  totalRubBasis?: number;
  /** When true, render the role-gated «Отвязать» button (REQ-9 AC#6). */
  canUnbind: boolean;
  /** Called when the user clicks «Отвязать» (only when `canUnbind`). */
  onUnbind?: (certId: string) => void;
  /** Called when the user clicks «Открыть сертификат» / «Подробнее». */
  onOpenDetails?: (cert: Certificate) => void;
}

/** True when `valid_until <= today` (REQ-4 AC#3). NULL → never expired. */
function isCertExpired(validUntil: string | null): boolean {
  if (!validUntil) return false;
  const expiry = new Date(validUntil);
  if (Number.isNaN(expiry.getTime())) return false;
  // Compare day-only — the cert is "expired" the day it lapses.
  const today = new Date();
  const todayDayOnly = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate(),
  );
  const expiryDayOnly = new Date(
    expiry.getFullYear(),
    expiry.getMonth(),
    expiry.getDate(),
  );
  return expiryDayOnly.getTime() <= todayDayOnly.getTime();
}

/**
 * Format an ISO date string `YYYY-MM-DD` directly without going through
 * `new Date()` (which would shift by the host timezone offset). Falls
 * back to `formatDateRussian` for full timestamps. Returns "" on null
 * to keep React happy.
 */
function formatCertDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (match) {
    const [, year, month, day] = match;
    return `${day}.${month}.${year}`;
  }
  return formatDateRussian(iso);
}

export function CertificateCoverageList({
  itemId: _itemId,
  attachedCerts,
  totalQuoteItems: _totalQuoteItems,
  itemRubBasis,
  totalRubBasis,
  canUnbind,
  onUnbind,
  onOpenDetails,
}: CertificateCoverageListProps) {
  // Empty list — caller renders the amber empty-state card (REQ-9 AC#8).
  if (attachedCerts.length === 0) {
    return null;
  }

  return (
    <div
      className="flex flex-col gap-2"
      data-testid="certificate-coverage-list"
    >
      {attachedCerts.map(({ cert, share_rub, share_percent }) => {
        const expired = isCertExpired(cert.valid_until);

        // Border priority (REQ-9 AC#5): red > emerald > gray.
        const borderClass = expired
          ? "border-red-900 bg-red-950/10"
          : cert.is_custom_expense
            ? "border-neutral-700 bg-neutral-900/40"
            : "border-emerald-900 bg-emerald-950/10";

        return (
          <div
            key={cert.id}
            className={`rounded-md border ${borderClass} p-3`}
            data-testid="certificate-coverage-card"
            data-cert-id={cert.id}
            data-expired={expired ? "true" : "false"}
            data-custom-expense={cert.is_custom_expense ? "true" : "false"}
          >
            {/* Top row: badge + copy */}
            <div className="text-sm flex items-center gap-2">
              {cert.is_custom_expense ? (
                <>
                  <Badge variant="secondary">Расход</Badge>
                  <span>{cert.display_name ?? ""}</span>
                </>
              ) : (
                <>
                  <Badge variant="default">{cert.type}</Badge>
                  <span>Покрыта общим сертификатом</span>
                </>
              )}
            </div>

            {/* Sub-row: number + share copy */}
            <div className="text-xs text-neutral-400 mt-1">
              {cert.is_custom_expense ? (
                <>
                  {"доля "}
                  <span className="text-amber-400">
                    {formatRub(share_rub)}
                  </span>
                  {` (${share_percent}%)`}
                </>
              ) : (
                <>
                  {`№${cert.number ?? ""} · доля `}
                  <span className="text-amber-400">
                    {formatRub(share_rub)}
                  </span>
                  {itemRubBasis !== undefined && totalRubBasis !== undefined
                    ? ` (${share_percent}% пропорционально стоимости ${formatRub(itemRubBasis)} / ${formatRub(totalRubBasis)})`
                    : ` (${share_percent}%)`}
                </>
              )}
            </div>

            {/* Optional expiry hint when valid_until set */}
            {cert.valid_until && !cert.is_custom_expense ? (
              <div className="text-xs text-neutral-500 mt-0.5">
                {`${expired ? "истёк" : "действует до"} ${formatCertDate(cert.valid_until)}`}
              </div>
            ) : null}

            {/* Footer buttons */}
            <div className="flex gap-2 mt-2">
              <Button
                size="xs"
                variant="outline"
                onClick={() => onOpenDetails?.(cert)}
                data-testid="cert-coverage-open-details"
              >
                {cert.is_custom_expense ? "Подробнее" : "Открыть сертификат"}
              </Button>
              {canUnbind ? (
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => onUnbind?.(cert.id)}
                  data-testid="cert-coverage-unbind"
                >
                  Отвязать
                </Button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
