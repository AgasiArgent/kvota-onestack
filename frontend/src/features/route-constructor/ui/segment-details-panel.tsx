"use client";

import { useEffect, useState, useTransition } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import {
  LOCATION_TYPE_LABEL,
  formatLocationLabel,
  type LocationOption,
} from "@/entities/location";
import { LocationChip } from "@/entities/location/ui/location-chip";
import type {
  LogisticsSegment,
  LogisticsSegmentExpense,
  SegmentCurrency,
  SegmentPatch,
} from "@/entities/logistics-segment";
import {
  SEGMENT_CURRENCIES,
  createSegmentExpense,
  deleteSegmentExpense,
  updateSegment,
} from "@/entities/logistics-segment";
import { supplierDeliversFirstSegment } from "@/shared/lib/incoterms";
import { cn } from "@/lib/utils";

/**
 * SegmentDetailsPanel — inline editor for the currently-selected segment.
 *
 * Pattern: fields are locally controlled for instant feedback; on `blur`
 * (or select change) the patch is flushed to the server via
 * {@link updateSegment}. Field edits are optimistic-only — `onLocalUpdate`
 * mirrors the change into the parent's `segments` state (route totals
 * recompute client-side), and `updateSegment` calls `revalidatePath`
 * server-side so the next real navigation gets fresh data. No
 * `router.refresh()` is fired for field edits — that would re-run the
 * whole `/quotes/[id]` route, remounting this panel and losing focus
 * (Testing 2 row 58). Failures surface via toast.
 *
 * Expenses are managed inline (create/delete) through their own server
 * actions. Expense edits require delete + re-create in the current API;
 * if that shows up in usage we'll add PATCH later.
 */

const CURRENCY_FMT_CACHE = new Map<string, Intl.NumberFormat>();

function formatCurrency(amount: number, code: SegmentCurrency): string {
  let fmt = CURRENCY_FMT_CACHE.get(code);
  if (!fmt) {
    fmt = new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: code,
      maximumFractionDigits: 0,
    });
    CURRENCY_FMT_CACHE.set(code, fmt);
  }
  return fmt.format(amount);
}

interface SegmentDetailsPanelProps {
  segment: LogisticsSegment | null;
  locations: LocationOption[];
  revalidatePath: string;
  onLocalUpdate?: (id: string, patch: Partial<LogisticsSegment>) => void;
  /**
   * Bubbles up to the parent (LogisticsStep) so the client-side Supabase
   * loader can re-fetch after server mutations. router.refresh() alone
   * does not re-run useEffects whose deps haven't changed (Testing 2 row 30).
   */
  onMutation?: () => void;
  disabled?: boolean;
  /**
   * Parent invoice's `supplier_incoterms`. When this resolves to a
   * supplier-delivers term (DAP/DPU/DDP/CPT/CIP/CFR/CIF) AND the selected
   * segment is the first one, the cost input is locked at 0 and a
   * «Поставщик доставляет» badge replaces the editable field. Testing 2
   * row 44.
   */
  supplierIncoterms?: string | null;
}

export function SegmentDetailsPanel({
  segment,
  locations,
  revalidatePath,
  onLocalUpdate,
  onMutation,
  disabled,
  supplierIncoterms,
}: SegmentDetailsPanelProps) {
  if (!segment) {
    return (
      <div className="rounded-lg border border-border-light bg-card px-4 py-8 text-center">
        <p className="text-sm text-text-muted">
          Выберите сегмент слева, чтобы увидеть детали.
        </p>
      </div>
    );
  }

  return (
    <section
      className="rounded-lg border border-border-light bg-card"
      aria-label={`Детали сегмента ${segment.sequenceOrder}`}
    >
      <header className="flex items-center justify-between border-b border-border-light px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex size-6 items-center justify-center rounded-sm bg-sidebar text-xs font-semibold text-text">
            {segment.sequenceOrder}
          </span>
          <h3 className="text-sm font-semibold text-text">
            Детали сегмента
          </h3>
        </div>
        {segment.label && (
          <LocationChip
            variant="ghost"
            size="sm"
            label={segment.label}
            className="bg-accent-subtle/60 text-info"
          />
        )}
      </header>

      <div className="flex flex-col gap-3 p-4">
        <SegmentFields
          key={segment.id}
          segment={segment}
          locations={locations}
          revalidatePath={revalidatePath}
          onLocalUpdate={onLocalUpdate}
          disabled={disabled}
          supplierIncoterms={supplierIncoterms}
        />

        <SegmentExpensesList
          segmentId={segment.id}
          expenses={segment.expenses}
          revalidatePath={revalidatePath}
          onMutation={onMutation}
          disabled={disabled}
        />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Fields (from/to, days, cost, carrier, label, notes)
// ---------------------------------------------------------------------------

interface SegmentFieldsProps {
  segment: LogisticsSegment;
  locations: LocationOption[];
  revalidatePath: string;
  onLocalUpdate?: (id: string, patch: Partial<LogisticsSegment>) => void;
  disabled?: boolean;
  supplierIncoterms?: string | null;
}

function SegmentFields({
  segment,
  locations,
  revalidatePath,
  onLocalUpdate,
  disabled,
  supplierIncoterms,
}: SegmentFieldsProps) {
  const [label, setLabel] = useState(segment.label ?? "");
  const [carrier, setCarrier] = useState(segment.carrier ?? "");
  const [notes, setNotes] = useState(segment.notes ?? "");
  const [transitDays, setTransitDays] = useState(
    segment.transitDays != null ? String(segment.transitDays) : "",
  );
  const [mainCost, setMainCost] = useState(String(segment.mainCostRub ?? 0));
  const [currencyCode, setCurrencyCode] = useState<SegmentCurrency>(
    segment.currencyCode,
  );
  const [, startTransition] = useTransition();

  // Testing 2 row 44 — first-segment cost is locked at 0 when the parent
  // invoice's supplier_incoterms implies the supplier is delivering the
  // first leg at their own expense (D-terms + C-terms).
  const isFirstSegment = segment.sequenceOrder === 1;
  const supplierCoversFirstSegment =
    isFirstSegment && supplierDeliversFirstSegment(supplierIncoterms);

  // Re-sync local input state ONLY when the user switches to a different
  // segment. Earlier code listed every individual field in the deps array,
  // which caused the effect to re-run mid-edit on any unrelated server
  // update (e.g. revalidatePath cascading down a new `segment` object with
  // the same id). The effect would then call setLabel("") / setCarrier("")
  // while the user was still typing, wiping their input — РОЛ Тест 07 #3.6
  // ("страница remount при наборе 1 символа"). The parent already mounts
  // SegmentFields with `key={segment.id}`, so this hook is a defensive
  // re-init for the rare case of an in-place segment swap; it must never
  // overwrite user input on field-level updates.
  useEffect(() => {
    setLabel(segment.label ?? "");
    setCarrier(segment.carrier ?? "");
    setNotes(segment.notes ?? "");
    setTransitDays(segment.transitDays != null ? String(segment.transitDays) : "");
    setMainCost(String(segment.mainCostRub ?? 0));
    setCurrencyCode(segment.currencyCode);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional: see comment above
  }, [segment.id]);

  // Testing 2 row 44 — once we enter the «supplier delivers» state on a
  // first segment that still carries a non-zero cost, drop it to 0 on the
  // server. Without this, switching the parent invoice's incoterms from
  // EXW → DAP would leave the old buyer-paid cost dangling in the DB even
  // though the UI now displays «Поставщик доставляет».
  useEffect(() => {
    if (!supplierCoversFirstSegment) return;
    if ((segment.mainCostRub ?? 0) === 0) return;
    setMainCost("0");
    startTransition(async () => {
      try {
        await updateSegment({
          segment_id: segment.id,
          patch: { main_cost_rub: 0 },
          revalidate_path: revalidatePath,
        });
        if (onLocalUpdate) onLocalUpdate(segment.id, { mainCostRub: 0 });
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Не удалось сохранить";
        toast.error(msg);
      }
    });
    // We do NOT depend on segment.mainCostRub — the auto-zero ran once when
    // the «supplier delivers» state turned on, no need to re-fire on each
    // optimistic update inside the same render cycle.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supplierCoversFirstSegment, segment.id]);

  function patch(patch: SegmentPatch, local?: Partial<LogisticsSegment>) {
    // Field edits are optimistic-only: `onLocalUpdate` keeps the parent's
    // `segments` state (and the client-computed route totals) correct, and
    // `updateSegment` persists + revalidates the Next cache server-side.
    // We deliberately do NOT call `onMutation()` here — that would trigger
    // router.refresh(), re-running the whole /quotes/[id] route and
    // remounting this panel mid-edit (Testing 2 row 58: scroll jump +
    // focus loss). Structural ops (create/delete/reorder/template) still
    // refresh in route-constructor.tsx because they need server-generated
    // IDs / re-sequencing.
    if (local && onLocalUpdate) onLocalUpdate(segment.id, local);
    startTransition(async () => {
      try {
        await updateSegment({
          segment_id: segment.id,
          patch,
          revalidate_path: revalidatePath,
        });
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось сохранить",
        );
      }
    });
  }

  function handleLocationChange(side: "from" | "to", value: string | null) {
    // Combobox is non-clearable (DB column is NOT NULL) — guard against
    // an unexpected null emission rather than PATCHing a value the API rejects.
    // Both branches below are "impossible" under the current contract, so a
    // hit means a real regression — surface via console.warn instead of a
    // silent return so it shows up in DevTools.
    if (!value) {
      console.warn(
        `[SegmentDetailsPanel] handleLocationChange(${side}) got falsy value with clearable=false`,
      );
      return;
    }
    // No-op guard (Testing 2 row 30 #2): re-selecting the location already
    // assigned to this side must not trigger a PATCH / refetch.
    const currentId =
      side === "from" ? segment.fromLocation?.id : segment.toLocation?.id;
    if (value === currentId) return;
    const selected = locations.find((l) => l.id === value);
    if (!selected) {
      console.warn(
        `[SegmentDetailsPanel] handleLocationChange(${side}): combobox emitted id ${value} but no matching location in items list`,
      );
      return;
    }
    const local: Partial<LogisticsSegment> = {
      [side === "from" ? "fromLocation" : "toLocation"]: {
        id: selected.id,
        country: selected.country,
        iso2: selected.iso2,
        city: selected.city,
        type: selected.type,
      },
    };
    patch(
      side === "from"
        ? { from_location_id: value }
        : { to_location_id: value },
      local,
    );
  }

  function handleIntBlur(value: string, key: "transit_days") {
    const parsed = value === "" ? null : Number.parseInt(value, 10);
    if (parsed != null && Number.isNaN(parsed)) return;
    // No-op guard (Testing 2 row 30 #2): a blur with no change must not save.
    const current = segment.transitDays ?? null;
    if (parsed === current) return;
    patch({ [key]: parsed }, { transitDays: parsed ?? undefined });
  }

  function handleCostBlur(value: string) {
    const parsed = value === "" ? 0 : Number.parseFloat(value);
    if (Number.isNaN(parsed)) return;
    // No-op guard (Testing 2 row 30 #2): a blur with no change must not save.
    if (parsed === (segment.mainCostRub ?? 0)) {
      setMainCost(String(parsed));
      return;
    }
    patch({ main_cost_rub: parsed }, { mainCostRub: parsed });
    setMainCost(String(parsed));
  }

  function handleCurrencyChange(next: SegmentCurrency) {
    if (next === currencyCode) return;
    setCurrencyCode(next);
    patch({ currency_code: next }, { currencyCode: next });
  }

  function handleTextBlur(
    value: string,
    key: "label" | "carrier" | "notes",
  ) {
    const trimmed = value;
    // No-op guard (Testing 2 row 30 #2): clicking a Перевозчик / Метка /
    // Примечание cell and blurring without an edit must not persist or
    // trigger a refetch. Compare the normalised new value against the
    // segment's current value (both empty-string and null mean "unset").
    const next = trimmed === "" ? null : trimmed;
    const current = (segment[key] ?? null) || null;
    if (next === current) return;
    patch(
      { [key]: next },
      {
        label: key === "label" ? (trimmed || undefined) : segment.label,
        carrier: key === "carrier" ? (trimmed || undefined) : segment.carrier,
        notes: key === "notes" ? (trimmed || undefined) : segment.notes,
      },
    );
  }

  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <Field label="Откуда">
        <SearchableCombobox
          ariaLabel="Локация отправления"
          value={segment.fromLocation?.id ?? null}
          onChange={(v) => handleLocationChange("from", v)}
          items={locations}
          getLabel={formatLocationLabel}
          getSecondary={(loc) => LOCATION_TYPE_LABEL[loc.type]}
          getSearchableExtras={(loc) => [LOCATION_TYPE_LABEL[loc.type], loc.city ?? ""]}
          placeholder="Выберите локацию…"
          emptyMessage="Нет локаций — создайте их в «Справочниках»."
          clearable={false}
          disabled={disabled}
        />
      </Field>
      <Field label="Куда">
        <SearchableCombobox
          ariaLabel="Локация назначения"
          value={segment.toLocation?.id ?? null}
          onChange={(v) => handleLocationChange("to", v)}
          items={locations}
          getLabel={formatLocationLabel}
          getSecondary={(loc) => LOCATION_TYPE_LABEL[loc.type]}
          getSearchableExtras={(loc) => [LOCATION_TYPE_LABEL[loc.type], loc.city ?? ""]}
          placeholder="Выберите локацию…"
          emptyMessage="Нет локаций — создайте их в «Справочниках»."
          clearable={false}
          disabled={disabled}
        />
      </Field>

      <Field label="Транзит (дней)">
        <Input
          type="number"
          min={0}
          step={1}
          value={transitDays}
          onChange={(e) => setTransitDays(e.target.value)}
          onBlur={(e) => handleIntBlur(e.target.value, "transit_days")}
          placeholder="0"
          disabled={disabled}
          className="tabular-nums"
        />
      </Field>
      <Field label="Стоимость">
        {supplierCoversFirstSegment ? (
          // Testing 2 row 44 — display-only banner when the supplier covers
          // this leg under their Incoterms. Editable input is suppressed so
          // logistics can't accidentally re-introduce a cost the customer
          // shouldn't see.
          <div className="rounded-md border border-border-light bg-accent-subtle/40 px-3 py-2 text-xs text-text">
            <span className="font-medium">Поставщик доставляет</span>
            {supplierIncoterms ? (
              <span className="ml-1 text-text-muted">
                (Incoterms {supplierIncoterms})
              </span>
            ) : null}
            <span className="ml-2 tabular-nums text-text-muted">
              · 0 {currencyCode}
            </span>
          </div>
        ) : (
          <div className="flex gap-1.5">
            <Input
              type="number"
              min={0}
              step={1}
              value={mainCost}
              onChange={(e) => setMainCost(e.target.value)}
              onBlur={(e) => handleCostBlur(e.target.value)}
              placeholder="0"
              disabled={disabled}
              className="tabular-nums"
              aria-label="Сумма"
            />
            <CurrencyPicker
              value={currencyCode}
              onChange={handleCurrencyChange}
              disabled={disabled}
              ariaLabel="Валюта стоимости"
            />
          </div>
        )}
      </Field>

      <Field label="Перевозчик">
        <Input
          value={carrier}
          onChange={(e) => setCarrier(e.target.value)}
          onBlur={(e) => handleTextBlur(e.target.value, "carrier")}
          placeholder="Название перевозчика"
          disabled={disabled}
        />
      </Field>
      <Field label="Метка">
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          onBlur={(e) => handleTextBlur(e.target.value, "label")}
          placeholder="First mile, Main freight, …"
          disabled={disabled}
        />
      </Field>

      <Field label="Примечание" className="md:col-span-2">
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={(e) => handleTextBlur(e.target.value, "notes")}
          rows={3}
          placeholder="Дополнительная информация о сегменте"
          disabled={disabled}
        />
      </Field>
    </div>
  );
}

function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex flex-col gap-1", className)}>
      <span className="text-xs font-medium text-text-muted">{label}</span>
      {children}
    </label>
  );
}

interface CurrencyPickerProps {
  value: SegmentCurrency;
  onChange: (next: SegmentCurrency) => void;
  disabled?: boolean;
  ariaLabel: string;
}

/**
 * CurrencyPicker — compact native <select> for the four supported segment
 * currencies. Native select keeps the keyboard / a11y story simple and
 * matches the design system's restraint (no animations, no bespoke
 * dropdowns for fixed 4-item lists).
 */
function CurrencyPicker({
  value,
  onChange,
  disabled,
  ariaLabel,
}: CurrencyPickerProps) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value as SegmentCurrency)}
      disabled={disabled}
      className={cn(
        "h-9 rounded-md border border-border-light bg-background px-2 text-sm text-text",
        "focus:outline-none focus:ring-2 focus:ring-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
      data-testid="segment-currency-picker"
    >
      {SEGMENT_CURRENCIES.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
    </select>
  );
}

// ---------------------------------------------------------------------------
// Expenses
// ---------------------------------------------------------------------------

interface SegmentExpensesListProps {
  segmentId: string;
  expenses: LogisticsSegmentExpense[];
  revalidatePath: string;
  onMutation?: () => void;
  disabled?: boolean;
}

function SegmentExpensesList({
  segmentId,
  expenses,
  revalidatePath,
  onMutation,
  disabled,
}: SegmentExpensesListProps) {
  const [label, setLabel] = useState("");
  const [cost, setCost] = useState("");
  const [currencyCode, setCurrencyCode] = useState<SegmentCurrency>("RUB");
  const [isPending, startTransition] = useTransition();

  function handleAdd() {
    const trimmed = label.trim();
    const parsed = Number.parseFloat(cost);
    if (!trimmed) {
      toast.error("Укажите название расхода");
      return;
    }
    if (Number.isNaN(parsed)) {
      toast.error("Укажите сумму расхода");
      return;
    }
    startTransition(async () => {
      try {
        await createSegmentExpense({
          segment_id: segmentId,
          label: trimmed,
          cost_rub: parsed,
          currency_code: currencyCode,
          revalidate_path: revalidatePath,
        });
        setLabel("");
        setCost("");
        onMutation?.();
        // Keep currency selection between adds — common case is several
        // expenses in the same currency for one segment.
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось добавить расход",
        );
      }
    });
  }

  function handleDelete(expenseId: string) {
    startTransition(async () => {
      try {
        await deleteSegmentExpense({
          expense_id: expenseId,
          revalidate_path: revalidatePath,
        });
        onMutation?.();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось удалить расход",
        );
      }
    });
  }

  return (
    <div className="flex flex-col gap-2 border-t border-border-light pt-4">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-text">Дополнительные расходы</h4>
      </div>

      {expenses.length === 0 ? (
        <p className="text-xs text-text-subtle">Нет дополнительных расходов</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {expenses.map((expense) => (
            <li
              key={expense.id}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-2 rounded-md border border-border-light bg-card px-2.5 py-1.5"
            >
              <span className="truncate text-sm text-text">
                {expense.label}
              </span>
              <span className="tabular-nums text-sm font-medium text-text">
                {formatCurrency(expense.costRub, expense.currencyCode)}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon-xs"
                onClick={() => handleDelete(expense.id)}
                disabled={disabled || isPending}
                aria-label={`Удалить расход ${expense.label}`}
                className="text-text-muted hover:text-error"
              >
                <Trash2 size={12} strokeWidth={2} />
              </Button>
            </li>
          ))}
        </ul>
      )}

      <div className="grid grid-cols-[1fr_110px_auto_auto] items-end gap-2 pt-1">
        <Input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Название расхода"
          disabled={disabled || isPending}
        />
        <Input
          type="number"
          min={0}
          step={1}
          value={cost}
          onChange={(e) => setCost(e.target.value)}
          placeholder="0"
          disabled={disabled || isPending}
          className="tabular-nums"
          aria-label="Сумма расхода"
        />
        <CurrencyPicker
          value={currencyCode}
          onChange={setCurrencyCode}
          disabled={disabled || isPending}
          ariaLabel="Валюта расхода"
        />
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleAdd}
          disabled={disabled || isPending}
          className="gap-1"
        >
          <Plus size={14} strokeWidth={2} aria-hidden />
          Добавить
        </Button>
      </div>
    </div>
  );
}
