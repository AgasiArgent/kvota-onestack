"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2, ArrowRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import {
  LOCATION_TYPE_LABEL,
  formatLocationLabel,
  type LocationOption,
} from "@/entities/location";
import type { LocationType } from "@/entities/location/ui/location-chip";

/**
 * LogisticsTemplateDialog — creation form for a new logistics route template.
 *
 * Hybrid scaffold (РОЛ Тест 07 #3.5): each segment side carries a
 * (location_type) pair, plus an OPTIONAL concrete location id. When the
 * concrete id is set, apply_template uses it directly; otherwise it falls
 * back to type-based selection at apply time. Lets admins build a
 * "skeleton + pinned waypoint" template without forcing every leg to be
 * type-only.
 */

interface TemplateSegmentForm {
  sequence_order: number;
  from_location_type: LocationType;
  to_location_type: LocationType;
  default_label: string;
  default_days: number | null;
  /** Optional concrete from-location id (3.5). Null = type-only. */
  from_location_id: string | null;
  /** Optional concrete to-location id (3.5). Null = type-only. */
  to_location_id: string | null;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (input: {
    name: string;
    description: string;
    segments: TemplateSegmentForm[];
  }) => void;
  busy: boolean;
  /** Prefill values when editing an existing template. */
  initial?: {
    name: string;
    description: string;
    segments: TemplateSegmentForm[];
  };
  /**
   * All org-scoped locations for the optional concrete location pickers.
   * Empty array is acceptable — falls back to type-only templates.
   */
  locations?: LocationOption[];
}

const LOCATION_TYPES: Array<{ value: LocationType; label: string }> = [
  { value: "supplier", label: "Поставщик" },
  { value: "hub", label: "Хаб" },
  { value: "customs", label: "Таможня" },
  { value: "own_warehouse", label: "Склад" },
  { value: "client", label: "Клиент" },
];

interface ConcreteLocationFieldProps {
  label: string;
  locations: LocationOption[];
  value: string | null;
  onChange: (next: string | null) => void;
  disabled?: boolean;
}

/**
 * ConcreteLocationField — searchable picker that defaults to "Любая
 * локация типа выше" (i.e. type-only, value=null) and lets the admin pin
 * a specific location when needed (3.5 hybrid templates).
 */
function ConcreteLocationField({
  label,
  locations,
  value,
  onChange,
  disabled,
}: ConcreteLocationFieldProps) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-text-muted">{label}</span>
      <SearchableCombobox
        ariaLabel={label}
        value={value}
        onChange={(v) => onChange(v ?? null)}
        items={locations}
        getLabel={formatLocationLabel}
        getSecondary={(loc) => LOCATION_TYPE_LABEL[loc.type]}
        getSearchableExtras={(loc) => [
          LOCATION_TYPE_LABEL[loc.type],
          loc.city ?? "",
        ]}
        placeholder="Авто (по типу)"
        emptyMessage="Нет локаций — создайте их в «Справочниках»."
        clearable
        disabled={disabled}
      />
    </label>
  );
}

function emptySegment(sequence_order: number): TemplateSegmentForm {
  return {
    sequence_order,
    from_location_type: "supplier",
    to_location_type: "hub",
    default_label: "",
    default_days: null,
    from_location_id: null,
    to_location_id: null,
  };
}

export function LogisticsTemplateDialog({
  open,
  onOpenChange,
  onSubmit,
  busy,
  initial,
  locations = [],
}: Props) {
  const isEdit = Boolean(initial);
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [segments, setSegments] = useState<TemplateSegmentForm[]>(
    initial?.segments ?? [emptySegment(1)],
  );

  // Reset state whenever the dialog reopens with a (possibly different)
  // `initial` payload — sibling rows may open the same dialog in turn.
  useEffect(() => {
    if (open) {
      setName(initial?.name ?? "");
      setDescription(initial?.description ?? "");
      setSegments(initial?.segments ?? [emptySegment(1)]);
    }
  }, [open, initial]);

  const reset = () => {
    setName("");
    setDescription("");
    setSegments([emptySegment(1)]);
  };

  const addSegment = () => {
    setSegments((prev) => [
      ...prev,
      {
        ...emptySegment(prev.length + 1),
        // Chain new segment's "from" to previous "to" for natural flow
        from_location_type:
          prev[prev.length - 1]?.to_location_type ?? "supplier",
      },
    ]);
  };

  const removeSegment = (index: number) => {
    setSegments((prev) =>
      prev
        .filter((_, i) => i !== index)
        .map((s, i) => ({ ...s, sequence_order: i + 1 })),
    );
  };

  const updateSegment = (
    index: number,
    patch: Partial<TemplateSegmentForm>,
  ) => {
    setSegments((prev) =>
      prev.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    );
  };

  const canSubmit = name.trim().length > 0 && segments.length > 0 && !busy;

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({
      name: name.trim(),
      description: description.trim(),
      segments,
    });
    // Parent handles closing on success; we only reset on close.
  };

  const handleOpenChange = (o: boolean) => {
    if (!o) reset();
    onOpenChange(o);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="!max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Редактирование шаблона" : "Новый шаблон маршрута"}
          </DialogTitle>
          <DialogDescription>
            Опишите типовую цепочку перемещений. Логист применит шаблон к
            инвойсу и подставит конкретные локации.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
            <div>
              <Label htmlFor="tpl-name">Название</Label>
              <Input
                id="tpl-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Напр. «Китай → Россия через Алма-Ату»"
                disabled={busy}
                autoFocus
              />
            </div>

            <div>
              <Label htmlFor="tpl-desc">Описание</Label>
              <Textarea
                id="tpl-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Когда применять, ограничения, примечания"
                rows={2}
                disabled={busy}
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <Label>Сегменты маршрута</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={addSegment}
                  disabled={busy}
                >
                  <Plus size={14} aria-hidden /> Добавить сегмент
                </Button>
              </div>

              <div className="mt-2 space-y-2">
                {segments.map((seg, i) => (
                  <div
                    key={i}
                    className="rounded-md border border-border-light bg-card px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="shrink-0 text-xs text-text-subtle tabular-nums">
                        {seg.sequence_order}
                      </span>
                      <select
                        className="rounded border border-border-light bg-background px-2 py-1 text-sm"
                        value={seg.from_location_type}
                        onChange={(e) =>
                          updateSegment(i, {
                            from_location_type: e.target.value as LocationType,
                          })
                        }
                        disabled={busy}
                        aria-label="Тип начальной локации"
                      >
                        {LOCATION_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                      <ArrowRight
                        size={14}
                        className="text-text-subtle"
                        aria-hidden
                      />
                      <select
                        className="rounded border border-border-light bg-background px-2 py-1 text-sm"
                        value={seg.to_location_type}
                        onChange={(e) =>
                          updateSegment(i, {
                            to_location_type: e.target.value as LocationType,
                          })
                        }
                        disabled={busy}
                        aria-label="Тип конечной локации"
                      >
                        {LOCATION_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                      <Input
                        className="flex-1"
                        placeholder="Подпись сегмента (опц.)"
                        value={seg.default_label}
                        onChange={(e) =>
                          updateSegment(i, { default_label: e.target.value })
                        }
                        disabled={busy}
                      />
                      <Input
                        type="number"
                        min={0}
                        step={1}
                        className="w-20"
                        placeholder="Дни"
                        value={seg.default_days ?? ""}
                        onChange={(e) =>
                          updateSegment(i, {
                            default_days: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                        disabled={busy}
                        aria-label="Дней по умолчанию"
                      />
                      {segments.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeSegment(i)}
                          disabled={busy}
                          aria-label={`Удалить сегмент ${seg.sequence_order}`}
                        >
                          <Trash2 size={14} aria-hidden />
                        </Button>
                      )}
                    </div>

                    {/* Optional concrete-location pickers (3.5).
                        Hidden when the org has no locations yet — keeps
                        the dialog usable while the locations directory
                        is empty. */}
                    {locations.length > 0 && (
                      <div
                        className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2"
                        data-testid={`template-segment-${i}-concrete`}
                      >
                        <ConcreteLocationField
                          label="Конкретная локация (откуда)"
                          locations={locations}
                          value={seg.from_location_id}
                          onChange={(v) =>
                            updateSegment(i, { from_location_id: v })
                          }
                          disabled={busy}
                        />
                        <ConcreteLocationField
                          label="Конкретная локация (куда)"
                          locations={locations}
                          value={seg.to_location_id}
                          onChange={(v) =>
                            updateSegment(i, { to_location_id: v })
                          }
                          disabled={busy}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={busy}
          >
            Отмена
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {busy
              ? isEdit
                ? "Сохранение..."
                : "Создание..."
              : isEdit
                ? "Сохранить"
                : "Создать шаблон"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
