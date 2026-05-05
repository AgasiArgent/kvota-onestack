"use client";

import { useState } from "react";
import { ArrowDown } from "lucide-react";
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
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import type { LocationOption, LocationType } from "@/entities/location";

const LOCATION_TYPE_LABEL: Record<LocationType, string> = {
  supplier: "Поставщики",
  hub: "Хабы",
  customs: "Таможня",
  own_warehouse: "Склады",
  client: "Клиенты",
};

interface AddSegmentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  locations: LocationOption[];
  /** Resolves on success (dialog will close). Throws on failure (dialog stays open, caller toasts). */
  onSubmit: (input: {
    from_location_id: string;
    to_location_id: string;
    label: string | null;
  }) => Promise<void>;
}

function formatLocationLabel(loc: LocationOption): string {
  if (loc.city && loc.country) return `${loc.country} · ${loc.city}`;
  return loc.country || "—";
}

/**
 * AddSegmentDialog — modal for creating a new route segment with required
 * from/to locations. The Python API + DB schema both require non-null
 * locations on every segment (kvota.logistics_route_segments columns are
 * NOT NULL); previously the "+" button POSTed nulls and surfaced a 500.
 *
 * The label field is optional — it can also be edited later via the
 * SegmentDetailsPanel together with carrier/cost/transit days.
 */
export function AddSegmentDialog({
  open,
  onOpenChange,
  locations,
  onSubmit,
}: AddSegmentDialogProps) {
  const [fromId, setFromId] = useState<string | null>(null);
  const [toId, setToId] = useState<string | null>(null);
  const [label, setLabel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function handleOpenChange(next: boolean) {
    // Block close while a submit is in flight — otherwise Esc/backdrop close
    // would orphan the in-flight POST: dialog vanishes, but if the request
    // errors the toast appears with no dialog to retry from.
    if (!next && submitting) return;
    if (!next) {
      setFromId(null);
      setToId(null);
      setLabel("");
    }
    onOpenChange(next);
  }

  async function handleSubmit() {
    if (!fromId || !toId || fromId === toId) return;
    setSubmitting(true);
    try {
      await onSubmit({
        from_location_id: fromId,
        to_location_id: toId,
        label: label.trim() || null,
      });
      handleOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  }

  const sameLocation = !!fromId && !!toId && fromId === toId;
  const canSubmit = !!fromId && !!toId && !sameLocation && !submitting;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Добавить сегмент маршрута</DialogTitle>
          <DialogDescription>
            Выберите начальную и конечную локации. Стоимость, перевозчик и срок можно заполнить после создания.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-3 pb-2">
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium text-text-muted">
              Откуда
            </Label>
            <SearchableCombobox
              ariaLabel="Локация отправления"
              value={fromId}
              onChange={setFromId}
              items={locations}
              getLabel={formatLocationLabel}
              getSecondary={(loc) => LOCATION_TYPE_LABEL[loc.type]}
              getSearchableExtras={(loc) => [LOCATION_TYPE_LABEL[loc.type], loc.city ?? ""]}
              placeholder="Выберите локацию…"
              emptyMessage="Нет локаций — создайте их в «Справочниках»."
            />
          </div>

          <div className="flex justify-center text-text-subtle">
            <ArrowDown size={16} strokeWidth={2} aria-hidden />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-medium text-text-muted">
              Куда
            </Label>
            <SearchableCombobox
              ariaLabel="Локация назначения"
              value={toId}
              onChange={setToId}
              items={locations}
              getLabel={formatLocationLabel}
              getSecondary={(loc) => LOCATION_TYPE_LABEL[loc.type]}
              getSearchableExtras={(loc) => [LOCATION_TYPE_LABEL[loc.type], loc.city ?? ""]}
              placeholder="Выберите локацию…"
              emptyMessage="Нет локаций — создайте их в «Справочниках»."
              invalid={sameLocation}
            />
            {sameLocation && (
              <p className="text-xs text-destructive">Откуда и куда не могут совпадать.</p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="add-seg-label" className="text-xs font-medium text-text-muted">
              Название (опционально)
            </Label>
            <Input
              id="add-seg-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Например: морем до Шанхая"
              maxLength={120}
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? "Создание…" : "Создать"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
