"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Loader2, Trash2 } from "lucide-react";
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
import { Label } from "@/components/ui/label";

import type { TableView } from "@/entities/table-view";
import { createView, deleteView, updateView } from "@/entities/table-view";

export interface AvailableColumn {
  /** Stable logical key (stored in `visible_columns`). */
  key: string;
  /** Russian human-readable label. */
  label: string;
}

interface TableViewsSettingsDialogProps {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  /** When editing, the existing view. When undefined, the dialog creates a new view. */
  initial?: TableView;
  tableKey: string;
  availableColumns: readonly AvailableColumn[];
  /** Acting user id — used as `user_id` on INSERT and for role checks. */
  userId: string;
  /** Acting user's organization id — required for shared-view role check. */
  orgId: string;
  /** True when the acting user can create/edit shared views. */
  canCreateShared: boolean;
  /** Called after a successful create/update/delete so the parent can refresh. */
  onSaved: () => void;
}

/**
 * Modal for creating or editing a user_table_views row for the customs
 * registry. Offers:
 *  - Name input (required, 1-100 chars).
 *  - Drag-to-reorder checkbox list of available columns.
 *  - Optional "Общее представление" toggle (only if `canCreateShared`).
 *  - Delete button when editing.
 *
 * Save creates or updates via the entity mutations. Role enforcement for
 * shared views is layered: this component gates the checkbox, the mutation
 * double-checks, and RLS is the final authority.
 */
export function TableViewsSettingsDialog({
  open,
  onOpenChange,
  initial,
  tableKey,
  availableColumns,
  userId,
  orgId,
  canCreateShared,
  onSaved,
}: TableViewsSettingsDialogProps) {
  const [name, setName] = useState("");
  const [orderedKeys, setOrderedKeys] = useState<string[]>([]);
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [isShared, setIsShared] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const allKeys = useMemo(
    () => availableColumns.map((c) => c.key),
    [availableColumns]
  );
  const columnByKey = useMemo(() => {
    const m = new Map<string, AvailableColumn>();
    for (const c of availableColumns) m.set(c.key, c);
    return m;
  }, [availableColumns]);

  // Initialize state whenever the dialog opens or its initial target changes.
  useEffect(() => {
    if (!open) return;
    if (initial) {
      setName(initial.name);
      // Use the saved order but append any new columns added to the registry
      // since the view was saved (so the user can toggle them on).
      const saved = initial.visibleColumns.filter((k) => columnByKey.has(k));
      const missing = allKeys.filter((k) => !saved.includes(k));
      setOrderedKeys([...saved, ...missing]);
      setVisible(new Set(saved));
      setIsShared(initial.isShared);
    } else {
      setName("");
      setOrderedKeys([...allKeys]);
      setVisible(new Set(allKeys));
      setIsShared(false);
    }
    setError(null);
  }, [open, initial, allKeys, columnByKey]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = orderedKeys.indexOf(String(active.id));
    const newIndex = orderedKeys.indexOf(String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    setOrderedKeys((prev) => arrayMove(prev, oldIndex, newIndex));
  }

  function toggleVisible(key: string, next: boolean) {
    setVisible((prev) => {
      const copy = new Set(prev);
      if (next) copy.add(key);
      else copy.delete(key);
      return copy;
    });
  }

  async function handleSave() {
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setError("Введите название");
      return;
    }
    if (trimmed.length > 100) {
      setError("Название слишком длинное");
      return;
    }
    // Persist only the visible keys, in the current drag order.
    const visibleOrdered = orderedKeys.filter((k) => visible.has(k));
    if (visibleOrdered.length === 0) {
      setError("Выберите хотя бы одну колонку");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      if (initial) {
        await updateView(
          initial.id,
          {
            name: trimmed,
            visibleColumns: visibleOrdered,
          },
          { existing: initial, actingUserId: userId, orgId }
        );
        toast.success(`Вид "${trimmed}" сохранён`);
      } else {
        await createView(
          userId,
          {
            tableKey,
            name: trimmed,
            filters: {},
            sort: null,
            visibleColumns: visibleOrdered,
            isShared: isShared && canCreateShared,
          },
          orgId
        );
        toast.success(`Вид "${trimmed}" создан`);
      }
      onSaved();
      onOpenChange(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось сохранить";
      setError(message);
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!initial) return;
    setDeleting(true);
    try {
      await deleteView(initial.id, {
        existing: initial,
        actingUserId: userId,
        orgId,
      });
      toast.success(`Вид "${initial.name}" удалён`);
      onSaved();
      onOpenChange(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось удалить";
      setError(message);
      toast.error(message);
    } finally {
      setDeleting(false);
    }
  }

  const title = initial ? "Настройка представления" : "Новое представление";
  const description = initial
    ? "Отредактируйте название, видимые колонки и порядок."
    : "Сохраните текущий набор и порядок колонок под новым именем.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label
              htmlFor="view-name"
              className="text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Название <span className="text-destructive">*</span>
            </Label>
            <Input
              id="view-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError(null);
              }}
              placeholder="Например: Полный вид"
              autoFocus
              disabled={submitting || deleting}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Колонки
            </Label>
            <p className="text-xs text-muted-foreground">
              Отметьте видимые колонки и перетащите, чтобы изменить порядок.
            </p>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={orderedKeys}
                strategy={verticalListSortingStrategy}
              >
                <ul className="flex flex-col gap-1 rounded-md border border-border bg-card p-1 max-h-64 overflow-y-auto">
                  {orderedKeys.map((key) => {
                    const col = columnByKey.get(key);
                    if (!col) return null;
                    return (
                      <SortableColumnRow
                        key={key}
                        columnKey={key}
                        label={col.label}
                        checked={visible.has(key)}
                        onCheckedChange={(next) => toggleVisible(key, next)}
                        disabled={submitting || deleting}
                      />
                    );
                  })}
                </ul>
              </SortableContext>
            </DndContext>
          </div>

          {canCreateShared && !initial && (
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={isShared}
                onCheckedChange={(next) => setIsShared(next === true)}
                disabled={submitting}
              />
              <span>Общее представление (для всей организации)</span>
            </label>
          )}

          {error && (
            <p className="text-xs text-destructive" role="alert">
              {error}
            </p>
          )}
        </div>

        <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
          <div>
            {initial && (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                disabled={submitting || deleting}
              >
                {deleting ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Trash2 size={14} />
                )}
                Удалить
              </Button>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting || deleting}
            >
              Отмена
            </Button>
            <Button
              type="button"
              onClick={handleSave}
              disabled={submitting || deleting || name.trim().length === 0}
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Сохранить
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface SortableColumnRowProps {
  columnKey: string;
  label: string;
  checked: boolean;
  onCheckedChange: (next: boolean) => void;
  disabled?: boolean;
}

function SortableColumnRow({
  columnKey,
  label,
  checked,
  onCheckedChange,
  disabled,
}: SortableColumnRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: columnKey, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 rounded-sm px-2 py-1 hover:bg-muted/50"
    >
      <button
        type="button"
        {...attributes}
        {...listeners}
        aria-label="Перетащить"
        className="flex size-6 shrink-0 cursor-grab items-center justify-center rounded-sm text-muted-foreground hover:bg-muted active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-40"
        disabled={disabled}
      >
        <GripVertical size={14} strokeWidth={2} aria-hidden />
      </button>
      <Checkbox
        checked={checked}
        onCheckedChange={(next) => onCheckedChange(next === true)}
        disabled={disabled}
      />
      <span className="text-sm truncate">{label}</span>
    </li>
  );
}
