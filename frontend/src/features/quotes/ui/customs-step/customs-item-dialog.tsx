"use client";

/**
 * CustomsItemDialog — Task 8 of logistics-customs-redesign.
 *
 * Full-form editor for a single quote_item's customs fields, opened from
 * the `↗` action button on each row of the customs handsontable.
 *
 * Mirrors the columns exposed in customs-handsontable.tsx (see COLUMN_KEYS
 * there) plus reuses the existing ItemCustomsExpenses component so testing/
 * translation/sticker costs can be managed without closing the dialog.
 *
 * Writes flow:
 *   - Top-level customs fields → updateQuoteItem (kvota.quote_items)
 *   - Per-item expenses → ItemCustomsExpenses (kvota.customs_item_expenses)
 *
 * Duty has three expression modes (%, ₽/кг, ₽/шт); ₽/шт requires a column
 * that does not yet exist in the DB and is disabled, matching the inline
 * chip UI in the handsontable.
 */

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { updateQuoteItem } from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

import { ClassifyButton } from "@/features/customs-classify";
import { CustomsCountryDropdown } from "@/features/customs-country-dropdown";
import { ALTA_FEATURES_ENABLED } from "@/shared/lib/feature-flags";
import {
  AutoResolveButton,
  RateBreakdown,
  SourceTimestamp,
  SpecialDutyBlock,
  formatDutyFormula,
  type ApiError,
  type DutyRateType,
  type DutySign,
  type DutyUnit,
  type ResolveRatesData,
  type SpecialDutyType,
} from "@/features/customs-rate-resolve";
import { MeasuresList } from "@/features/customs-non-tariff-measures";

import { ItemCustomsExpenses } from "./item-customs-expenses";

function ext<T>(row: unknown): T {
  return row as T;
}

type DutyMode = "pct" | "perKg";

interface CustomsExtras {
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
  license_ds_cost?: number | null;
  license_ss_required?: boolean | null;
  license_ss_cost?: number | null;
  license_sgr_required?: boolean | null;
  license_sgr_cost?: number | null;
  // REQ-7 customs-phase-1 — country of origin + certificates
  country_of_origin_oksm?: number | null;
  has_origin_certificate?: boolean | null;
  has_fta_certificate?: boolean | null;
  // REQ-4 customs-phase-A — manual combined-rate snapshot.
  // JSONB compatible with Alta `Rate` dataclass (3-slot model). Saved into
  // `quote_versions.input_variables.customs_rates[item_id].manual_rate` by
  // the calc-engine adapter; UI mirrors the structure here for round-trip.
  customs_manual_override?: boolean | null;
  customs_manual_rate_payload?: ManualRatePayload | null;
}

/**
 * Snapshot shape persisted when Manual mode is active.
 *
 * Mirrors `services.alta_client.Rate` field-for-field so the
 * calc-engine adapter can deserialize without a translation layer.
 * Currency may be null for percent / RUB-denominated rates.
 */
export interface ManualRatePayload {
  duty_rate_type: DutyRateType;
  value_1_number: number | null;
  value_1_unit: string | null;
  value_1_currency: string | null;
  value_2_number: number | null;
  value_2_unit: string | null;
  value_2_currency: string | null;
  sign_1: DutySign;
}

export interface FormState {
  hs_code: string;
  duty_mode: DutyMode;
  duty_value: string;
  customs_util_fee: string;
  customs_excise: string;
  customs_psm_pts: string;
  customs_notification: string;
  customs_licenses: string;
  customs_eco_fee: string;
  customs_honest_mark: string;
  import_banned: boolean;
  import_ban_reason: string;
  license_ds_required: boolean;
  license_ds_cost: string;
  license_ss_required: boolean;
  license_ss_cost: string;
  license_sgr_required: boolean;
  license_sgr_cost: string;
  // REQ-7 customs-phase-1 — country of origin + certificates
  country_of_origin_oksm: number | null;
  has_origin_certificate: boolean;
  has_fta_certificate: boolean;
  // REQ-4 customs-phase-A — manual combined-rate input
  duty_manual_mode: boolean;
  duty_rate_type: DutyRateType;
  duty_value_1: string;
  duty_unit_1: DutyUnit;
  duty_value_2: string;
  duty_unit_2: DutyUnit;
  duty_sign: DutySign;
}

function stateFromItem(item: QuoteItemRow): FormState {
  const extras = ext<CustomsExtras>(item);
  const dutyPerKg = extras.customs_duty_per_kg ?? null;
  const duty = extras.customs_duty ?? null;
  const mode: DutyMode = dutyPerKg != null ? "perKg" : "pct";
  const compositeValue = mode === "perKg" ? dutyPerKg : duty;

  const numToStr = (n: number | null | undefined): string =>
    n == null ? "" : String(n);

  // REQ-4: re-hydrate Manual mode from snapshot when present so the user
  // sees what they entered last time. Falls back to Auto / simple defaults.
  const manualPayload = extras.customs_manual_rate_payload ?? null;
  const manualOverride = Boolean(extras.customs_manual_override);
  const initialUnit1: DutyUnit =
    (manualPayload?.value_1_unit as DutyUnit | undefined) ??
    (mode === "perKg" ? "EUR/kg" : "percent");
  const initialUnit2: DutyUnit =
    (manualPayload?.value_2_unit as DutyUnit | undefined) ?? "EUR/kg";

  return {
    hs_code: extras.hs_code ?? "",
    duty_mode: mode,
    duty_value: numToStr(compositeValue),
    customs_util_fee: numToStr(extras.customs_util_fee),
    customs_excise: numToStr(extras.customs_excise),
    customs_psm_pts: extras.customs_psm_pts ?? "",
    customs_notification: extras.customs_notification ?? "",
    customs_licenses: extras.customs_licenses ?? "",
    customs_eco_fee: numToStr(extras.customs_eco_fee),
    customs_honest_mark: extras.customs_honest_mark ?? "",
    import_banned: Boolean(extras.import_banned),
    import_ban_reason: extras.import_ban_reason ?? "",
    license_ds_required: Boolean(extras.license_ds_required),
    license_ds_cost: numToStr(extras.license_ds_cost),
    license_ss_required: Boolean(extras.license_ss_required),
    license_ss_cost: numToStr(extras.license_ss_cost),
    license_sgr_required: Boolean(extras.license_sgr_required),
    license_sgr_cost: numToStr(extras.license_sgr_cost),
    country_of_origin_oksm: extras.country_of_origin_oksm ?? null,
    has_origin_certificate: Boolean(extras.has_origin_certificate),
    has_fta_certificate: Boolean(extras.has_fta_certificate),
    duty_manual_mode: manualOverride,
    duty_rate_type: manualPayload?.duty_rate_type ?? "simple",
    duty_value_1: numToStr(manualPayload?.value_1_number ?? compositeValue),
    duty_unit_1: initialUnit1,
    duty_value_2: numToStr(manualPayload?.value_2_number),
    duty_unit_2: initialUnit2,
    duty_sign: manualPayload?.sign_1 ?? null,
  };
}

function parseNumOrNull(s: string): number | null {
  const trimmed = s.trim();
  if (trimmed === "") return null;
  const n = Number.parseFloat(trimmed);
  return Number.isFinite(n) ? n : null;
}

/**
 * Extract currency code (EUR / USD / RUB) from a unit token like "EUR/kg",
 * "USD/pc", "RUB/l". Returns null for the bare "percent" unit.
 */
function unitCurrency(unit: DutyUnit | string): string | null {
  if (unit === "percent") return null;
  const sep = unit.indexOf("/");
  if (sep <= 0) return null;
  return unit.slice(0, sep);
}

/**
 * Build the JSONB payload stored when Manual mode is active.
 *
 * Shape mirrors `services.alta_client.Rate` so the calc-engine adapter
 * can deserialize without translation. For "simple" / "specific" only
 * slot 1 is filled; for "combined" both slots plus `sign_1` are present.
 */
export function buildManualRatePayload(
  form: Pick<
    FormState,
    | "duty_rate_type"
    | "duty_value_1"
    | "duty_unit_1"
    | "duty_value_2"
    | "duty_unit_2"
    | "duty_sign"
  >,
): ManualRatePayload {
  const value1 = parseNumOrNull(form.duty_value_1);
  const value2 =
    form.duty_rate_type === "combined"
      ? parseNumOrNull(form.duty_value_2)
      : null;
  return {
    duty_rate_type: form.duty_rate_type,
    value_1_number: value1,
    value_1_unit: form.duty_unit_1,
    value_1_currency: unitCurrency(form.duty_unit_1),
    value_2_number: value2,
    value_2_unit: form.duty_rate_type === "combined" ? form.duty_unit_2 : null,
    value_2_currency:
      form.duty_rate_type === "combined"
        ? unitCurrency(form.duty_unit_2)
        : null,
    sign_1: form.duty_rate_type === "combined" ? form.duty_sign : null,
  };
}

export function buildUpdates(form: FormState): Record<string, unknown> {
  // Auto mode (or legacy rows) — keep the existing two-column duty
  // representation untouched; customs_manual_* stay null.
  if (!form.duty_manual_mode) {
    const dutyValue = parseNumOrNull(form.duty_value);
    const dutyColumns =
      form.duty_mode === "perKg"
        ? { customs_duty: null, customs_duty_per_kg: dutyValue }
        : { customs_duty: dutyValue, customs_duty_per_kg: null };

    return {
      hs_code: form.hs_code.trim() || null,
      ...dutyColumns,
      customs_util_fee: parseNumOrNull(form.customs_util_fee),
      customs_excise: parseNumOrNull(form.customs_excise),
      customs_psm_pts: form.customs_psm_pts.trim() || null,
      customs_notification: form.customs_notification.trim() || null,
      customs_licenses: form.customs_licenses.trim() || null,
      customs_eco_fee: parseNumOrNull(form.customs_eco_fee),
      customs_honest_mark: form.customs_honest_mark.trim() || null,
      import_banned: form.import_banned,
      import_ban_reason: form.import_banned
        ? form.import_ban_reason.trim() || null
        : null,
      license_ds_required: form.license_ds_required,
      license_ds_cost: form.license_ds_required
        ? parseNumOrNull(form.license_ds_cost)
        : null,
      license_ss_required: form.license_ss_required,
      license_ss_cost: form.license_ss_required
        ? parseNumOrNull(form.license_ss_cost)
        : null,
      license_sgr_required: form.license_sgr_required,
      license_sgr_cost: form.license_sgr_required
        ? parseNumOrNull(form.license_sgr_cost)
        : null,
      country_of_origin_oksm: form.country_of_origin_oksm,
      has_origin_certificate: form.has_origin_certificate,
      has_fta_certificate: form.has_fta_certificate,
      customs_manual_override: false,
      customs_manual_rate_payload: null,
    };
  }

  // Manual mode — derive the legacy customs_duty / customs_duty_per_kg
  // pair from slot 1 so the calc-engine continues to compute, and stash
  // the full 3-slot payload in customs_manual_rate_payload for round-trip.
  const payload = buildManualRatePayload(form);
  const value1 = payload.value_1_number;
  const dutyColumns =
    form.duty_unit_1 === "percent"
      ? { customs_duty: value1, customs_duty_per_kg: null }
      : { customs_duty: null, customs_duty_per_kg: value1 };

  return {
    hs_code: form.hs_code.trim() || null,
    ...dutyColumns,
    customs_util_fee: parseNumOrNull(form.customs_util_fee),
    customs_excise: parseNumOrNull(form.customs_excise),
    customs_psm_pts: form.customs_psm_pts.trim() || null,
    customs_notification: form.customs_notification.trim() || null,
    customs_licenses: form.customs_licenses.trim() || null,
    customs_eco_fee: parseNumOrNull(form.customs_eco_fee),
    customs_honest_mark: form.customs_honest_mark.trim() || null,
    import_banned: form.import_banned,
    import_ban_reason: form.import_banned
      ? form.import_ban_reason.trim() || null
      : null,
    license_ds_required: form.license_ds_required,
    license_ds_cost: form.license_ds_required
      ? parseNumOrNull(form.license_ds_cost)
      : null,
    license_ss_required: form.license_ss_required,
    license_ss_cost: form.license_ss_required
      ? parseNumOrNull(form.license_ss_cost)
      : null,
    license_sgr_required: form.license_sgr_required,
    license_sgr_cost: form.license_sgr_required
      ? parseNumOrNull(form.license_sgr_cost)
      : null,
    country_of_origin_oksm: form.country_of_origin_oksm,
    has_origin_certificate: form.has_origin_certificate,
    has_fta_certificate: form.has_fta_certificate,
    customs_manual_override: true,
    customs_manual_rate_payload: payload,
  };
}

interface CustomsItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  quoteId: string;
  item: QuoteItemRow | null;
  userRoles: string[];
  /** Called after a successful save so parents can refresh the handsontable. */
  onSaved?: () => void;
}

const CAN_WRITE_ROLES = new Set(["customs", "head_of_customs", "admin"]);

export function CustomsItemDialog({
  open,
  onOpenChange,
  quoteId,
  item,
  userRoles,
  onSaved,
}: CustomsItemDialogProps) {
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [resolveResult, setResolveResult] = useState<ResolveRatesData | null>(
    null
  );
  const [refreshing, setRefreshing] = useState(false);
  // Selected variant per special-duty type — keyed by category_code from the
  // resolver. Wired into the SpecialDutyBlock radio UI; persistence into
  // tnved_user_choices is Task 10's responsibility.
  const [specialDutySelections, setSpecialDutySelections] = useState<
    Partial<Record<SpecialDutyType, string>>
  >({});
  const canWrite = userRoles.some((r) => CAN_WRITE_ROLES.has(r));

  // Re-seed the form whenever a different row is opened. Avoids stale state
  // when the dialog is reused across rows.
  useEffect(() => {
    if (open && item) {
      setForm(stateFromItem(item));
      setResolveResult(null);
      setSpecialDutySelections({});
    }
  }, [open, item]);

  if (!item || !form) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl" />
      </Dialog>
    );
  }

  const itemLabel = [item.brand, item.product_code]
    .filter(Boolean)
    .join(" · ") || item.product_name || "";

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave() {
    if (!form || !item) return;
    setSaving(true);
    try {
      await updateQuoteItem(item.id, buildUpdates(form));
      toast.success("Данные по позиции сохранены");
      onSaved?.();
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось сохранить");
    } finally {
      setSaving(false);
    }
  }

  function handleResolved(data: ResolveRatesData) {
    setResolveResult(data);
    setRefreshing(false);
    // Q4 freeze warnings UI (forward-compat with Task 8): non-blocking toast
    // for Tier 2 cache-stale warnings. Currently never populated by Phase 1
    // resolve-rates, but the wiring is in place for the freeze endpoint.
    if (data.warnings && data.warnings.length > 0) {
      for (const w of data.warnings) {
        toast.warning(w);
      }
    }
    toast.success("Ставки обновлены");
  }

  function handleResolveError(error: ApiError) {
    setRefreshing(false);
    if (error.code === "ALTA_UNAVAILABLE") {
      toast.error(
        error.message ||
          "Alta API недоступен, попробуйте позже",
        {
          action: {
            label: "Повторить",
            onClick: () => {
              // Re-trigger the same resolve via a synthetic refresh.
              setResolveResult(null);
            },
          },
        }
      );
    } else if (error.code === "FREEZE_ABORTED") {
      // Q4 Tier 3 — Task 8 will surface this code; rendered as a blocking
      // modal-style toast in the meantime.
      toast.error(
        error.message ||
          "Не удалось зафиксировать ставки. Если проблема повторяется — обратитесь к администратору."
      );
    } else if (
      error.code === "INVALID_TNVED_CODE" ||
      error.code === "INVALID_OKSM" ||
      error.code === "BAD_REQUEST"
    ) {
      toast.error(error.message || "Проверьте введённые данные");
    } else {
      toast.error(error.message || "Не удалось получить ставки");
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next && saving) return;
    onOpenChange(next);
  }

  const readOnly = !canWrite;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Таможня: {itemLabel || "позиция"}</DialogTitle>
          <DialogDescription>
            {item.product_name || "Полный набор таможенных полей по позиции"}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-6">
          {/* Core customs classification */}
          <section className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Код ТН ВЭД">
              <div className="flex gap-2">
                <Input
                  value={form.hs_code}
                  onChange={(e) => update("hs_code", e.target.value)}
                  disabled={readOnly || saving}
                  placeholder="0000000000"
                  className="flex-1"
                />
                {ALTA_FEATURES_ENABLED && (
                  <ClassifyButton
                    quoteItemId={item.id}
                    initialName={item.product_name ?? ""}
                    initialBrand={item.brand ?? undefined}
                    onSelected={(code) => update("hs_code", code)}
                    disabled={readOnly || saving}
                  />
                )}
              </div>
            </Field>

            <Field label="Пошлина" className="sm:col-span-2">
              <DutyRateInput
                form={form}
                update={update}
                readOnly={readOnly}
                saving={saving}
                weightKg={
                  (item as { weight_kg?: number | null }).weight_kg ?? null
                }
                customsValue={extractCustomsValue(item)}
              />
            </Field>

            <Field label="Утильсбор, ₽">
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={form.customs_util_fee}
                onChange={(e) => update("customs_util_fee", e.target.value)}
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="Акциз, ₽">
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={form.customs_excise}
                onChange={(e) => update("customs_excise", e.target.value)}
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="Экосбор, ₽">
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                value={form.customs_eco_fee}
                onChange={(e) => update("customs_eco_fee", e.target.value)}
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="ПСМ/ПТС">
              <Input
                value={form.customs_psm_pts}
                onChange={(e) => update("customs_psm_pts", e.target.value)}
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="Нотификация">
              <Input
                value={form.customs_notification}
                onChange={(e) =>
                  update("customs_notification", e.target.value)
                }
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="Лицензии">
              <Input
                value={form.customs_licenses}
                onChange={(e) => update("customs_licenses", e.target.value)}
                disabled={readOnly || saving}
              />
            </Field>

            <Field label="Честный знак" className="sm:col-span-2">
              <Input
                value={form.customs_honest_mark}
                onChange={(e) =>
                  update("customs_honest_mark", e.target.value)
                }
                disabled={readOnly || saving}
              />
            </Field>
          </section>

          {/* REQ-7 customs-phase-1 — country of origin + cert flags + auto-resolve */}
          <section className="space-y-3 rounded-md border border-border bg-muted/20 p-3">
            <div className="text-sm font-medium text-foreground">
              {ALTA_FEATURES_ENABLED
                ? "Страна происхождения и автоподбор ставок"
                : "Страна происхождения"}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Страна происхождения">
                <CustomsCountryDropdown
                  value={form.country_of_origin_oksm}
                  onChange={(oksm) => update("country_of_origin_oksm", oksm)}
                  disabled={readOnly || saving}
                  ariaLabel="Страна происхождения"
                />
              </Field>

              <div className="flex flex-col gap-2 justify-end">
                <label className="flex items-center gap-2 cursor-pointer text-sm">
                  <Checkbox
                    checked={form.has_origin_certificate}
                    onCheckedChange={(checked) =>
                      update("has_origin_certificate", checked === true)
                    }
                    disabled={readOnly || saving}
                  />
                  <span className="text-foreground">
                    Сертификат происхождения
                  </span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-sm">
                  <Checkbox
                    checked={form.has_fta_certificate}
                    onCheckedChange={(checked) =>
                      update("has_fta_certificate", checked === true)
                    }
                    disabled={readOnly || saving}
                  />
                  <span className="text-foreground">Сертификат FTA</span>
                </label>
              </div>
            </div>

            {ALTA_FEATURES_ENABLED && (
              <div className="flex flex-wrap items-center gap-2">
                <AutoResolveButton
                  tnvedCode={form.hs_code}
                  countryOksm={form.country_of_origin_oksm}
                  hasOriginCertificate={form.has_origin_certificate}
                  hasFtaCertificate={form.has_fta_certificate}
                  quoteItemId={item.id}
                  onResolved={handleResolved}
                  onError={handleResolveError}
                  disabled={readOnly}
                />
                {resolveResult && (
                  <span className="text-xs text-muted-foreground">
                    Получено {resolveResult.rates.length} ставок
                  </span>
                )}
              </div>
            )}

            {ALTA_FEATURES_ENABLED && resolveResult && (
              <div className="flex flex-col gap-2">
                <RateBreakdown
                  rates={resolveResult.rates}
                  totalRub={resolveResult.total_rub}
                  source={resolveResult.source}
                />
                <SourceTimestamp
                  fetchedAt={resolveResult.fetched_at}
                  refreshing={refreshing}
                  onRefresh={() => {
                    // Force-live re-fetch — same handler, but with force_live.
                    // Simulated by re-mounting the AutoResolveButton via state
                    // is overkill — we manually re-call resolveRates here for
                    // a clean refresh affordance.
                    setRefreshing(true);
                    // Two-stage error handling (review fix L1):
                    //  1. Module-load failure (network drop, chunk hash miss
                    //     after a deploy) → "перезагрузите страницу"
                    //  2. resolveRates() rejection (network → caught by the
                    //     api layer and surfaced as res.error) → generic
                    //     "не удалось обновить ставки".
                    import("@/features/customs-rate-resolve")
                      .then(
                        ({ resolveRates }) =>
                          resolveRates({
                            tnved_code: form.hs_code.trim(),
                            country_oksm: form.country_of_origin_oksm!,
                            certificate: form.has_origin_certificate,
                            sp_certificate: form.has_fta_certificate,
                            has_fta_certificate: form.has_fta_certificate,
                            quote_item_id: item.id,
                            force_live: true,
                          })
                            .then((res) => {
                              if (res.success && res.data) {
                                handleResolved(res.data);
                              } else if (res.error) {
                                handleResolveError(res.error);
                              }
                            })
                            .catch(() => {
                              setRefreshing(false);
                              toast.error("Не удалось обновить ставки");
                            }),
                        () => {
                          // Dynamic import itself rejected — module-load error.
                          setRefreshing(false);
                          toast.error(
                            "Не удалось загрузить модуль обновления, попробуйте перезагрузить страницу",
                          );
                        },
                      );
                  }}
                />
              </div>
            )}

            {ALTA_FEATURES_ENABLED && resolveResult && (
              <div className="flex flex-col gap-2">
                {(["IMPDEMP", "IMPCOMP", "IMPDOP", "IMPTMP"] as const).map(
                  (pt) => {
                    const variants = resolveResult.rates.filter(
                      (r) => r.payment_type === pt,
                    );
                    if (variants.length === 0) return null;
                    return (
                      <SpecialDutyBlock
                        key={pt}
                        variants={variants}
                        paymentType={pt}
                        selectedCode={specialDutySelections[pt] ?? null}
                        onSelect={(code) =>
                          setSpecialDutySelections((prev) => ({
                            ...prev,
                            [pt]: code,
                          }))
                        }
                        tnvedCode={form.hs_code}
                      />
                    );
                  },
                )}
              </div>
            )}

            {ALTA_FEATURES_ENABLED && (
              <MeasuresList
                tnvedCode={form.hs_code}
                countryOksm={form.country_of_origin_oksm}
              />
            )}
          </section>

          {/* Import ban */}
          <section className="space-y-3">
            <label className="flex items-center gap-2 cursor-pointer">
              <Checkbox
                checked={form.import_banned}
                onCheckedChange={(checked) =>
                  update("import_banned", checked === true)
                }
                disabled={readOnly || saving}
              />
              <span className="text-sm font-medium text-foreground">
                Запрет ввоза
              </span>
            </label>
            {form.import_banned && (
              <Field label="Причина запрета">
                <Textarea
                  value={form.import_ban_reason}
                  onChange={(e) =>
                    update("import_ban_reason", e.target.value)
                  }
                  disabled={readOnly || saving}
                  rows={2}
                  placeholder="Опишите основание для запрета"
                />
              </Field>
            )}
          </section>

          {/* Licenses block */}
          <section className="space-y-3">
            <div className="text-sm font-medium text-foreground">
              Лицензии и разрешения
            </div>
            <LicenseRow
              label="Декларация соответствия (ДС)"
              required={form.license_ds_required}
              onRequiredChange={(v) => update("license_ds_required", v)}
              cost={form.license_ds_cost}
              onCostChange={(v) => update("license_ds_cost", v)}
              disabled={readOnly || saving}
            />
            <LicenseRow
              label="Сертификат соответствия (СС)"
              required={form.license_ss_required}
              onRequiredChange={(v) => update("license_ss_required", v)}
              cost={form.license_ss_cost}
              onCostChange={(v) => update("license_ss_cost", v)}
              disabled={readOnly || saving}
            />
            <LicenseRow
              label="Свидетельство гос. регистрации (СГР)"
              required={form.license_sgr_required}
              onRequiredChange={(v) => update("license_sgr_required", v)}
              cost={form.license_sgr_cost}
              onCostChange={(v) => update("license_sgr_cost", v)}
              disabled={readOnly || saving}
            />
          </section>

          {/* Per-item expenses — reuses the same component rendered on the
              customs step page. Loads/mutates on its own, independent of the
              form save button. */}
          <section>
            <ItemCustomsExpenses
              quoteId={quoteId}
              quoteItemId={item.id}
              itemLabel={itemLabel}
              userRoles={userRoles}
            />
          </section>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={saving}
          >
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={readOnly || saving}>
            {saving ? (
              <>
                <Loader2 size={14} className="animate-spin mr-1" />
                Сохранение…
              </>
            ) : (
              "Сохранить"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Field({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <label className={`flex flex-col gap-1 ${className ?? ""}`.trim()}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function ChipButton({
  active,
  disabled,
  onClick,
  title,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={[
        "px-2.5 text-xs font-semibold border-l border-border first:border-l-0",
        active
          ? "bg-accent text-accent-foreground"
          : "bg-transparent text-muted-foreground hover:text-foreground",
        disabled ? "opacity-45 cursor-not-allowed" : "cursor-pointer",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

/**
 * REQ-4 Phase A — Manual duty-rate input + Auto/Manual toggle.
 *
 * - Auto branch reuses the existing two-button (% / ₽/кг) chip group, untouched
 *   so calc-engine reads `customs_duty` / `customs_duty_per_kg` as before.
 * - Manual branch renders a chip-toggle for rate type
 *   (Простая / Комбинированная / Специфическая) plus 1-2 input slots
 *   with unit selectors and a live formula preview below.
 *
 * When ALTA_FEATURES_ENABLED=false the Auto/Manual toggle is hidden and
 * Manual mode is forced — defensive flag-aware behavior per Req 4 AC #3.
 */
const DUTY_UNIT_OPTIONS: Array<{ value: DutyUnit; label: string }> = [
  { value: "percent", label: "%" },
  { value: "EUR/kg", label: "EUR/кг" },
  { value: "USD/kg", label: "USD/кг" },
  { value: "USD/pc", label: "USD/шт" },
  { value: "RUB/l", label: "₽/л" },
  { value: "EUR/l", label: "EUR/л" },
  { value: "USD/l", label: "USD/л" },
];

function DutyRateInput({
  form,
  update,
  readOnly,
  saving,
  weightKg,
  customsValue,
}: {
  form: FormState;
  update: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  readOnly: boolean;
  saving: boolean;
  weightKg: number | null;
  customsValue: number | null;
}) {
  // Defensive flag-off: when Alta features are disabled, only Manual mode
  // is available — the Auto resolver is unreachable so the toggle is hidden
  // and Manual mode is implicitly selected.
  const showAutoToggle = ALTA_FEATURES_ENABLED;
  const isManual = !showAutoToggle || form.duty_manual_mode;
  const value1 = parseNumOrNull(form.duty_value_1);
  const value2 = parseNumOrNull(form.duty_value_2);
  const previewText = formatDutyFormula({
    rate_type: form.duty_rate_type,
    value_1: value1,
    unit_1: form.duty_unit_1,
    value_2: value2,
    unit_2: form.duty_unit_2,
    sign: form.duty_sign,
    customs_value: customsValue,
    weight_kg: weightKg,
  });

  return (
    <div className="flex flex-col gap-2">
      {showAutoToggle && (
        <div
          role="group"
          aria-label="Режим ввода"
          className="inline-flex overflow-hidden rounded-md border border-border bg-card self-start"
        >
          <ChipButton
            active={!form.duty_manual_mode}
            disabled={readOnly || saving}
            onClick={() => update("duty_manual_mode", false)}
          >
            Auto
          </ChipButton>
          <ChipButton
            active={form.duty_manual_mode}
            disabled={readOnly || saving}
            onClick={() => update("duty_manual_mode", true)}
          >
            Manual
          </ChipButton>
        </div>
      )}

      {isManual ? (
        <div className="flex flex-col gap-2 rounded-md border border-border bg-muted/10 p-2">
          {/* Rate-type chip toggle */}
          <div
            role="group"
            aria-label="Тип ставки"
            className="inline-flex overflow-hidden rounded-md border border-border bg-card self-start"
          >
            <ChipButton
              active={form.duty_rate_type === "simple"}
              disabled={readOnly || saving}
              onClick={() => update("duty_rate_type", "simple")}
            >
              Простая
            </ChipButton>
            <ChipButton
              active={form.duty_rate_type === "combined"}
              disabled={readOnly || saving}
              onClick={() => update("duty_rate_type", "combined")}
            >
              Комбинированная
            </ChipButton>
            <ChipButton
              active={form.duty_rate_type === "specific"}
              disabled={readOnly || saving}
              onClick={() => update("duty_rate_type", "specific")}
            >
              Специфическая
            </ChipButton>
          </div>

          {/* Slot 1 */}
          <DutySlotRow
            value={form.duty_value_1}
            onValueChange={(v) => update("duty_value_1", v)}
            unit={form.duty_unit_1}
            onUnitChange={(u) => update("duty_unit_1", u)}
            // Specific cannot be "percent" — only specific currency units.
            allowPercent={form.duty_rate_type !== "specific"}
            disabled={readOnly || saving}
          />

          {/* Combined: sign selector + slot 2 */}
          {form.duty_rate_type === "combined" && (
            <>
              <select
                aria-label="Связь между slot 1 и slot 2"
                value={form.duty_sign ?? ">"}
                onChange={(e) =>
                  update("duty_sign", e.target.value as DutySign)
                }
                disabled={readOnly || saving}
                className="self-start rounded-md border border-border bg-card text-sm px-2 py-1"
              >
                <option value=">">но не менее</option>
                <option value="+">плюс</option>
              </select>
              <DutySlotRow
                value={form.duty_value_2}
                onValueChange={(v) => update("duty_value_2", v)}
                unit={form.duty_unit_2}
                onUnitChange={(u) => update("duty_unit_2", u)}
                allowPercent
                disabled={readOnly || saving}
              />
            </>
          )}

          {/* Live preview formula */}
          <div
            data-testid="duty-formula-preview"
            className="text-xs font-mono text-amber-300 mt-1 break-words"
          >
            {previewText}
          </div>
        </div>
      ) : (
        // Auto branch — the legacy single-input + (% / ₽/кг) chip pair.
        // Unchanged behavior: calc-engine reads customs_duty /
        // customs_duty_per_kg directly. AutoResolveButton + RateBreakdown
        // continue to render in the section below.
        <div className="flex gap-2">
          <Input
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            value={form.duty_value}
            onChange={(e) => update("duty_value", e.target.value)}
            disabled={readOnly || saving}
            className="flex-1"
            placeholder="0"
          />
          <div
            role="group"
            aria-label="Тип пошлины"
            className="inline-flex overflow-hidden rounded-md border border-border bg-card"
          >
            <ChipButton
              active={form.duty_mode === "pct"}
              disabled={readOnly || saving}
              onClick={() => update("duty_mode", "pct")}
            >
              %
            </ChipButton>
            <ChipButton
              active={form.duty_mode === "perKg"}
              disabled={readOnly || saving}
              onClick={() => update("duty_mode", "perKg")}
            >
              ₽/кг
            </ChipButton>
            <ChipButton
              active={false}
              disabled
              title="Требуется миграция: колонка customs_duty_per_pc"
            >
              ₽/шт
            </ChipButton>
          </div>
        </div>
      )}
    </div>
  );
}

function DutySlotRow({
  value,
  onValueChange,
  unit,
  onUnitChange,
  allowPercent,
  disabled,
}: {
  value: string;
  onValueChange: (v: string) => void;
  unit: DutyUnit;
  onUnitChange: (u: DutyUnit) => void;
  allowPercent: boolean;
  disabled: boolean;
}) {
  const options = allowPercent
    ? DUTY_UNIT_OPTIONS
    : DUTY_UNIT_OPTIONS.filter((o) => o.value !== "percent");
  return (
    <div className="flex gap-2">
      <Input
        type="number"
        inputMode="decimal"
        step="0.01"
        min="0"
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        disabled={disabled}
        className="flex-1"
        placeholder="0"
        aria-label="Значение ставки"
      />
      <select
        aria-label="Единица ставки"
        value={unit}
        onChange={(e) => onUnitChange(e.target.value as DutyUnit)}
        disabled={disabled}
        className="rounded-md border border-border bg-card text-sm px-2 py-1"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

/**
 * Best-effort customs_value extraction for the live preview.
 *
 * Prefers an explicit RUB-denominated field if the row carries one, then
 * falls back to proforma_amount_excl_vat which represents purchase price
 * × quantity in the proforma currency. Returns null when nothing is
 * available — callers render "—" rather than a misleading number.
 */
function extractCustomsValue(item: QuoteItemRow): number | null {
  const row = item as Record<string, unknown>;
  const rub = row.customs_value_rub ?? row.customs_value;
  if (typeof rub === "number" && Number.isFinite(rub)) return rub;
  const proforma = row.proforma_amount_excl_vat;
  if (typeof proforma === "number" && Number.isFinite(proforma)) return proforma;
  return null;
}

function LicenseRow({
  label,
  required,
  onRequiredChange,
  cost,
  onCostChange,
  disabled,
}: {
  label: string;
  required: boolean;
  onRequiredChange: (v: boolean) => void;
  cost: string;
  onCostChange: (v: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-border bg-card px-3 py-2">
      <label className="flex items-center gap-2 cursor-pointer flex-1 min-w-[200px]">
        <Checkbox
          checked={required}
          onCheckedChange={(checked) => onRequiredChange(checked === true)}
          disabled={disabled}
        />
        <span className="text-sm text-foreground">{label}</span>
      </label>
      <div className="flex items-center gap-2">
        <Input
          type="number"
          inputMode="decimal"
          step="0.01"
          min="0"
          value={cost}
          onChange={(e) => onCostChange(e.target.value)}
          disabled={disabled || !required}
          className="w-32 text-right tabular-nums"
          placeholder="0"
        />
        <span className="text-xs text-muted-foreground">₽</span>
      </div>
    </div>
  );
}
