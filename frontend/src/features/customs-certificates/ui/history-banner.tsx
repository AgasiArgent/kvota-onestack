"use client";

/**
 * HistoryBanner — Phase B Wave 3 Task 7f / REQ-5.
 *
 * Surfaces the most recent matching certificate the customs specialist saw
 * for the current `(hs_code, brand, supplier_id)` combination so they can
 * either re-apply it (still actual) or create a new one with the prior
 * type/cost as defaults (expired).
 *
 * Two variants — selected by `match.is_actual`:
 *
 *   - **apply** (`is_actual === true`) — info-blue tinted card. Copy:
 *     «Возможно подойдёт сертификат {type} №{number} от {DD.MM.YYYY},
 *     ~{cost_rub}₽» + «Применить» button + «×» dismiss.
 *
 *   - **create-new** (`is_actual === false`) — amber/warning tinted card.
 *     Copy: «Прежний сертификат истёк {DD.MM.YYYY}, нужен новый ~{cost_rub}₽»
 *     + «Создать новый» button + «×» dismiss.
 *
 * Pure presentation component — the parent owns the apply/create-new/dismiss
 * state. When `match` is `null` the banner renders nothing (parent gating
 * fallback so the markup tree stays predictable).
 *
 * Date formatting goes through `formatDateRussian` (LD-11, REQ-4 AC#7) — the
 * Phase A helper is the single source of truth for the DD.MM.YYYY format.
 * RUB formatting goes through `formatRub` (Wave 3 Task 6) — see
 * `lib/format-rub.ts` for NBSP / kopek-grouping rules.
 *
 * Compliance (LD-13):
 *   - shadcn `<Button variant="outline|ghost">` — no raw `<button>`.
 *   - Tailwind v4 design tokens for borders/backgrounds — no hex codes.
 *   - No `transition: all`, no `transform: translateY()` on hover.
 *   - Inter font inherited from layout.
 */

import { Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatDateRussian } from "@/features/customs-history/lib/format-date";

import { formatRub } from "../lib/format-rub";
import type { HistoryCertMatch } from "../model/types";

export interface HistoryBannerProps {
  /**
   * History match returned by `GET /api/customs/certificates/history`.
   * `null` collapses the banner to nothing — see component note above.
   */
  match: HistoryCertMatch | null;
  /**
   * Click handler for the «Применить» button (apply variant only).
   * Receives the matched cert id so the parent can `POST /items` against
   * the existing certificate (REQ-5 AC#8).
   */
  onApply?: (certId: string) => void;
  /**
   * Click handler for the «Создать новый» button (create-new variant only).
   * Receives a preset `{type, cost_rub}` so the parent can pre-fill the
   * `CertificateModal` (REQ-4 AC#5 / REQ-5 AC#9).
   */
  onCreateNew?: (preset: { type: string; cost_rub: number }) => void;
  /**
   * Click handler for the «×» dismiss button. The banner does not manage
   * its own visibility — the parent must remove the match from state to
   * actually hide it (REQ-5 AC#10 — no silent autofill).
   */
  onDismiss?: () => void;
}

/**
 * Renders the history banner — see component-level docstring for variants.
 *
 * Returns `null` when `match` is `null`/`undefined` so the caller can mount
 * `<HistoryBanner match={...} ... />` unconditionally.
 */
export function HistoryBanner({
  match,
  onApply,
  onCreateNew,
  onDismiss,
}: HistoryBannerProps) {
  if (!match) return null;

  const isActual = match.is_actual === true;
  const variant: "apply" | "create-new" = isActual ? "apply" : "create-new";

  // Wrapper classes — design tokens via Tailwind utility classes only.
  // Apply variant uses the project's info/blue tone (sky-* palette in the
  // existing customs-history banner, kept for visual continuity); create-new
  // variant uses amber tones to mark the warning state.
  const wrapperClass = isActual
    ? "border-blue-900 bg-blue-950/20"
    : "border-amber-900 bg-amber-950/20";

  // Pre-format the recurring tokens once so the JSX stays focused on layout.
  const issuedAtRu = formatDateRussian(match.issued_at);
  const validUntilRu = formatDateRussian(match.valid_until);
  const costFormatted = formatRub(match.cost_rub);
  const numberFragment = match.number ? `№${match.number} ` : "";

  // Copy must match REQ-5 AC#6 / AC#7 exactly. Keep both variants here so a
  // future copy change lives in a single component.
  const headlineApply =
    `Возможно подойдёт сертификат ${match.type} ${numberFragment}` +
    `от ${issuedAtRu}, ~${costFormatted}`;
  const headlineCreateNew =
    `Прежний сертификат истёк ${validUntilRu}, нужен новый ~${costFormatted}`;
  const headline = isActual ? headlineApply : headlineCreateNew;

  return (
    <div
      className={
        "flex items-center justify-between gap-2 rounded-md border " +
        `${wrapperClass} px-3 py-2 mb-3`
      }
      data-testid="customs-cert-history-banner"
      data-variant={variant}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <Sparkles size={14} className="shrink-0 text-blue-400" />
        <div className="text-xs text-foreground/90 truncate">{headline}</div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {isActual ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onApply?.(match.cert_id)}
            className="text-xs h-7"
          >
            Применить
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              onCreateNew?.({ type: match.type, cost_rub: match.cost_rub })
            }
            className="text-xs h-7"
          >
            Создать новый
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={onDismiss}
          className="h-7 w-7 p-0"
          aria-label="Скрыть подсказку"
        >
          <X size={14} />
        </Button>
      </div>
    </div>
  );
}
