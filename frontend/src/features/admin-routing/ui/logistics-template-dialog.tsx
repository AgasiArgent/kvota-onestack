"use client";

import { useState } from "react";
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
import type { LocationType } from "@/entities/location/ui/location-chip";

/**
 * LogisticsTemplateDialog — creation form for a new logistics route template.
 *
 * The template is a typed scaffold: each segment is a (from_location_type,
 * to_location_type) pair with optional default label/days. Logisticians
 * instantiate it by picking concrete locations in the Route Constructor.
 */

interface TemplateSegmentForm {
  sequence_order: number;
  from_location_type: LocationType;
  to_location_type: LocationType;
  default_label: string;
  default_days: number | null;
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
}

const LOCATION_TYPES: Array<{ value: LocationType; label: string }> = [
  { value: "supplier", label: "Поставщик" },
  { value: "hub", label: "Хаб" },
  { value: "customs", label: "Таможня" },
  { value: "own_warehouse", label: "Склад" },
  { value: "client", label: "Клиент" },
];

function emptySegment(sequence_order: number): TemplateSegmentForm {
  return {
    sequence_order,
    from_location_type: "supplier",
    to_location_type: "hub",
    default_label: "",
    default_days: null,
  };
}

export function LogisticsTemplateDialog({
  open,
  onOpenChange,
  onSubmit,
  busy,
}: Props) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [segments, setSegments] = useState<TemplateSegmentForm[]>([
    emptySegment(1),
  ]);

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
          <DialogTitle>Новый шаблон маршрута</DialogTitle>
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
                    className="flex items-center gap-2 rounded-md border border-border-light bg-card px-3 py-2"
                  >
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
            {busy ? "Создание..." : "Создать шаблон"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
