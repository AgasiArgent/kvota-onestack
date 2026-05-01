"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { extractErrorMessage } from "@/shared/lib/errors";
import { addCargoPlace } from "@/entities/quote/mutations";

/**
 * Small dialog for adding a single cargo place to an invoice. Opened from
 * the «+ Добавить место» button in the InvoiceCard's cargo-places editor.
 *
 * All four fields are required (> 0). Replaces the old placeholder-default
 * insert pattern — the user enters real values before persistence so we
 * never write 1mm/100mm "garbage" placeholder rows.
 */

export interface AddCargoPlaceFormState {
  weight_kg: string;
  length_mm: string;
  width_mm: string;
  height_mm: string;
}

export function isValidAddCargoPlaceForm(
  state: AddCargoPlaceFormState
): boolean {
  const w = parseFloat(state.weight_kg);
  const l = parseInt(state.length_mm, 10);
  const wd = parseInt(state.width_mm, 10);
  const h = parseInt(state.height_mm, 10);
  return (
    Number.isFinite(w) &&
    w > 0 &&
    Number.isFinite(l) &&
    l > 0 &&
    Number.isFinite(wd) &&
    wd > 0 &&
    Number.isFinite(h) &&
    h > 0
  );
}

const EMPTY: AddCargoPlaceFormState = {
  weight_kg: "",
  length_mm: "",
  width_mm: "",
  height_mm: "",
};

interface AddCargoPlaceDialogProps {
  open: boolean;
  onClose: () => void;
  invoiceId: string;
  /** Called after a successful add — typically to refetch + close. */
  onAdded: () => void;
}

export function AddCargoPlaceDialog({
  open,
  onClose,
  invoiceId,
  onAdded,
}: AddCargoPlaceDialogProps) {
  const [state, setState] = useState<AddCargoPlaceFormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setState(EMPTY);
  }, [open]);

  function setField<K extends keyof AddCargoPlaceFormState>(
    field: K,
    value: string
  ) {
    setState((prev) => ({ ...prev, [field]: value }));
  }

  function handleClose() {
    if (submitting) return;
    onClose();
  }

  async function handleSubmit() {
    if (!isValidAddCargoPlaceForm(state)) return;
    setSubmitting(true);
    try {
      await addCargoPlace(invoiceId, {
        weight_kg: parseFloat(state.weight_kg),
        length_mm: parseInt(state.length_mm, 10),
        width_mm: parseInt(state.width_mm, 10),
        height_mm: parseInt(state.height_mm, 10),
      });
      toast.success("Место добавлено");
      onAdded();
    } catch (err) {
      console.error("[add-cargo-place-dialog] submit failed:", err);
      toast.error(
        extractErrorMessage(err) ?? "Не удалось добавить место"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting && isValidAddCargoPlaceForm(state);

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleClose()}>
      <DialogContent className="sm:max-w-md z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Новое грузовое место</DialogTitle>
          <DialogDescription>
            Укажите вес и габариты места. Все поля обязательны и должны быть
            больше нуля.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-2">
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">
              Вес, кг <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              autoFocus
              placeholder="Вес"
              value={state.weight_kg}
              onChange={(e) => setField("weight_kg", e.target.value)}
              className="h-8 text-sm tabular-nums"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">
              Длина, мм <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="1"
              min="0"
              placeholder="Длина"
              value={state.length_mm}
              onChange={(e) => setField("length_mm", e.target.value)}
              className="h-8 text-sm tabular-nums"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">
              Ширина, мм <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="1"
              min="0"
              placeholder="Ширина"
              value={state.width_mm}
              onChange={(e) => setField("width_mm", e.target.value)}
              className="h-8 text-sm tabular-nums"
            />
          </div>
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">
              Высота, мм <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="1"
              min="0"
              placeholder="Высота"
              value={state.height_mm}
              onChange={(e) => setField("height_mm", e.target.value)}
              className="h-8 text-sm tabular-nums"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Добавить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
