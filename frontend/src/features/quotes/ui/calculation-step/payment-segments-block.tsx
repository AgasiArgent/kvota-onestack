"use client";

/**
 * Multi-segment client payment terms (Testing 2 row 46).
 *
 * Spec: `.kiro/specs/payment-segments-row-46/`
 *
 * Replaces the 3 single-field FormRows ("Аванс клиента", "До аванса", "До
 * расчёта") with a 5-anchor block matching the calc engine эталон
 * PaymentTerms. Anchor 5 % is auto-balanced (= 100 - Σ anchors 1-4) and
 * displayed read-only.
 *
 * Source of truth at calc-step is the parent `formValues` map — every input
 * change propagates via `onFieldChange` so the existing "Пересчитать" flow
 * persists payment fields to `quote_calculation_variables.variables` (the
 * calc engine input). When `specId` is provided the block also exposes a
 * "Сохранить" button that PATCHes `kvota.specifications` via the
 * `updateSpecificationPayment` server action — used after spec creation
 * for inline edits.
 */

import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { updateSpecificationPayment } from "@/entities/specification";

interface PaymentSegmentsBlockProps {
  /**
   * 9 controlled string values from the parent calc form. Strings (not
   * numbers) because the parent stores all form fields as strings to
   * mirror the existing `formValues` map shape used by the calc API.
   */
  values: {
    advance_from_client: string;
    time_to_advance: string;
    advance_on_loading: string;
    time_to_advance_loading: string;
    advance_on_going_to_country_destination: string;
    time_to_advance_going_to_country_destination: string;
    advance_on_customs_clearance: string;
    time_to_advance_on_customs_clearance: string;
    time_to_advance_on_receiving: string;
  };
  /** Parent's setter — every input change calls this with the engine field name. */
  onFieldChange: (key: string, value: string) => void;
  /**
   * When provided, "Сохранить" persists current segments to
   * `kvota.specifications` via the server action. When undefined (e.g.,
   * spec not yet created), the save button is hidden — fields still
   * persist via the existing calc submit ("Пересчитать").
   */
  specId?: string | null;
  /** Optional callback fired after a successful spec save. */
  onSaved?: () => void;
}

const PRESET_30_70 = {
  advance_from_client: "30",
  time_to_advance: "7",
  advance_on_loading: "0",
  time_to_advance_loading: "0",
  advance_on_going_to_country_destination: "0",
  time_to_advance_going_to_country_destination: "0",
  advance_on_customs_clearance: "0",
  time_to_advance_on_customs_clearance: "0",
  time_to_advance_on_receiving: "30",
} as const;

const PRESET_50_50 = {
  ...PRESET_30_70,
  advance_from_client: "50",
} as const;

const PRESET_70_30 = {
  ...PRESET_30_70,
  advance_from_client: "70",
} as const;

const PRESET_20_30_50 = {
  advance_from_client: "20",
  time_to_advance: "7",
  advance_on_loading: "0",
  time_to_advance_loading: "0",
  advance_on_going_to_country_destination: "30",
  time_to_advance_going_to_country_destination: "30",
  advance_on_customs_clearance: "0",
  time_to_advance_on_customs_clearance: "0",
  time_to_advance_on_receiving: "60",
} as const;

const PRESET_RESET = {
  advance_from_client: "100",
  time_to_advance: "0",
  advance_on_loading: "0",
  time_to_advance_loading: "0",
  advance_on_going_to_country_destination: "0",
  time_to_advance_going_to_country_destination: "0",
  advance_on_customs_clearance: "0",
  time_to_advance_on_customs_clearance: "0",
  time_to_advance_on_receiving: "0",
} as const;

const PRESETS: Record<string, Readonly<Record<string, string>>> = {
  "30/70": PRESET_30_70,
  "50/50": PRESET_50_50,
  "70/30": PRESET_70_30,
  "20/30/50": PRESET_20_30_50,
  Сброс: PRESET_RESET,
};

function parsePct(raw: string): number {
  const n = Number.parseFloat(raw);
  return Number.isFinite(n) ? n : 0;
}

function parseDays(raw: string): number {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : 0;
}

export function PaymentSegmentsBlock({
  values,
  onFieldChange,
  specId,
  onSaved,
}: PaymentSegmentsBlockProps) {
  const [saving, startSaveTransition] = useTransition();
  // Local optimistic flag so we surface "Saved ✓" briefly after a write.
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const anchor1Pct = parsePct(values.advance_from_client);
  const anchor2Pct = parsePct(values.advance_on_loading);
  const anchor3Pct = parsePct(values.advance_on_going_to_country_destination);
  const anchor4Pct = parsePct(values.advance_on_customs_clearance);

  const explicitPctSum = useMemo(
    () => anchor1Pct + anchor2Pct + anchor3Pct + anchor4Pct,
    [anchor1Pct, anchor2Pct, anchor3Pct, anchor4Pct]
  );
  const receivingPct = 100 - explicitPctSum;

  // Anchor 5 % is auto-balanced (= 100 - Σ anchors 1-4). Any explicit sum
  // ≤ 100 is "valid" (total is always exactly 100 incl. anchor 5). Only the
  // > 100 case is invalid — there's no headroom for anchor 5 and the DB
  // CHECK rejects the row.
  const sumStatus: "valid" | "over" = explicitPctSum <= 100 ? "valid" : "over";
  const sumValid = sumStatus === "valid";

  function applyPreset(presetKey: string): void {
    const preset = PRESETS[presetKey];
    if (!preset) return;
    for (const [k, v] of Object.entries(preset)) {
      onFieldChange(k, v);
    }
  }

  function handleSave(): void {
    if (!specId) return;
    if (!sumValid) {
      toast.error(
        `Сумма % = ${explicitPctSum}%, превышение на ${explicitPctSum - 100}%`
      );
      return;
    }

    startSaveTransition(async () => {
      try {
        await updateSpecificationPayment(specId, {
          advance_percent_from_client: anchor1Pct,
          payment_deferral_days: parseDays(values.time_to_advance),
          payment_on_loading_pct: anchor2Pct,
          payment_on_loading_days: parseDays(values.time_to_advance_loading),
          payment_on_country_arrival_pct: anchor3Pct,
          payment_on_country_arrival_days: parseDays(
            values.time_to_advance_going_to_country_destination
          ),
          payment_on_customs_clearance_pct: anchor4Pct,
          payment_on_customs_clearance_days: parseDays(
            values.time_to_advance_on_customs_clearance
          ),
          payment_on_receiving_days: parseDays(values.time_to_advance_on_receiving),
        });
        toast.success("Условия оплаты сохранены");
        setSavedAt(Date.now());
        onSaved?.();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Не удалось сохранить";
        toast.error(message);
      }
    });
  }

  return (
    <section
      data-testid="payment-segments-block"
      className="rounded-md border border-border bg-card p-4 space-y-3"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wide text-muted-foreground">
          Условия оплаты
        </h3>
        <SumIndicator
          status={sumStatus}
          explicitPctSum={explicitPctSum}
          receivingPct={receivingPct}
        />
      </header>

      <QuickPresets onApply={applyPreset} />

      <div className="space-y-2">
        <PaymentRow
          label="Аванс клиента"
          pct={values.advance_from_client}
          days={values.time_to_advance}
          onPctChange={(v) => onFieldChange("advance_from_client", v)}
          onDaysChange={(v) => onFieldChange("time_to_advance", v)}
        />
        <PaymentRow
          label="При погрузке"
          pct={values.advance_on_loading}
          days={values.time_to_advance_loading}
          onPctChange={(v) => onFieldChange("advance_on_loading", v)}
          onDaysChange={(v) => onFieldChange("time_to_advance_loading", v)}
        />
        <PaymentRow
          label="При прибытии в страну"
          pct={values.advance_on_going_to_country_destination}
          days={values.time_to_advance_going_to_country_destination}
          onPctChange={(v) =>
            onFieldChange("advance_on_going_to_country_destination", v)
          }
          onDaysChange={(v) =>
            onFieldChange("time_to_advance_going_to_country_destination", v)
          }
        />
        <PaymentRow
          label="При таможне"
          pct={values.advance_on_customs_clearance}
          days={values.time_to_advance_on_customs_clearance}
          onPctChange={(v) => onFieldChange("advance_on_customs_clearance", v)}
          onDaysChange={(v) =>
            onFieldChange("time_to_advance_on_customs_clearance", v)
          }
        />
        <PaymentRow
          label="После получения"
          pct={String(receivingPct)}
          days={values.time_to_advance_on_receiving}
          pctReadOnly
          pctInvalid={receivingPct < 0}
          onPctChange={() => {
            /* read-only — derived from explicit anchors */
          }}
          onDaysChange={(v) => onFieldChange("time_to_advance_on_receiving", v)}
        />
      </div>

      {specId ? (
        <footer className="flex items-center justify-end gap-2">
          {savedAt && !saving ? (
            <span className="text-[11px] text-muted-foreground">
              Сохранено
            </span>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            disabled={!sumValid || saving}
            onClick={handleSave}
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </Button>
        </footer>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Значения применятся при пересчёте и сохранятся в спецификации после её
          создания.
        </p>
      )}
    </section>
  );
}

interface SumIndicatorProps {
  status: "valid" | "over";
  explicitPctSum: number;
  receivingPct: number;
}

function SumIndicator({
  status,
  explicitPctSum,
  receivingPct,
}: SumIndicatorProps) {
  if (status === "valid") {
    // Receiving anchor (5) closes the gap to 100% automatically — total
    // shown is always 100. Sub-label calls out the implicit anchor 5 when
    // anchors 1-4 do not reach 100 explicitly.
    const hasReceiving = receivingPct > 0;
    return (
      <span
        data-testid="payment-sum-indicator"
        data-status="valid"
        className="text-[11px] font-medium text-green-700"
      >
        Σ = 100% ✓
        {hasReceiving ? (
          <span className="ml-1 text-muted-foreground">
            ({explicitPctSum.toFixed(0)}% + {receivingPct.toFixed(0)}% «после получения»)
          </span>
        ) : null}
      </span>
    );
  }
  return (
    <span
      data-testid="payment-sum-indicator"
      data-status="over"
      className="text-[11px] font-medium text-destructive"
    >
      Σ = {explicitPctSum.toFixed(0)}% — превышение на {(explicitPctSum - 100).toFixed(0)}%
    </span>
  );
}

interface QuickPresetsProps {
  onApply: (presetKey: string) => void;
}

function QuickPresets({ onApply }: QuickPresetsProps) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {Object.keys(PRESETS).map((key) => (
        <button
          key={key}
          type="button"
          data-testid={`payment-preset-${key}`}
          onClick={() => onApply(key)}
          className="text-[11px] px-2 py-0.5 border border-border rounded-sm bg-background hover:bg-muted text-muted-foreground"
        >
          {key}
        </button>
      ))}
    </div>
  );
}

interface PaymentRowProps {
  label: string;
  pct: string;
  days: string;
  pctReadOnly?: boolean;
  pctInvalid?: boolean;
  onPctChange: (value: string) => void;
  onDaysChange: (value: string) => void;
}

function PaymentRow({
  label,
  pct,
  days,
  pctReadOnly,
  pctInvalid,
  onPctChange,
  onDaysChange,
}: PaymentRowProps) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label className="text-xs text-muted-foreground shrink-0 w-44">
        {label}
      </Label>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            max={100}
            step={1}
            value={pct}
            readOnly={pctReadOnly}
            aria-label={`${label} — процент`}
            aria-invalid={pctInvalid || undefined}
            onChange={(e) => onPctChange(e.target.value)}
            className={`w-16 text-right ${pctReadOnly ? "bg-muted text-muted-foreground" : ""} ${pctInvalid ? "border-destructive" : ""}`}
          />
          <span className="text-xs text-muted-foreground">%</span>
        </div>
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            step={1}
            value={days}
            aria-label={`${label} — дни`}
            onChange={(e) => onDaysChange(e.target.value)}
            className="w-16 text-right"
          />
          <span className="text-xs text-muted-foreground">дн.</span>
        </div>
      </div>
    </div>
  );
}
