"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { TableView } from "@/entities/table-view";
import { createView, updateView } from "@/entities/table-view";

import type { SerializedTableState } from "./types";

export type SaveViewDialogMode =
  | { kind: "create"; initialName?: string }
  | { kind: "rename"; view: TableView };

interface SaveViewDialogProps {
  open: boolean;
  onClose: () => void;
  mode: SaveViewDialogMode;
  tableKey: string;
  userId: string;
  /** Current state to persist — used for create mode. */
  currentState: SerializedTableState;
  /** Existing view names for inline uniqueness validation. */
  existingNames: readonly string[];
  onSaved: (view: TableView) => void;
}

/**
 * Dialog for creating a new view (with current filter state) or renaming
 * an existing one. Inline validation rejects empty and duplicate names
 * before submission.
 */
export function SaveViewDialog({
  open,
  onClose,
  mode,
  tableKey,
  userId,
  currentState,
  existingNames,
  onSaved,
}: SaveViewDialogProps) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Initialize name when dialog opens.
  useEffect(() => {
    if (!open) return;
    if (mode.kind === "create") {
      setName(mode.initialName ?? "");
    } else {
      setName(mode.view.name);
    }
    setError(null);
  }, [open, mode]);

  function validate(trimmedName: string): string | null {
    if (trimmedName.length === 0) return "Введите название";
    if (trimmedName.length > 100) return "Название слишком длинное";

    // Exclude the current view's own name when renaming.
    const blockedNames = new Set(existingNames);
    if (mode.kind === "rename") {
      blockedNames.delete(mode.view.name);
    }
    if (blockedNames.has(trimmedName)) {
      return "Вид с таким названием уже существует";
    }
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    const validationError = validate(trimmed);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      let saved: TableView;
      if (mode.kind === "create") {
        saved = await createView(userId, {
          tableKey,
          name: trimmed,
          filters: currentState.filters,
          sort: currentState.sort,
          visibleColumns: currentState.visibleColumns,
        });
        toast.success(`Вид "${trimmed}" сохранён`);
      } else {
        saved = await updateView(mode.view.id, { name: trimmed });
        toast.success(`Вид переименован в "${trimmed}"`);
      }
      onSaved(saved);
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось сохранить вид";
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const title =
    mode.kind === "create" ? "Сохранить вид" : "Переименовать вид";
  const description =
    mode.kind === "create"
      ? "Название сохранит текущие фильтры, сортировку и видимые колонки."
      : "Новое название для этого сохранённого вида.";
  const submitLabel = mode.kind === "create" ? "Сохранить" : "Переименовать";

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="view-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Название <span className="text-error">*</span>
            </Label>
            <Input
              id="view-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
              placeholder="Например: Мои просроченные КП"
              autoFocus
              disabled={submitting}
              aria-invalid={error !== null}
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={submitting || name.trim().length === 0}
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
