"use client";

/**
 * SpecialDutyBlock — orange-tinted card surfacing антидемпинговые / компенсационные /
 * специальные защитные / сезонные пошлины returned by the Alta resolver.
 *
 * Per Phase A Req 5 (`.kiro/specs/customs-tariff-completeness/requirements.md`):
 *   - IMPDEMP renders a full orange card with explanatory line + radio-selection
 *     when several variants apply (e.g. multiple producer-specific rates).
 *   - IMPCOMP / IMPDOP / IMPTMP render compact one-line cards with distinct
 *     colour coding (red / blue / slate respectively) — they're shown but rarely
 *     applied so they take less vertical space.
 *
 * The component is purely presentational: parent supplies the filtered variants
 * + currently-selected variant code and listens for selection changes.
 *
 * Visibility: parent must filter variants by `payment_type` before passing in;
 * an empty variants array yields a null render.
 */

import { ExternalLink } from "lucide-react";

import { type ResolvedRate } from "../model/types";

export type SpecialDutyType = "IMPDEMP" | "IMPCOMP" | "IMPDOP" | "IMPTMP";

export interface SpecialDutyBlockProps {
  /** Filtered list of resolver rates whose payment_type matches `paymentType`. */
  variants: ResolvedRate[];
  paymentType: SpecialDutyType;
  /** Selected variant identifier — typically the rate's category_code. */
  selectedCode: string | null;
  onSelect: (code: string) => void;
  /** Optional country display name for the explanation line (IMPDEMP only). */
  countryName?: string;
  /** Optional ТН ВЭД code for the explanation line (IMPDEMP only). */
  tnvedCode?: string;
}

interface DutyStyle {
  /** Outer card wrapper (border + tinted background). */
  card: string;
  /** Inline rate badge styling. */
  badge: string;
  /** Russian heading rendered at the top of the card. */
  title: string;
}

const TYPE_STYLES: Record<SpecialDutyType, DutyStyle> = {
  IMPDEMP: {
    card: "border-orange-900 bg-orange-950/20",
    badge: "bg-amber-700/30 text-amber-300",
    title: "Антидемпинговая пошлина",
  },
  IMPCOMP: {
    card: "border-red-900 bg-red-950/20",
    badge: "bg-red-700/30 text-red-300",
    title: "Компенсационная пошлина",
  },
  IMPDOP: {
    card: "border-blue-900 bg-blue-950/20",
    badge: "bg-blue-700/30 text-blue-300",
    title: "Специальная защитная пошлина",
  },
  IMPTMP: {
    card: "border-slate-700 bg-slate-900/50",
    badge: "bg-slate-700/30 text-slate-300",
    title: "Сезонная пошлина",
  },
};

/** Format the rate value to a short string (`19.4%` or fallback raw string). */
function formatRateValue(rate: ResolvedRate): string {
  if (rate.value_1_unit === "percent" && rate.value_1_number != null) {
    return `${rate.value_1_number}%`;
  }
  if (rate.raw_value_string) return rate.raw_value_string;
  if (rate.value_1_number != null) return String(rate.value_1_number);
  return "—";
}

export function SpecialDutyBlock({
  variants,
  paymentType,
  selectedCode,
  onSelect,
  countryName,
  tnvedCode,
}: SpecialDutyBlockProps) {
  if (variants.length === 0) return null;

  const styles = TYPE_STYLES[paymentType];
  const isFullCard = paymentType === "IMPDEMP";
  const firstVariant = variants[0];
  const rateText = formatRateValue(firstVariant);

  if (!isFullCard) {
    // Compact single-line card for IMPCOMP / IMPDOP / IMPTMP — these
    // rarely apply, so we use less vertical space.
    return (
      <div className={`rounded-md border ${styles.card} p-2`}>
        <div className="flex items-center gap-2 text-xs">
          <span
            className={`inline-flex items-center rounded-md px-1.5 py-0.5 font-medium ${styles.badge}`}
          >
            {styles.title}
          </span>
          <span className="font-mono tabular-nums">{rateText}</span>
          <span className="truncate text-muted-foreground">
            {firstVariant.order_ref ?? "—"}
          </span>
          {firstVariant.legal_link && (
            <a
              href={firstVariant.legal_link}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto inline-flex items-center gap-1 text-blue-400 hover:underline"
            >
              <ExternalLink size={10} />
              документ
            </a>
          )}
        </div>
      </div>
    );
  }

  // Full orange card for IMPDEMP — Req 5 AC#1-6.
  return (
    <div className={`rounded-md border ${styles.card} space-y-2 p-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-sm font-medium text-foreground">
          {styles.title}
        </div>
        <span
          className={`inline-flex items-center rounded-md px-2 py-0.5 font-mono text-xs font-medium tabular-nums ${styles.badge}`}
        >
          {rateText}
        </span>
      </div>

      <div className="text-xs text-neutral-300">
        {firstVariant.order_ref ?? "—"}
      </div>

      {countryName && tnvedCode && (
        <div className="text-[11px] text-neutral-500">
          Применяется потому что: страна = {countryName}, ТН ВЭД попадает в
          решение.
        </div>
      )}

      {variants.length > 1 && (
        <div className="mt-2 space-y-1">
          <div className="text-[11px] text-neutral-500">
            Варианты ({variants.length}):
          </div>
          {variants.map((v) => {
            const code = v.category_code ?? "";
            const checked = code === selectedCode;
            return (
              <label
                key={code || v.order_ref || formatRateValue(v)}
                className="flex cursor-pointer items-start gap-2 rounded p-1.5 hover:bg-orange-900/20"
              >
                <input
                  type="radio"
                  name={`${paymentType}-variant`}
                  checked={checked}
                  onChange={() => onSelect(code)}
                  className="mt-0.5"
                />
                <div className="flex-1 text-xs">
                  <span className="font-mono tabular-nums">
                    {formatRateValue(v)}
                  </span>
                  {v.description && (
                    <span className="ml-2 text-neutral-500">
                      {v.description}
                    </span>
                  )}
                </div>
              </label>
            );
          })}
        </div>
      )}

      {firstVariant.legal_link && (
        <a
          href={firstVariant.legal_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-blue-400 hover:underline"
        >
          <ExternalLink size={12} />
          документ
        </a>
      )}
    </div>
  );
}
