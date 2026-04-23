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
}

interface FormState {
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
}

function stateFromItem(item: QuoteItemRow): FormState {
  const extras = ext<CustomsExtras>(item);
  const dutyPerKg = extras.customs_duty_per_kg ?? null;
  const duty = extras.customs_duty ?? null;
  const mode: DutyMode = dutyPerKg != null ? "perKg" : "pct";
  const compositeValue = mode === "perKg" ? dutyPerKg : duty;

  const numToStr = (n: number | null | undefined): string =>
    n == null ? "" : String(n);

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
  };
}

function parseNumOrNull(s: string): number | null {
  const trimmed = s.trim();
  if (trimmed === "") return null;
  const n = Number.parseFloat(trimmed);
  return Number.isFinite(n) ? n : null;
}

function buildUpdates(form: FormState): Record<string, unknown> {
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
  const canWrite = userRoles.some((r) => CAN_WRITE_ROLES.has(r));

  // Re-seed the form whenever a different row is opened. Avoids stale state
  // when the dialog is reused across rows.
  useEffect(() => {
    if (open && item) {
      setForm(stateFromItem(item));
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
              <Input
                value={form.hs_code}
                onChange={(e) => update("hs_code", e.target.value)}
                disabled={readOnly || saving}
                placeholder="0000000000"
              />
            </Field>

            <Field label="Пошлина">
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
