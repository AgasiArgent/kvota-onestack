"use client";

import { useEffect, useState, useTransition } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type {
  LocationOption,
  LocationType,
} from "@/entities/location";
import { LocationChip } from "@/entities/location/ui/location-chip";
import type {
  LogisticsSegment,
  LogisticsSegmentExpense,
  SegmentPatch,
} from "@/entities/logistics-segment";
import {
  createSegmentExpense,
  deleteSegmentExpense,
  updateSegment,
} from "@/entities/logistics-segment";
import { cn } from "@/lib/utils";

/**
 * SegmentDetailsPanel — inline editor for the currently-selected segment.
 *
 * Pattern: fields are locally controlled for instant feedback; on `blur`
 * (or select change) the patch is flushed to the server via
 * {@link updateSegment}, then Next router.refresh() reloads fresh server
 * props. Optimistic UI is intentional — failures surface via toast.
 *
 * Expenses are managed inline (create/delete) through their own server
 * actions. Expense edits require delete + re-create in the current API;
 * if that shows up in usage we'll add PATCH later.
 */

const rubFmt = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

interface SegmentDetailsPanelProps {
  segment: LogisticsSegment | null;
  locations: LocationOption[];
  revalidatePath: string;
  onLocalUpdate?: (id: string, patch: Partial<LogisticsSegment>) => void;
  disabled?: boolean;
}

export function SegmentDetailsPanel({
  segment,
  locations,
  revalidatePath,
  onLocalUpdate,
  disabled,
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
        />

        <SegmentExpensesList
          segmentId={segment.id}
          expenses={segment.expenses}
          revalidatePath={revalidatePath}
          disabled={disabled}
        />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Fields (from/to, days, cost, carrier, label, notes)
// ---------------------------------------------------------------------------

const LOCATION_TYPE_ORDER: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function locationTypeLabel(type: LocationType): string {
  switch (type) {
    case "supplier":
      return "Поставщики";
    case "hub":
      return "Хабы";
    case "customs":
      return "Таможня";
    case "own_warehouse":
      return "Склады";
    case "client":
      return "Клиенты";
  }
}

interface SegmentFieldsProps {
  segment: LogisticsSegment;
  locations: LocationOption[];
  revalidatePath: string;
  onLocalUpdate?: (id: string, patch: Partial<LogisticsSegment>) => void;
  disabled?: boolean;
}

function SegmentFields({
  segment,
  locations,
  revalidatePath,
  onLocalUpdate,
  disabled,
}: SegmentFieldsProps) {
  const [label, setLabel] = useState(segment.label ?? "");
  const [carrier, setCarrier] = useState(segment.carrier ?? "");
  const [notes, setNotes] = useState(segment.notes ?? "");
  const [transitDays, setTransitDays] = useState(
    segment.transitDays != null ? String(segment.transitDays) : "",
  );
  const [mainCost, setMainCost] = useState(String(segment.mainCostRub ?? 0));
  const [, startTransition] = useTransition();

  // Re-sync when switching selected segment
  useEffect(() => {
    setLabel(segment.label ?? "");
    setCarrier(segment.carrier ?? "");
    setNotes(segment.notes ?? "");
    setTransitDays(segment.transitDays != null ? String(segment.transitDays) : "");
    setMainCost(String(segment.mainCostRub ?? 0));
  }, [segment.id, segment.label, segment.carrier, segment.notes, segment.transitDays, segment.mainCostRub]);

  const locationsByType = LOCATION_TYPE_ORDER.map((type) => ({
    type,
    items: locations.filter((l) => l.type === type),
  })).filter((g) => g.items.length > 0);

  function patch(patch: SegmentPatch, local?: Partial<LogisticsSegment>) {
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

  function handleLocationChange(side: "from" | "to", value: string) {
    const selected = locations.find((l) => l.id === value);
    const local: Partial<LogisticsSegment> = selected
      ? {
          [side === "from" ? "fromLocation" : "toLocation"]: {
            id: selected.id,
            country: selected.country,
            iso2: selected.iso2,
            city: selected.city,
            type: selected.type,
          },
        }
      : {};
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
    patch({ [key]: parsed }, { transitDays: parsed ?? undefined });
  }

  function handleCostBlur(value: string) {
    const parsed = value === "" ? 0 : Number.parseFloat(value);
    if (Number.isNaN(parsed)) return;
    patch({ main_cost_rub: parsed }, { mainCostRub: parsed });
    setMainCost(String(parsed));
  }

  function handleTextBlur(
    value: string,
    key: "label" | "carrier" | "notes",
  ) {
    const trimmed = value;
    patch(
      { [key]: trimmed === "" ? null : trimmed },
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
        <Select
          value={segment.fromLocation?.id ?? ""}
          onValueChange={(v) => handleLocationChange("from", String(v))}
          disabled={disabled}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Выберите локацию…" />
          </SelectTrigger>
          <SelectContent>
            {locationsByType.map((group) => (
              <SelectGroup key={group.type}>
                <div className="px-2 pt-1 pb-0.5 text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
                  {locationTypeLabel(group.type)}
                </div>
                {group.items.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {formatLocationLabel(loc)}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      </Field>
      <Field label="Куда">
        <Select
          value={segment.toLocation?.id ?? ""}
          onValueChange={(v) => handleLocationChange("to", String(v))}
          disabled={disabled}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Выберите локацию…" />
          </SelectTrigger>
          <SelectContent>
            {locationsByType.map((group) => (
              <SelectGroup key={group.type}>
                <div className="px-2 pt-1 pb-0.5 text-[11px] font-semibold uppercase tracking-wide text-text-subtle">
                  {locationTypeLabel(group.type)}
                </div>
                {group.items.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {formatLocationLabel(loc)}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
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
      <Field label="Стоимость, ₽">
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
        />
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

function formatLocationLabel(loc: LocationOption): string {
  if (loc.city && loc.country) return `${loc.country} · ${loc.city}`;
  return loc.country || "—";
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

// ---------------------------------------------------------------------------
// Expenses
// ---------------------------------------------------------------------------

interface SegmentExpensesListProps {
  segmentId: string;
  expenses: LogisticsSegmentExpense[];
  revalidatePath: string;
  disabled?: boolean;
}

function SegmentExpensesList({
  segmentId,
  expenses,
  revalidatePath,
  disabled,
}: SegmentExpensesListProps) {
  const [label, setLabel] = useState("");
  const [cost, setCost] = useState("");
  const [isPending, startTransition] = useTransition();

  const total = expenses.reduce((a, e) => a + (e.costRub ?? 0), 0);

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
          revalidate_path: revalidatePath,
        });
        setLabel("");
        setCost("");
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
        <span className="text-xs text-text-muted tabular-nums">
          Σ {rubFmt.format(total)}
        </span>
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
                {rubFmt.format(expense.costRub)}
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

      <div className="grid grid-cols-[1fr_110px_auto] items-end gap-2 pt-1">
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
