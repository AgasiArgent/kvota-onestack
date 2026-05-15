"use client";

import { useRef, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import Handsontable from "handsontable";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { updateQuoteItem } from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";
import { normalizeHsCode } from "@/shared/lib/hs-code";
import type { CustomsAutofillSuggestion } from "@/features/customs-autofill";
import type { SystemView } from "@/features/customs-certificates";
import { CustomsViewHintBanner } from "@/features/customs-certificates";
import {
  formatDutyChip,
  type DutyRateType,
  type DutySign,
  type DutyUnit,
} from "@/features/customs-rate-resolve";

import { CUSTOMS_AVAILABLE_COLUMNS } from "./customs-columns";
import { isSystemViewId, resolveSystemView } from "./customs-views";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

// ---------------------------------------------------------------------------
// REQ-11 (Phase B Wave 4 Task 11) — synthetic `system:*` view resolver.
//
// The customs items registry exposes 4 client-side virtual views (see
// `./customs-views.ts`). This file owns the URL → view → column-filter
// resolution so the table can react to `?customs_view=` directly,
// without waiting for the parent (`customs-step.tsx`) to thread a prop
// through. UUID rows from `kvota.user_table_views` keep the old prop-based
// path — only `system:*` IDs trigger the override.
//
// Helpers are exported so the unit-test suite can exercise them without
// rendering the full Handsontable (no jsdom in this workspace — see
// `__tests__/customs-antidumping.test.ts`). All three helpers are pure.
// ---------------------------------------------------------------------------

/**
 * Resolve the active **system** view from a raw URL param.
 *
 * Returns the matching {@link SystemView} when:
 *   - `viewParam` matches the `system:*` synthetic-ID pattern AND
 *   - the ID corresponds to a known entry in `CUSTOMS_SYSTEM_VIEWS`.
 *
 * Returns `null` for everything else — UUIDs from `user_table_views`,
 * `null`/`undefined`/empty strings, and unknown `system:*` sub-ids
 * (graceful degradation per REQ-11 AC#7). Callers compose this with the
 * existing user-view lookup performed in `customs-step.tsx`.
 */
export function resolveActiveSystemView(
  viewParam: string | null | undefined,
): SystemView | null {
  if (!isSystemViewId(viewParam)) return null;
  return resolveSystemView(viewParam);
}

/**
 * Compute the visible column list passed to {@link filterColumns}.
 *
 * Precedence:
 *   1. If a system view is active, its `visibleColumnIds` win — the
 *      `system:all` row enumerates every column so the result matches
 *      the no-filter behaviour, just routed through `filterColumns`.
 *   2. Otherwise the prop from `customs-step.tsx` (a UUID-based user
 *      view's columns, or `undefined` for «show all») is returned
 *      unchanged.
 *
 * The function is pure so unit tests can assert routing without
 * rendering Handsontable.
 */
export function effectiveVisibleColumns(
  activeSystemView: SystemView | null,
  visibleColumnsProp: readonly string[] | undefined,
): readonly string[] | undefined {
  if (activeSystemView !== null) return activeSystemView.visibleColumnIds;
  return visibleColumnsProp;
}

/**
 * Whether the {@link CustomsViewHintBanner} should be mounted above the
 * Handsontable. The banner self-collapses to `null` for the default
 * `system:all` view and for `null` inputs, so this predicate just guards
 * against rendering an empty wrapper element.
 */
export function shouldRenderHintBanner(
  activeSystemView: SystemView | null,
): boolean {
  return activeSystemView !== null && activeSystemView.id !== "system:all";
}

function ext<T>(row: unknown): T {
  return row as T;
}

// ---------------------------------------------------------------------------
// Row model — mirrors DB columns after migration 293:
//   dropped: customs_ds_sgr, customs_marking
//   renamed: customs_psn_pts → customs_psm_pts
// ---------------------------------------------------------------------------

/**
 * Row 9 — JSONB payload mirror of `services.alta_client.Rate`. Stored on
 * `kvota.quote_items.customs_manual_rate_payload` when the user enters a
 * Manual duty rate via the per-item dialog. The Handsontable «Пошлина»
 * renderer reads this so the chip can display the combined-rate formula
 * (`10% > 0.5 EUR/kg`) instead of just the percent slot value.
 */
interface ManualRatePayload {
  duty_rate_type?: DutyRateType | null;
  value_1_number?: number | null;
  value_1_unit?: string | null;
  value_2_number?: number | null;
  value_2_unit?: string | null;
  sign_1?: DutySign | null;
}

type ItemExtras = {
  hs_code?: string | null;
  customs_duty?: number | null;
  customs_duty_per_kg?: number | null;
  customs_util_fee?: number | null;
  customs_excise?: number | null;
  customs_psm_pts?: string | null;
  customs_notification?: string | null;
  customs_licenses?: string | null;
  customs_eco_fee?: number | null;
  customs_honest_mark?: string | null;
  import_banned?: boolean | null;
  import_ban_reason?: string | null;
  license_ds_required?: boolean | null;
  license_ss_required?: boolean | null;
  license_sgr_required?: boolean | null;
  // REQ-7 customs-phase-1 — country of origin (read-only column).
  // Edits happen through customs-item-dialog (CustomsCountryDropdown).
  country_of_origin_oksm?: number | null;
  // Row 9 (Testing 2) — Manual-mode round-trip data so the table can
  // render a formula chip when the user picked combined/specific rate.
  customs_manual_override?: boolean | null;
  customs_manual_rate_payload?: ManualRatePayload | null;
  // REQ-6 customs-phase-A — special-duty variants from snapshot.
  // Multiple shapes supported (defensive read-side):
  //   - Phase 1 snapshot: `customs_rates_snapshot.rates: SpecialDutyVariant[]`
  //   - Phase A user choices: `tnved_user_choices_chosen.chosen_*_variant`
  //   - Resolved live: `_resolved_rates_by_payment_type.IMPDEMP[]`
  customs_rates_snapshot?: { rates?: unknown[] } | null;
  _resolved_rates_by_payment_type?: Record<string, unknown[]> | null;
  tnved_user_choices_chosen?: {
    chosen_impdemp_variant?: unknown;
    chosen_impcomp_variant?: unknown;
    chosen_impdop_variant?: unknown;
    chosen_imptmp_variant?: unknown;
  } | null;
};

/**
 * REQ-6: payment_types rendered in the «Антидемпинг» column.
 * IMPDEMP is the priority case (МастерБэринг товары часто из Китая).
 * IMPCOMP/IMPDOP/IMPTMP are rendered with distinct colour badges per AC #6.
 */
const SPECIAL_DUTY_PAYMENT_TYPES = [
  "IMPDEMP",
  "IMPCOMP",
  "IMPDOP",
  "IMPTMP",
] as const;
type SpecialDutyPaymentType = (typeof SPECIAL_DUTY_PAYMENT_TYPES)[number];

/**
 * Subset of fields read from a snapshot variant. All optional — the renderer
 * falls back to «—» when essential data (value_1_number) is missing.
 */
export interface SpecialDutyVariant {
  payment_type: SpecialDutyPaymentType;
  value_1_number: number;
  order_ref?: string | null;
  legal_link?: string | null;
}

/**
 * Shorten a КТС/EEK decision reference for compact badge display.
 *   "Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины ...)" → "Реш.702 КТС"
 *   "Постановление 688 ..." → first 18 chars + ellipsis
 *   null/undefined/empty → ""
 */
export function shortenDecisionRef(orderRef: string | null | undefined): string {
  if (!orderRef) return "";
  const match = orderRef.match(/Решение\s+(\d+).*?КТС/i);
  if (match) return `Реш.${match[1]} КТС`;
  if (orderRef.length > 20) return orderRef.slice(0, 18) + "…";
  return orderRef;
}

/**
 * Defensive snapshot reader — returns the first applicable special-duty
 * variant (IMPDEMP priority, then IMPCOMP/IMPDOP/IMPTMP). Returns null
 * when no special-duty variant is present in the item data.
 *
 * Multiple snapshot shapes are tried in priority order:
 *   1. `customs_rates_snapshot.rates` (Phase 1 frozen snapshot)
 *   2. `_resolved_rates_by_payment_type[type][0]` (Phase A live resolve)
 *   3. `tnved_user_choices_chosen.chosen_<type>_variant` (Phase A user choice)
 */
export function readSpecialDutyVariant(
  item: ItemExtras
): SpecialDutyVariant | null {
  // Shape 1: Phase 1 customs_rates_snapshot.rates[] flat array
  const snapshotRates = item.customs_rates_snapshot?.rates;
  if (Array.isArray(snapshotRates)) {
    for (const targetType of SPECIAL_DUTY_PAYMENT_TYPES) {
      const found = snapshotRates.find(
        (r) =>
          isPlainObject(r) &&
          (r as Record<string, unknown>).payment_type === targetType &&
          typeof (r as Record<string, unknown>).value_1_number === "number"
      );
      if (found) return normaliseVariant(found, targetType);
    }
  }

  // Shape 2: Phase A live-resolve grouped map
  const grouped = item._resolved_rates_by_payment_type;
  if (grouped && typeof grouped === "object") {
    for (const targetType of SPECIAL_DUTY_PAYMENT_TYPES) {
      const list = grouped[targetType];
      if (Array.isArray(list) && list.length > 0) {
        const first = list[0];
        if (
          isPlainObject(first) &&
          typeof (first as Record<string, unknown>).value_1_number === "number"
        ) {
          return normaliseVariant(first, targetType);
        }
      }
    }
  }

  // Shape 3: Phase A user-chosen variant per migration 304
  const chosen = item.tnved_user_choices_chosen;
  if (chosen) {
    const map: Record<SpecialDutyPaymentType, unknown> = {
      IMPDEMP: chosen.chosen_impdemp_variant,
      IMPCOMP: chosen.chosen_impcomp_variant,
      IMPDOP: chosen.chosen_impdop_variant,
      IMPTMP: chosen.chosen_imptmp_variant,
    };
    for (const targetType of SPECIAL_DUTY_PAYMENT_TYPES) {
      const v = map[targetType];
      if (
        isPlainObject(v) &&
        typeof (v as Record<string, unknown>).value_1_number === "number"
      ) {
        return normaliseVariant(v, targetType);
      }
    }
  }

  return null;
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function normaliseVariant(
  raw: unknown,
  paymentType: SpecialDutyPaymentType
): SpecialDutyVariant {
  const r = raw as Record<string, unknown>;
  return {
    payment_type: paymentType,
    value_1_number: r.value_1_number as number,
    order_ref:
      typeof r.order_ref === "string" && r.order_ref.length > 0
        ? r.order_ref
        : null,
    legal_link:
      typeof r.legal_link === "string" && r.legal_link.length > 0
        ? r.legal_link
        : null,
  };
}

/** Tailwind-class colour scheme per payment_type (matches Req 6 AC #6). */
const SPECIAL_DUTY_BADGE_CLASS: Record<SpecialDutyPaymentType, string> = {
  IMPDEMP: "bg-amber-700/30 text-amber-300",
  IMPCOMP: "bg-red-700/30 text-red-300",
  IMPDOP: "bg-blue-700/30 text-blue-300",
  IMPTMP: "bg-slate-700/30 text-slate-300",
};

/** Russian label for the tooltip prefix per payment_type. */
const SPECIAL_DUTY_LABEL: Record<SpecialDutyPaymentType, string> = {
  IMPDEMP: "Антидемпинговая пошлина",
  IMPCOMP: "Компенсационная пошлина",
  IMPDOP: "Специальная защитная пошлина",
  IMPTMP: "Сезонная пошлина",
};

/**
 * Compose a multi-line tooltip for the special-duty badge:
 *   «Антидемпинговая пошлина
 *    Решение 702 от 22.06.2011 КТС (...)
 *    https://alta.ru/tamdoc/...»
 */
export function buildSpecialDutyTooltip(variant: SpecialDutyVariant): string {
  const parts: string[] = [SPECIAL_DUTY_LABEL[variant.payment_type]];
  if (variant.order_ref) parts.push(variant.order_ref);
  if (variant.legal_link) parts.push(variant.legal_link);
  return parts.join("\n");
}

/**
 * Pure merge helper for the inline «Пошлина» (`customs_duty_composite`)
 * edit path. Centralizes the rules:
 *
 *   1. Re-emit the value under `customs_duty` or `customs_duty_per_kg`
 *      based on the row's current storage mode (which slot is non-null).
 *   2. Always null the other slot so the row can only carry one duty
 *      value at a time.
 *   3. Testing 2 row 26 — if the row is currently in Manual override
 *      mode (a previously-saved combined/specific rate), clear the
 *      Manual snapshot so the renderer falls back to the Auto branch.
 *      Without this, the formula chip + «M» badge keeps painting the
 *      stale `customs_manual_rate_payload` and the user perceives
 *      «ячейка не редактируется».
 *
 * Exported so the regression test covers the merge rules directly without
 * having to mount Handsontable in jsdom.
 */
export interface DutyCompositeRowState {
  customs_duty_per_kg: number | null;
  customs_manual_override: boolean;
}

export interface DutyCompositeUpdates {
  customs_duty: number | null;
  customs_duty_per_kg: number | null;
  customs_manual_override?: false;
  customs_manual_rate_payload?: null;
}

export function buildDutyCompositeUpdates(
  rawValue: unknown,
  rowState: DutyCompositeRowState,
): DutyCompositeUpdates {
  const parsed = parseFloat(String(rawValue));
  const num = Number.isNaN(parsed) ? null : parsed;
  const mode: DutyMode = rowState.customs_duty_per_kg != null ? "perKg" : "pct";
  const updates: DutyCompositeUpdates =
    mode === "perKg"
      ? { customs_duty: null, customs_duty_per_kg: num }
      : { customs_duty: num, customs_duty_per_kg: null };
  if (rowState.customs_manual_override) {
    updates.customs_manual_override = false;
    updates.customs_manual_rate_payload = null;
  }
  return updates;
}

/**
 * Logical column keys (order matches HoT column array below).
 *
 * Exported (via {@link CUSTOMS_AVAILABLE_COLUMNS}) so the table-views
 * settings dialog can present the same canonical column list.
 */
const COLUMN_KEYS = [
  "expand",
  "position",
  "brand",
  "product_code",
  "product_name",
  "quantity",
  "supplier_country",
  "hs_code",
  "country_of_origin_oksm",
  "customs_duty_composite",
  "customs_util_fee",
  "customs_excise",
  "customs_antidumping",
  "customs_psm_pts",
  "customs_notification",
  "customs_licenses",
  "customs_eco_fee",
  "customs_honest_mark",
  "import_banned",
  "import_ban_reason",
  "license_ds_required",
  "license_ss_required",
  "license_sgr_required",
] as const;

type DutyMode = "pct" | "perKg";

interface RowData {
  id: string;
  position: number;
  brand: string;
  product_code: string;
  product_name: string;
  quantity: number | null;
  supplier_country: string;
  hs_code: string;

  /**
   * REQ-7 customs-phase-1 — country of origin OKSM digital code, displayed
   * read-only in the grid. Edits go through customs-item-dialog so the
   * searchable dropdown standard is preserved (memory feedback_searchable_select).
   */
  country_of_origin_oksm: number | null;

  /** Composite display value — mode determined by which storage column is set. */
  customs_duty_composite: number | null;
  /** Actual storage — only one of these is non-null per row. */
  customs_duty: number | null;
  customs_duty_per_kg: number | null;
  /**
   * Row 9 — when true the renderer formats the manual rate chip
   * (`10% > 0.5 EUR/kg`) using the JSONB payload below.
   */
  customs_manual_override: boolean;
  customs_manual_rate_payload: ManualRatePayload | null;

  customs_util_fee: number | null;
  customs_excise: number | null;
  /**
   * REQ-6 customs-phase-A — read-only computed value for the «Антидемпинг»
   * column. Stores the resolved special-duty variant (priority IMPDEMP →
   * IMPCOMP → IMPDOP → IMPTMP), or null when no special-duty applies.
   * Editing routes through the per-item dialog.
   */
  customs_antidumping: SpecialDutyVariant | null;
  customs_psm_pts: string;
  customs_notification: string;
  customs_licenses: string;
  customs_eco_fee: number | null;
  customs_honest_mark: string;
  import_banned: boolean;
  import_ban_reason: string;
  license_ds_required: boolean;
  license_ss_required: boolean;
  license_sgr_required: boolean;
}

function resolveDutyMode(
  _duty: number | null | undefined,
  dutyPerKg: number | null | undefined,
): DutyMode {
  return dutyPerKg != null ? "perKg" : "pct";
}

function itemToRow(
  item: QuoteItemRow,
  invoiceCountryMap: Map<string, string>,
  supplierByQi: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >,
): RowData {
  const extras = ext<ItemExtras>(item);
  const supplier = supplierByQi.get(item.id) ?? null;
  const country =
    supplier?.supplier_country ??
    (supplier?.invoice_id
      ? invoiceCountryMap.get(supplier.invoice_id) ?? ""
      : "");

  const duty = extras.customs_duty ?? null;
  const dutyPerKg = extras.customs_duty_per_kg ?? null;
  const composite = dutyPerKg != null ? dutyPerKg : duty;

  return {
    id: item.id,
    position: item.position ?? 0,
    brand: item.brand ?? "",
    product_code: item.product_code ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    supplier_country: country,
    hs_code: extras.hs_code ?? "",
    country_of_origin_oksm: extras.country_of_origin_oksm ?? null,

    customs_duty_composite: composite,
    customs_duty: duty,
    customs_duty_per_kg: dutyPerKg,
    customs_manual_override: Boolean(extras.customs_manual_override),
    customs_manual_rate_payload: extras.customs_manual_rate_payload ?? null,

    customs_util_fee: extras.customs_util_fee ?? null,
    customs_excise: extras.customs_excise ?? null,
    customs_antidumping: readSpecialDutyVariant(extras),
    customs_psm_pts: extras.customs_psm_pts ?? "",
    customs_notification: extras.customs_notification ?? "",
    customs_licenses: extras.customs_licenses ?? "",
    customs_eco_fee: extras.customs_eco_fee ?? null,
    customs_honest_mark: extras.customs_honest_mark ?? "",
    import_banned: extras.import_banned ?? false,
    import_ban_reason: extras.import_ban_reason ?? "",
    license_ds_required: extras.license_ds_required ?? false,
    license_ss_required: extras.license_ss_required ?? false,
    license_sgr_required: extras.license_sgr_required ?? false,
  };
}

const NUMERIC_FIELDS = new Set([
  "customs_util_fee",
  "customs_excise",
  "customs_eco_fee",
]);

const BOOLEAN_FIELDS = new Set([
  "import_banned",
  "license_ds_required",
  "license_ss_required",
  "license_sgr_required",
]);

const TEXT_FIELDS = new Set([
  "hs_code",
  "customs_psm_pts",
  "customs_notification",
  "customs_licenses",
  "customs_honest_mark",
  "import_ban_reason",
]);

function headerWithTooltip(label: string, tooltip: string): string {
  return `<span title="${tooltip}">${label}</span>`;
}

const numericTooltip = "Значение за единицу товара";

/**
 * Static column headers — defined at module level to prevent
 * Handsontable re-initialization issues on React re-renders.
 */
const COL_HEADERS: string[] = [
  "",
  "No",
  "Бренд",
  "Артикул",
  "Наименование",
  "Кол-во",
  "Страна",
  "Код ТН ВЭД",
  headerWithTooltip(
    "Страна происх.",
    "ОКСМ страны происхождения. Редактирование — через карточку позиции."
  ),
  headerWithTooltip("Пошлина", "Процент / ₽ за кг (₽ за шт требует миграции)"),
  headerWithTooltip("Утильсбор", numericTooltip),
  headerWithTooltip("Акциз", numericTooltip),
  headerWithTooltip(
    "Антидемпинг",
    "Антидемпинговая / компенсационная / спец / сезонная пошлина (read-only — редактирование в карточке позиции)."
  ),
  "ПСМ/ПТС",
  "Нотификация",
  "Лицензии",
  headerWithTooltip("Экосбор", numericTooltip),
  "Честный знак",
  "Запрет ввоза",
  "Причина запрета",
  "ДС",
  "СС",
  "СГР",
];


/**
 * Composite "Пошлина" cell renderer.
 *
 * Two branches:
 *   1. Auto / legacy: draws the value + an inline chip selector
 *      (%, ₽/кг). The chip toggles mode — writing to customs_duty (%)
 *      or customs_duty_per_kg (₽/кг) — via a synthetic CustomEvent.
 *      ₽/шт variant is shown disabled with a tooltip since the
 *      customs_duty_per_pc column does not yet exist in the DB.
 *
 *   2. Manual override (Row 9 fix, Testing 2): when the per-item
 *      dialog flipped the row into Manual mode (combined/specific or
 *      simple with custom units), we render a compact formula chip
 *      (`10% > 0.5 EUR/kg`) sourced from `customs_manual_rate_payload`.
 *      Without this branch the cell would show only the slot-1 value
 *      (e.g. `10`) and the tester would read it as "не сохранилось".
 *      See SB-E row 9 in docs/plans/2026-05-13-customs-batch-plan.md.
 */
function dutyCompositeRenderer(
  instance: Handsontable,
  td: HTMLTableCellElement,
  row: number,
  col: number,
  prop: string | number,
  value: unknown,
  cellProperties: Handsontable.CellProperties,
) {
  const manualOverride = Boolean(
    instance.getDataAtRowProp(row, "customs_manual_override"),
  );
  const manualPayload = instance.getDataAtRowProp(
    row,
    "customs_manual_rate_payload",
  ) as ManualRatePayload | null | undefined;

  // Manual branch — read-only formula chip. The user edits via the
  // dialog (combined-rate inputs); the table just confirms the saved
  // state so they don't perceive «не сохранилось».
  if (manualOverride && manualPayload) {
    td.innerHTML = "";
    td.classList.add("customs-duty-cell", "customs-duty-cell--manual");

    const chipText = formatDutyChip({
      rate_type: (manualPayload.duty_rate_type ?? "simple") as DutyRateType,
      value_1: manualPayload.value_1_number ?? null,
      unit_1: (manualPayload.value_1_unit ?? "percent") as DutyUnit,
      value_2: manualPayload.value_2_number ?? null,
      unit_2: (manualPayload.value_2_unit ?? null) as DutyUnit | null,
      sign: manualPayload.sign_1 ?? null,
    });

    const formula = document.createElement("span");
    formula.className = "customs-duty-formula";
    formula.title =
      "Manual-режим: ставка задаётся в карточке позиции. Тип: " +
      (manualPayload.duty_rate_type ?? "simple");
    formula.textContent = chipText;
    td.appendChild(formula);

    const badge = document.createElement("span");
    badge.className = "customs-duty-mode-badge";
    badge.textContent = "M";
    badge.title =
      "Manual override — редактирование в карточке позиции";
    td.appendChild(badge);
    return;
  }

  // Auto branch — original chip selector + numeric value.
  Handsontable.renderers.NumericRenderer(
    instance,
    td,
    row,
    col,
    prop,
    value,
    cellProperties,
  );

  td.classList.add("customs-duty-cell");
  td.classList.remove("customs-duty-cell--manual");

  // Strip any previously appended UI to avoid duplicates on re-render.
  const existingChip = td.querySelector(".customs-duty-chip");
  if (existingChip) existingChip.remove();
  const existingFormula = td.querySelector(".customs-duty-formula");
  if (existingFormula) existingFormula.remove();
  const existingBadge = td.querySelector(".customs-duty-mode-badge");
  if (existingBadge) existingBadge.remove();

  const duty = instance.getDataAtRowProp(row, "customs_duty") as
    | number
    | null
    | undefined;
  const dutyPerKg = instance.getDataAtRowProp(row, "customs_duty_per_kg") as
    | number
    | null
    | undefined;
  const mode: DutyMode = resolveDutyMode(duty, dutyPerKg);

  const chip = document.createElement("span");
  chip.className = "customs-duty-chip";
  chip.setAttribute("role", "group");
  chip.setAttribute("aria-label", "Тип пошлины");

  function mkBtn(
    label: string,
    targetMode: DutyMode | "perPc",
    disabled = false,
  ): HTMLButtonElement {
    const b = document.createElement("button");
    b.type = "button";
    b.className =
      "customs-duty-chip__btn" +
      (targetMode === mode ? " customs-duty-chip__btn--active" : "");
    b.textContent = label;
    if (disabled) {
      b.disabled = true;
      b.title = "Требуется миграция: колонка customs_duty_per_pc";
      b.classList.add("customs-duty-chip__btn--disabled");
    } else if (targetMode !== mode) {
      b.onclick = (e) => {
        e.stopPropagation();
        // Stash the current composite value under the new mode and clear the other.
        const rowId = instance.getDataAtRowProp(row, "id") as string;
        const event = new CustomEvent<
          { rowId: string; mode: "pct" | "perKg" }
        >("kvota:duty-mode-change", {
          bubbles: true,
          detail: {
            rowId,
            mode: targetMode === "perKg" ? "perKg" : "pct",
          },
        });
        td.dispatchEvent(event);
      };
    }
    return b;
  }

  chip.appendChild(mkBtn("%", "pct"));
  chip.appendChild(mkBtn("₽/кг", "perKg"));
  chip.appendChild(mkBtn("₽/шт", "perPc", /* disabled */ true));
  td.appendChild(chip);
}

/**
 * Row 10 — OKSM country renderer factory. Maps the read-only numeric
 * column `country_of_origin_oksm` to its Russian name (e.g. `156` →
 * «Китай»). Falls back to the raw digit when the lookup misses or the
 * map isn't loaded yet.
 *
 * Returns a renderer function bound to the supplied map; the outer
 * factory pattern matches `makePositionRenderer` below.
 */
function makeCountryOksmRenderer(
  oksmNameMap: Map<number, string>,
) {
  return function countryOksmRenderer(
    instance: Handsontable,
    td: HTMLTableCellElement,
    row: number,
  ): HTMLTableCellElement {
    td.innerHTML = "";
    td.classList.add("customs-country-cell");
    const value = instance.getDataAtRowProp(
      row,
      "country_of_origin_oksm",
    ) as number | null | undefined;
    if (value == null) {
      td.textContent = "—";
      td.classList.add("customs-country-cell--empty");
      return td;
    }
    const name = oksmNameMap.get(value);
    td.textContent = name ?? String(value);
    if (name) {
      td.title = `ОКСМ ${value}`;
    }
    return td;
  };
}

/**
 * REQ-6: «Антидемпинг» column renderer — read-only badge showing the
 * applicable special-duty variant (IMPDEMP priority, then IMPCOMP/IMPDOP/
 * IMPTMP). Em-dash «—» when no special-duty applies. Tooltip on hover
 * shows full <Order> text and legal_link via native `title` attribute
 * (matches Phase 1 country-of-origin pattern).
 */
function antidumpingRenderer(
  instance: Handsontable,
  td: HTMLTableCellElement,
  row: number,
): HTMLTableCellElement {
  td.innerHTML = "";
  td.classList.add("customs-antidumping-cell");

  const variant = instance.getDataAtRowProp(
    row,
    "customs_antidumping",
  ) as SpecialDutyVariant | null | undefined;

  if (!variant) {
    td.textContent = "—";
    td.classList.add("customs-antidumping-cell--empty");
    return td;
  }

  const span = document.createElement("span");
  span.className =
    "customs-antidumping-badge " +
    SPECIAL_DUTY_BADGE_CLASS[variant.payment_type];
  span.title = buildSpecialDutyTooltip(variant);
  const shortRef = shortenDecisionRef(variant.order_ref);
  span.textContent = shortRef
    ? `${variant.value_1_number}% ${shortRef}`
    : `${variant.value_1_number}%`;
  td.appendChild(span);
  return td;
}

/**
 * Expand-action cell renderer — draws a small `↗` button that opens the
 * per-row customs dialog (Task 8). The click is handled via event delegation
 * on the scrolling wrapper to avoid re-binding listeners on each render.
 */
function expandRenderer(
  _instance: Handsontable,
  td: HTMLTableCellElement,
): HTMLTableCellElement {
  td.innerHTML = "";
  td.classList.add("customs-expand-cell");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "customs-expand-btn";
  btn.setAttribute("data-customs-expand", "1");
  btn.title = "Открыть карточку позиции";
  btn.setAttribute("aria-label", "Открыть карточку позиции");
  btn.textContent = "↗";
  td.appendChild(btn);
  return td;
}

/**
 * Number renderer that adds a sparkle icon into the cell for autofilled rows.
 * Used on the `position` (№) column; the icon tooltip cites the source Q-number.
 */
function makePositionRenderer(
  autofillByRowId: Map<string, CustomsAutofillSuggestion>,
) {
  return function positionRenderer(
    instance: Handsontable,
    td: HTMLTableCellElement,
    row: number,
    col: number,
    prop: string | number,
    value: unknown,
    cellProperties: Handsontable.CellProperties,
  ) {
    Handsontable.renderers.NumericRenderer(
      instance,
      td,
      row,
      col,
      prop,
      value,
      cellProperties,
    );

    const existing = td.querySelector(".customs-sparkle");
    if (existing) existing.remove();

    const rowId = instance.getDataAtRowProp(row, "id") as string | null;
    if (!rowId) return;
    const suggestion = autofillByRowId.get(rowId);
    if (!suggestion) return;

    const sparkle = document.createElement("span");
    sparkle.className = "customs-sparkle";
    const idn = suggestion.source_quote_idn?.trim();
    sparkle.title = idn
      ? `Автозаполнено из КП ${idn}`
      : "Автозаполнено из истории";
    sparkle.innerHTML =
      // Small sparkle svg — matches lucide Sparkles at 12px.
      `<svg xmlns="http://www.w3.org/2000/svg" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/></svg>`;
    td.prepend(sparkle);
    td.classList.add("customs-autofill-row");
  };
}

/**
 * Static column definitions — defined at module level so Handsontable
 * always receives the same column count regardless of React re-render timing.
 * The `readOnly` for import_banned is handled dynamically in the cells callback.
 *
 * Column at index 7 ("Пошлина") is a composite backed by a virtual
 * `customs_duty_composite` key — writes are intercepted in handleAfterChange
 * and mirrored onto either customs_duty or customs_duty_per_kg depending on
 * the active mode.
 */
const COLUMNS: Handsontable.ColumnSettings[] = [
  { data: "expand", type: "text", width: 36, readOnly: true },
  { data: "position", type: "numeric", width: 42, readOnly: true },
  { data: "brand", type: "text", width: 70, readOnly: true, wordWrap: false },
  { data: "product_code", type: "text", width: 100, readOnly: true, wordWrap: false },
  { data: "product_name", type: "text", width: 200, readOnly: true, wordWrap: false },
  { data: "quantity", type: "numeric", width: 55, readOnly: true },
  { data: "supplier_country", type: "text", width: 70, readOnly: true },
  { data: "hs_code", type: "text", width: 90 },
  {
    data: "country_of_origin_oksm",
    type: "numeric",
    width: 75,
    readOnly: true,
    allowEmpty: true,
  },
  {
    data: "customs_duty_composite",
    type: "numeric",
    width: 130,
    allowEmpty: true,
  },
  { data: "customs_util_fee", type: "numeric", width: 70, allowEmpty: true },
  { data: "customs_excise", type: "numeric", width: 65, allowEmpty: true },
  {
    data: "customs_antidumping",
    type: "text",
    width: 110,
    readOnly: true,
    allowEmpty: true,
  },
  { data: "customs_psm_pts", type: "text", width: 75 },
  { data: "customs_notification", type: "text", width: 90 },
  { data: "customs_licenses", type: "text", width: 80 },
  { data: "customs_eco_fee", type: "numeric", width: 65, allowEmpty: true },
  { data: "customs_honest_mark", type: "text", width: 85 },
  { data: "import_banned", type: "checkbox", width: 50 },
  { data: "import_ban_reason", type: "text", width: 120 },
  { data: "license_ds_required", type: "checkbox", width: 30 },
  { data: "license_ss_required", type: "checkbox", width: 30 },
  { data: "license_sgr_required", type: "checkbox", width: 30 },
];

interface CustomsHandsontableProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
  supplierByQuoteItemId: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >;
  userRoles: string[];
  /** Per-row autofill suggestions (keyed by quote_item_id). Optional. */
  autofillSuggestions?: CustomsAutofillSuggestion[];
  /** Called when user selects a row (for the item-level expenses card). */
  onSelectRow?: (rowId: string | null) => void;
  /** Called when the per-row `↗` expand button is clicked (opens the dialog). */
  onExpandRow?: (rowId: string) => void;
  /**
   * Optional ordered list of logical column keys to show.
   *
   * - When undefined or empty, all columns are rendered (current behavior).
   * - When provided, only listed keys are rendered, in the given order.
   * - The `expand` (`↗`) column is always rendered first regardless of this
   *   filter, because the row-expand affordance is essential UX.
   */
  visibleColumns?: readonly string[];
  /**
   * Row 10 — OKSM digital code → Russian name lookup. Read-only column
   * `country_of_origin_oksm` renders the name (Китай) instead of the
   * raw digit (156). Empty map = fall back to digit.
   */
  oksmNameMap?: Map<number, string>;
  /**
   * Row 8 — synchronous optimistic patch callback. Invoked by HoT
   * inline edits (e.g. duty-mode chip) before the async server save
   * completes, so the dialog reseed sees the fresh value when the user
   * opens the row card right after the chip click.
   */
  onItemPatched?: (rowId: string, patch: Partial<QuoteItemRow>) => void;
}

/**
 * Apply a visible-column filter to a headers/columns pair. Keys not found
 * in {@link COLUMN_KEYS} are silently dropped. `expand` is always prepended.
 */
function filterColumns(
  visibleColumns: readonly string[]
): { headers: string[]; columns: Handsontable.ColumnSettings[] } {
  const keyToIndex = new Map<string, number>();
  COLUMN_KEYS.forEach((k, i) => keyToIndex.set(k, i));

  const orderedKeys: string[] = ["expand"];
  for (const key of visibleColumns) {
    if (key === "expand") continue;
    if (keyToIndex.has(key)) orderedKeys.push(key);
  }

  const headers: string[] = [];
  const columns: Handsontable.ColumnSettings[] = [];
  for (const key of orderedKeys) {
    const idx = keyToIndex.get(key);
    if (idx === undefined) continue;
    headers.push(COL_HEADERS[idx]);
    columns.push(COLUMNS[idx]);
  }
  return { headers, columns };
}

export function CustomsHandsontable({
  items,
  invoiceCountryMap,
  supplierByQuoteItemId,
  userRoles,
  autofillSuggestions = [],
  onSelectRow,
  onExpandRow,
  visibleColumns,
  oksmNameMap,
  onItemPatched,
}: CustomsHandsontableProps) {
  // REQ-11 — read the `?customs_view=` URL param directly so the table
  // reacts to synthetic `system:*` IDs without depending on the parent
  // re-threading them through `visibleColumns`. UUID values fall back to
  // the existing prop-based path (see `effectiveVisibleColumns`).
  const searchParams = useSearchParams();
  const viewParam = searchParams?.get("customs_view") ?? null;
  const activeSystemView = useMemo(
    () => resolveActiveSystemView(viewParam),
    [viewParam],
  );
  const resolvedVisibleColumns = useMemo(
    () => effectiveVisibleColumns(activeSystemView, visibleColumns),
    [activeSystemView, visibleColumns],
  );

  // Resolve the column set: either filtered or the full default set.
  // Memoized against the serialized key list so we don't rebuild on every render.
  const visibleKey = resolvedVisibleColumns?.join("|") ?? "";
  const { colHeaders, colDefs, visibleKeys } = useMemo(() => {
    if (resolvedVisibleColumns && resolvedVisibleColumns.length > 0) {
      const { headers, columns } = filterColumns(resolvedVisibleColumns);
      const keys = columns.map((c) => String(c.data));
      return { colHeaders: headers, colDefs: columns, visibleKeys: keys };
    }
    return {
      colHeaders: COL_HEADERS,
      colDefs: COLUMNS,
      visibleKeys: [...COLUMN_KEYS] as string[],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleKey]);

  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);
  const pendingOps = useRef(new Set<string>());
  const rowIdsRef = useRef<string[]>(items.map((i) => i.id));

  const initialData = useMemo(
    () =>
      items.map((item) =>
        itemToRow(item, invoiceCountryMap, supplierByQuoteItemId),
      ),
    [items, invoiceCountryMap, supplierByQuoteItemId],
  );

  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const autofillByRowId = useMemo(() => {
    const m = new Map<string, CustomsAutofillSuggestion>();
    for (const s of autofillSuggestions) m.set(s.item_id, s);
    return m;
  }, [autofillSuggestions]);

  const positionRenderer = useMemo(
    () => makePositionRenderer(autofillByRowId),
    [autofillByRowId],
  );

  // Row 10 — bind the OKSM map into a renderer closure. Map identity drives
  // the memo so the renderer doesn't churn on unrelated re-renders.
  const countryOksmRenderer = useMemo(
    () => makeCountryOksmRenderer(oksmNameMap ?? new Map<number, string>()),
    [oksmNameMap],
  );

  const handleAfterChange = useCallback(
    (changes: Handsontable.CellChange[] | null, source: string) => {
      if (!changes || source === "loadData") return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      // Group per-row patches, translating customs_duty_composite into either
      // customs_duty or customs_duty_per_kg based on the row's current mode.
      const changedRows = new Map<number, Map<string, unknown>>();
      for (const [row, prop, , newVal] of changes) {
        const field =
          typeof prop === "number"
            ? visibleKeys[prop]
            : typeof prop === "string"
              ? prop
              : undefined;
        if (!field || field === "id" || field === "position") continue;

        if (!changedRows.has(row)) {
          changedRows.set(row, new Map());
        }
        changedRows.get(row)!.set(field, newVal);
      }

      for (const [rowIndex, fieldChanges] of changedRows) {
        const rowId = rowIdsRef.current[rowIndex];
        if (!rowId) continue;

        const updates: Record<string, unknown> = {};

        for (const [field, val] of fieldChanges) {
          if (field === "customs_duty_composite") {
            const compositeUpdates = buildDutyCompositeUpdates(val, {
              customs_duty_per_kg: hot.getDataAtRowProp(
                rowIndex,
                "customs_duty_per_kg",
              ) as number | null,
              customs_manual_override: Boolean(
                hot.getDataAtRowProp(rowIndex, "customs_manual_override"),
              ),
            });
            Object.assign(updates, compositeUpdates);
            // Sync the mirror fields into HoT state so the renderer
            // sees the latest value immediately. When the row was in
            // Manual override, also clear the manual mirror columns —
            // otherwise the formula chip keeps painting the stale rate
            // (Testing 2 row 26).
            hot.setDataAtRowProp(
              rowIndex,
              "customs_duty",
              compositeUpdates.customs_duty,
              "internal-mirror",
            );
            hot.setDataAtRowProp(
              rowIndex,
              "customs_duty_per_kg",
              compositeUpdates.customs_duty_per_kg,
              "internal-mirror",
            );
            if (compositeUpdates.customs_manual_override === false) {
              hot.setDataAtRowProp(
                rowIndex,
                "customs_manual_override",
                false,
                "internal-mirror",
              );
              hot.setDataAtRowProp(
                rowIndex,
                "customs_manual_rate_payload",
                null,
                "internal-mirror",
              );
            }
            continue;
          }
          if (NUMERIC_FIELDS.has(field)) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (BOOLEAN_FIELDS.has(field)) {
            updates[field] = Boolean(val);
          } else if (field === "hs_code") {
            // ТН ВЭД is semantically 10 digits — strip pasted separators
            // so search / rate auto-resolve / comparison stay consistent.
            updates[field] = normalizeHsCode(val as string) || null;
          } else if (TEXT_FIELDS.has(field)) {
            updates[field] = val || null;
          }
        }

        if (Object.keys(updates).length === 0) continue;

        // Row 8 fix — push the patch into the parent's override map
        // synchronously so a dialog opened right after an inline edit
        // reseeds from the fresh value, not the stale items prop.
        onItemPatched?.(rowId, updates as Partial<QuoteItemRow>);

        const lockKey = `update-${rowId}`;
        if (pendingOps.current.has(lockKey)) continue;
        pendingOps.current.add(lockKey);

        updateQuoteItem(rowId, updates)
          .then(() => router.refresh())
          .catch((err) => {
            console.error("customs handsontable row save failed", {
              rowId,
              updates,
              err,
            });
            toast.error(
              err instanceof Error
                ? err.message
                : "Не удалось сохранить позицию таможни",
            );
          })
          .finally(() => pendingOps.current.delete(lockKey));
      }
    },
    [router, visibleKeys, onItemPatched],
  );

  /**
   * Handle mode chip clicks via a synthetic CustomEvent dispatched by the
   * composite renderer. Flips the row's duty storage column.
   */
  const handleDutyModeChange = useCallback(
    (e: Event) => {
      const custom = e as CustomEvent<{ rowId: string; mode: DutyMode }>;
      const { rowId, mode } = custom.detail;
      const hot = hotRef.current?.hotInstance;
      if (!hot) return;
      const rowIndex = rowIdsRef.current.indexOf(rowId);
      if (rowIndex < 0) return;

      const currentComposite = hot.getDataAtRowProp(
        rowIndex,
        "customs_duty_composite",
      ) as number | null | undefined;
      const val = currentComposite ?? 0;

      const updates: Record<string, unknown> =
        mode === "perKg"
          ? { customs_duty_per_kg: val, customs_duty: null }
          : { customs_duty: val, customs_duty_per_kg: null };

      // Mirror into HoT state so the renderer picks up the mode switch.
      hot.setDataAtRowProp(
        rowIndex,
        "customs_duty",
        updates.customs_duty,
        "internal-mirror",
      );
      hot.setDataAtRowProp(
        rowIndex,
        "customs_duty_per_kg",
        updates.customs_duty_per_kg,
        "internal-mirror",
      );

      // Row 8 fix — push the same patch into the parent's optimistic-
      // override map so the dialog reseed sees the fresh value if the
      // user opens the row card before the async save completes.
      onItemPatched?.(rowId, updates as Partial<QuoteItemRow>);

      const lockKey = `update-${rowId}`;
      if (pendingOps.current.has(lockKey)) return;
      pendingOps.current.add(lockKey);
      updateQuoteItem(rowId, updates)
        .then(() => router.refresh())
        .catch((err) => {
          console.error("customs handsontable duty-mode save failed", {
            rowId,
            updates,
            err,
          });
          toast.error(
            err instanceof Error
              ? err.message
              : "Не удалось сохранить тип пошлины",
          );
        })
        .finally(() => pendingOps.current.delete(lockKey));
    },
    [router, onItemPatched],
  );

  const canToggleBan = useMemo(
    () =>
      userRoles.some((r) =>
        ["customs", "head_of_customs", "head_of_logistics", "admin"].includes(r),
      ),
    [userRoles],
  );

  /** Per-cell config: banned row, composite renderer, autofill sparkle. */
  const cellsCallback = useCallback(
    function (
      this: Handsontable.CellProperties,
      row: number,
      col: number,
    ): Handsontable.CellMeta {
      const meta: Handsontable.CellMeta = {};
      const data = initialData[row];
      if (!data) return meta;

      if (data.import_banned) {
        meta.className = (meta.className ?? "") + " row-import-banned";
      }

      const prop = visibleKeys[col];

      if (prop === "position") {
        meta.renderer = positionRenderer;
      } else if (prop === "customs_duty_composite") {
        meta.renderer = dutyCompositeRenderer;
      } else if (prop === "expand") {
        meta.renderer = expandRenderer;
      } else if (prop === "customs_antidumping") {
        meta.renderer = antidumpingRenderer;
      } else if (prop === "country_of_origin_oksm") {
        // Row 10 — render OKSM digit as Russian country name.
        meta.renderer = countryOksmRenderer;
      }

      if (prop === "import_banned" && !canToggleBan) {
        meta.readOnly = true;
      }
      if (prop === "import_ban_reason" && !data.import_banned) {
        meta.readOnly = true;
      }

      return meta;
    },
    [initialData, canToggleBan, positionRenderer, countryOksmRenderer, visibleKeys],
  );

  const handleAfterSelectionEnd = useCallback(
    (rowStart: number) => {
      const rowId = rowIdsRef.current[rowStart] ?? null;
      onSelectRow?.(rowId);
    },
    [onSelectRow],
  );

  /**
   * Delegated click handler for the per-row `↗` expand button. Uses
   * HoT's getCoords(td) to resolve the row index rather than relying on
   * walking DOM attributes, because Handsontable does not expose a stable
   * data-row attribute on all render paths.
   */
  const handleExpandClick = useCallback(
    (e: Event) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const btn = target.closest<HTMLElement>("[data-customs-expand]");
      if (!btn) return;
      e.stopPropagation();
      e.preventDefault();
      const td = btn.closest<HTMLTableCellElement>("td");
      const hot = hotRef.current?.hotInstance;
      if (!td || !hot) return;
      const coords = hot.getCoords(td);
      if (!coords || coords.row < 0) return;
      const rowId = rowIdsRef.current[coords.row];
      if (!rowId) return;
      onExpandRow?.(rowId);
    },
    [onExpandRow],
  );

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Нет позиций для таможенного оформления
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <Badge
          variant="secondary"
          className="bg-accent/10 text-accent border border-accent/20"
        >
          Все суммы в таблице — в рублях ₽
        </Badge>
        <span className="text-xs text-muted-foreground">
          Числовые столбцы — значение за единицу товара.
        </span>
      </div>

      {/* REQ-11 AC#9 — hint banner above the table when a non-default
          system view hides one or more columns. Self-collapses to null
          for `null` / `system:all` so unconditional mount is safe. */}
      <CustomsViewHintBanner
        currentView={activeSystemView}
        allColumns={CUSTOMS_AVAILABLE_COLUMNS}
      />

      <div className="ht-theme-main">
        <style>{`
          .row-import-banned td {
            background-color: color-mix(in oklch, var(--destructive) 8%, transparent) !important;
          }
          .customs-duty-cell {
            position: relative;
            padding-right: 70px !important;
          }
          .customs-duty-chip {
            position: absolute;
            right: 4px;
            top: 50%;
            transform: translateY(-50%);
            display: inline-flex;
            border-radius: var(--radius-sm);
            overflow: hidden;
            border: 1px solid var(--border);
            background: var(--card);
          }
          .customs-duty-chip__btn {
            padding: 2px 5px;
            font-size: 10px;
            line-height: 1;
            font-weight: 600;
            color: var(--muted-foreground);
            background: transparent;
            border: 0;
            cursor: pointer;
          }
          .customs-duty-chip__btn + .customs-duty-chip__btn {
            border-left: 1px solid var(--border);
          }
          .customs-duty-chip__btn--active {
            background: var(--accent);
            color: var(--accent-foreground);
          }
          .customs-duty-chip__btn--disabled {
            opacity: 0.45;
            cursor: not-allowed;
          }
          .customs-sparkle {
            display: inline-flex;
            vertical-align: middle;
            margin-right: 4px;
            color: var(--accent);
          }
          .customs-autofill-row {
            background-color: color-mix(in oklch, var(--accent) 5%, transparent);
          }
          .customs-expand-cell {
            padding: 0 !important;
            text-align: center;
          }
          .customs-expand-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            margin: 2px auto;
            padding: 0;
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            background: var(--card);
            color: var(--muted-foreground);
            font-size: 13px;
            line-height: 1;
            cursor: pointer;
          }
          .customs-expand-btn:hover {
            color: var(--foreground);
            border-color: var(--accent);
          }
          .customs-antidumping-cell {
            text-align: center;
          }
          .customs-antidumping-cell--empty {
            color: var(--muted-foreground);
          }
          .customs-antidumping-badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 6px;
            font-size: 11px;
            line-height: 1.1;
            font-weight: 600;
            border-radius: var(--radius-sm);
            white-space: nowrap;
          }
          .customs-antidumping-badge.bg-amber-700\\/30 {
            background-color: rgb(180 83 9 / 0.30);
            color: rgb(252 211 77);
          }
          .customs-antidumping-badge.bg-red-700\\/30 {
            background-color: rgb(185 28 28 / 0.30);
            color: rgb(252 165 165);
          }
          .customs-antidumping-badge.bg-blue-700\\/30 {
            background-color: rgb(29 78 216 / 0.30);
            color: rgb(147 197 253);
          }
          .customs-antidumping-badge.bg-slate-700\\/30 {
            background-color: rgb(51 65 85 / 0.30);
            color: rgb(203 213 225);
          }
          /* Row 9 (Testing 2) — Manual-mode chip in «Пошлина» column. */
          .customs-duty-cell--manual {
            padding-right: 32px !important;
          }
          .customs-duty-formula {
            display: inline-block;
            font-family: var(--font-mono, ui-monospace, monospace);
            font-size: 11px;
            line-height: 1.2;
            color: var(--foreground);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: calc(100% - 24px);
            vertical-align: middle;
          }
          .customs-duty-mode-badge {
            position: absolute;
            right: 4px;
            top: 50%;
            transform: translateY(-50%);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            border-radius: var(--radius-sm);
            background: color-mix(in oklch, var(--accent) 20%, transparent);
            color: var(--accent);
            font-size: 10px;
            font-weight: 700;
            border: 1px solid color-mix(in oklch, var(--accent) 30%, transparent);
          }
          /* Row 10 — OKSM country name cell. */
          .customs-country-cell {
            text-align: left;
          }
          .customs-country-cell--empty {
            color: var(--muted-foreground);
          }
        `}</style>
        <div
          style={{ overflowX: "auto" }}
          ref={(el) => {
            if (!el) return;
            // Attach a single delegated listener for the custom duty-mode event.
            el.removeEventListener(
              "kvota:duty-mode-change",
              handleDutyModeChange as EventListener,
            );
            el.addEventListener(
              "kvota:duty-mode-change",
              handleDutyModeChange as EventListener,
            );
            el.removeEventListener(
              "click",
              handleExpandClick as EventListener,
            );
            el.addEventListener(
              "click",
              handleExpandClick as EventListener,
            );
          }}
        >
          <HotTable
            ref={hotRef}
            data={initialData}
            licenseKey="non-commercial-and-evaluation"
            colHeaders={colHeaders}
            columns={colDefs}
            cells={cellsCallback}
            rowHeaders={false}
            stretchH="none"
            autoWrapRow={true}
            autoWrapCol={true}
            manualColumnResize={true}
            contextMenu={false}
            minSpareRows={0}
            height="auto"
            afterChange={handleAfterChange}
            afterSelectionEnd={handleAfterSelectionEnd}
            className="htLeft"
          />
        </div>
      </div>
    </div>
  );
}
