"use client";

import { useMemo, useState } from "react";
import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";

import {
  paymentTypeLabel,
  type ResolvedRate,
} from "../model/types";

/**
 * Live-context for the auto-НДС formula display (Phase A — Req 7).
 *
 * Caller-supplied real numbers from the current item state — customs_value,
 * sum of all import-duty payment_types (IMP + IMPDEMP + IMPCOMP + ...) and
 * AKC. RateBreakdown uses these together with the selected NDS variant's
 * percent rate to render «(customs_value + duty + akc) × pct% = nds» in a
 * monospace box under the NDS row.
 *
 * When the prop is omitted (`undefined` / `null`), RateBreakdown falls back
 * to the simple badge rendering — keeps backwards compat with existing
 * callers (customs-item-dialog Phase 1 layout).
 */
export interface TotalContext {
  customs_value_rub: number;
  total_import_duty_rub: number;
  akc_rub: number;
}

export interface RateBreakdownProps {
  rates: ResolvedRate[];
  /** Phase 1: always null. When non-null, renders the итого row. */
  totalRub: number | null;
  source: string;
  /** Phase A — Req 7. When provided, NDS row renders live formula. */
  totalContext?: TotalContext | null;
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

/** Format a number with Russian thousand separators (NBSP between groups). */
function formatRub(n: number): string {
  return n.toLocaleString("ru-RU");
}

/**
 * Compose the auto-НДС formula string with real numbers — Req 7 AC#3.
 *
 * Returns `(customs_value + duty + akc) × pct% = nds` rendered with
 * Russian thousand separators. Returns null when the variant has no
 * percent rate (e.g., raw-string-only льготная without numeric value)
 * because we can't safely substitute a numeric pct in that case.
 */
export function composeNdsFormula(
  ctx: TotalContext,
  variant: ResolvedRate,
): string | null {
  if (
    variant.value_1_unit !== "percent" ||
    variant.value_1_number == null
  ) {
    return null;
  }
  const pct = variant.value_1_number;
  const base =
    ctx.customs_value_rub + ctx.total_import_duty_rub + ctx.akc_rub;
  const ndsAmount = (base * pct) / 100;
  return (
    "(" +
    formatRub(ctx.customs_value_rub) +
    " + " +
    formatRub(ctx.total_import_duty_rub) +
    " + " +
    formatRub(ctx.akc_rub) +
    ") × " +
    pct +
    "% = " +
    formatRub(ndsAmount)
  );
}

/**
 * Build the alternative-льготы tooltip text — Req 7 AC#5.
 *
 * Lists every NDS variant other than the selected one, in the form
 * «category_ru (condition_text): pct%» — one per line. Returns null
 * when there are no alternatives (single-variant NDS group).
 */
export function composeNdsTooltip(
  variants: ResolvedRate[],
  selectedIdx: number,
): string | null {
  const lines: string[] = [];
  for (let i = 0; i < variants.length; i += 1) {
    if (i === selectedIdx) continue;
    const v = variants[i];
    const label = v.category_ru ?? "Вариант";
    const cond = v.condition_text ? ` (${v.condition_text})` : "";
    const rate = formatRate(v);
    lines.push(`${label}${cond}: ${rate}`);
  }
  if (lines.length === 0) return null;
  return "Льготные категории:\n" + lines.join("\n");
}

interface RateGroup {
  payment_type: string;
  variants: ResolvedRate[];
  /** Index of the variant currently selected by the user (default-aware). */
  defaultIdx: number;
}

/** Group rates by payment_type — backend may emit multiple variants per
 * payment when льготные and стандартная ставки coexist (migration 301).
 * Pre-selected index = first variant flagged is_default, else 0. */
function groupRates(rates: ResolvedRate[]): RateGroup[] {
  const byType = new Map<string, ResolvedRate[]>();
  for (const r of rates) {
    const list = byType.get(r.payment_type) ?? [];
    list.push(r);
    byType.set(r.payment_type, list);
  }
  const groups: RateGroup[] = [];
  byType.forEach((variants, payment_type) => {
    const idx = variants.findIndex((v) => v.is_default);
    groups.push({
      payment_type,
      variants,
      defaultIdx: idx >= 0 ? idx : 0,
    });
  });
  return groups;
}

/**
 * Display a rate breakdown for a resolved customs query.
 *
 * Migration 301 — multi-variant flow: when the resolver returns several
 * variants for one payment_type (льготная + стандартная), render a
 * selector so the customs-specialist picks the rate applicable to the
 * actual product. Default selection = is_default=true variant (the
 * "прочее" / стандартная rate), so a wrong льготная never silently wins.
 *
 * Phase A — Req 7: when caller supplies `totalContext`, NDS row renders a
 * monospace formula box «(customs_value + duty + akc) × pct% = nds» with
 * real numbers from the item state. Without the prop the row falls back
 * to the simple badge — backwards compat with existing callers.
 *
 * Phase 1 limitation: backend cannot compute RUB amounts because the
 * `/resolve-rates` request body lacks customs_value/weight/quantity
 * inputs. When `totalRub` is null we surface that explicitly.
 */
export function RateBreakdown({
  rates,
  totalRub,
  source,
  totalContext,
}: RateBreakdownProps) {
  const groups = useMemo(() => groupRates(rates), [rates]);

  if (groups.length === 0) {
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

      <ul className="flex flex-col gap-3">
        {groups.map((group) => (
          <RateGroupRow
            key={group.payment_type}
            group={group}
            totalContext={totalContext}
          />
        ))}
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

function RateGroupRow({
  group,
  totalContext,
}: {
  group: RateGroup;
  totalContext?: TotalContext | null;
}) {
  const [selectedIdx, setSelectedIdx] = useState(group.defaultIdx);
  const label = paymentTypeLabel(group.payment_type);
  const selected = group.variants[selectedIdx] ?? group.variants[0];
  const isMulti = group.variants.length > 1;
  const isNds = group.payment_type === "NDS";
  const ndsFormula =
    isNds && totalContext ? composeNdsFormula(totalContext, selected) : null;
  const ndsTooltip = isNds
    ? composeNdsTooltip(group.variants, selectedIdx)
    : null;

  if (!isMulti) {
    // Single-variant row — keep the compact layout. Show льгота context
    // when present so users see why the rate is what it is.
    const display = formatRate(selected);
    const titleText = ndsTooltip ?? selected.raw_value_string ?? display;
    return (
      <li className="flex flex-col gap-1" title={titleText}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-foreground">{label}</span>
            {selected.description ? (
              <span className="truncate text-[11px] text-muted-foreground">
                {selected.description}
              </span>
            ) : null}
          </div>
          <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
            {display}
          </span>
        </div>
        {ndsFormula ? (
          <div
            className="font-mono text-xs text-amber-400"
            data-testid="nds-formula"
          >
            {ndsFormula}
          </div>
        ) : null}
      </li>
    );
  }

  return (
    <li
      className="flex flex-col gap-1.5"
      title={ndsTooltip ?? undefined}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-foreground">{label}</span>
        <span className="text-[10px] font-medium text-muted-foreground">
          {group.variants.length} варианта · выберите применимый
        </span>
      </div>

      {ndsFormula ? (
        <div
          className="font-mono text-xs text-amber-400"
          data-testid="nds-formula"
        >
          {ndsFormula}
        </div>
      ) : null}

      <div className="flex flex-col gap-1 rounded-md border border-border bg-muted/30 p-2">
        {group.variants.map((variant, idx) => {
          const display = formatRate(variant);
          const checked = idx === selectedIdx;
          return (
            <label
              key={`${group.payment_type}-variant-${idx}`}
              className={`flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 transition-colors ${
                checked
                  ? "bg-card ring-1 ring-primary/30"
                  : "hover:bg-card/60"
              }`}
            >
              <input
                type="radio"
                name={`rate-variant-${group.payment_type}`}
                checked={checked}
                onChange={() => setSelectedIdx(idx)}
                className="mt-0.5 cursor-pointer"
              />
              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs tabular-nums text-foreground">
                    {display}
                  </span>
                  {variant.is_default ? (
                    <Badge variant="outline" className="text-[9px]">
                      по умолчанию
                    </Badge>
                  ) : null}
                </div>
                {variant.category_ru ? (
                  <span className="text-[11px] font-medium text-muted-foreground">
                    {variant.category_ru}
                  </span>
                ) : null}
                {variant.description ? (
                  <span className="text-[11px] text-muted-foreground">
                    {variant.description}
                  </span>
                ) : null}
                {variant.condition_text ? (
                  <span className="text-[10px] text-muted-foreground/70">
                    {variant.condition_text}
                  </span>
                ) : null}
                {variant.legal_document || variant.legal_link ? (
                  <a
                    href={variant.legal_link ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[10px] text-primary hover:underline"
                    onClick={(e) => {
                      // Don't toggle the radio when clicking the link.
                      e.stopPropagation();
                      if (!variant.legal_link) {
                        e.preventDefault();
                      }
                    }}
                  >
                    <ExternalLink size={10} />
                    {variant.legal_document ?? "Документ"}
                  </a>
                ) : null}
              </div>
            </label>
          );
        })}
      </div>
    </li>
  );
}
