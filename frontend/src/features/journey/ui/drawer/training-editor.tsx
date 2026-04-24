"use client";

/**
 * Training-editor dialog (Task 27).
 *
 * Admin + head_of_* CUD for training steps on a single node. The dialog
 * is the only surface where training pins are created, edited, reordered,
 * or deleted — the regular pin-overlay dialog stays focused on QA pins.
 *
 * Reqs: 5.4 (ordered markdown blocks), 8.2 (training pins require a
 * non-null `training_step_order`), 12.10 (ACL).
 *
 * Reorder semantics: dnd-kit's `SortableContext` drives the visual order;
 * on `dragEnd` we compute the delta via `computeReorderedSteps` and fire
 * sequential `updatePin` calls (one per changed row). Supabase JS has no
 * batched UPDATE primitive — sequential writes are adequate for the
 * N ≤ ~20 typical step count and keep the per-row error handling simple.
 *
 * Visibility is gated by the parent (`training-section.tsx`) via
 * `canEditTraining(userRoles)` before mounting this component. RLS on
 * `journey_pins` is the server-side check.
 */

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Trash2 } from "lucide-react";

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

import {
  createPin,
  deletePin,
  updatePin,
  JOURNEY_QUERY_KEYS,
  type JourneyNodeId,
  type JourneyPin,
} from "@/entities/journey";

import {
  buildTrainingStepPayload,
  classifyTrainingEditorError,
  computeReorderedSteps,
  nextTrainingStepOrder,
  orderTrainingSteps,
} from "./_training-helpers";

interface Props {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly nodeId: JourneyNodeId;
  readonly pins: readonly JourneyPin[];
  readonly userId: string;
}

interface SortableStepRowProps {
  readonly pin: JourneyPin;
  readonly index: number;
  readonly editing: boolean;
  readonly draftExpected: string;
  readonly draftSelector: string;
  readonly onEditStart: () => void;
  readonly onEditCancel: () => void;
  readonly onDraftExpectedChange: (value: string) => void;
  readonly onDraftSelectorChange: (value: string) => void;
  readonly onSave: () => void;
  readonly onDelete: () => void;
  readonly busy: boolean;
}

function SortableStepRow({
  pin,
  index,
  editing,
  draftExpected,
  draftSelector,
  onEditStart,
  onEditCancel,
  onDraftExpectedChange,
  onDraftSelectorChange,
  onSave,
  onDelete,
  busy,
}: SortableStepRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: pin.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      data-testid={`training-step-row-${pin.id}`}
      className={`flex items-start gap-2 rounded-md border p-2 text-xs ${
        isDragging
          ? "border-primary bg-background-subtle"
          : "border-border-light bg-background"
      }`}
    >
      <button
        type="button"
        aria-label="Перетащить"
        className="mt-1 shrink-0 cursor-grab text-text-subtle"
        {...attributes}
        {...listeners}
        disabled={busy}
      >
        <GripVertical size={14} />
      </button>
      <span className="mt-1 w-5 shrink-0 font-mono text-text-subtle">
        {index + 1}.
      </span>
      <div className="flex-1">
        {editing ? (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor={`ed-exp-${pin.id}`}>Описание (markdown)</Label>
            <Textarea
              id={`ed-exp-${pin.id}`}
              value={draftExpected}
              rows={3}
              onChange={(e) => onDraftExpectedChange(e.target.value)}
            />
            <Label htmlFor={`ed-sel-${pin.id}`}>CSS-селектор</Label>
            <Input
              id={`ed-sel-${pin.id}`}
              value={draftSelector}
              onChange={(e) => onDraftSelectorChange(e.target.value)}
              placeholder='[data-testid="save"]'
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={onSave} disabled={busy}>
                Сохранить
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={onEditCancel}
                disabled={busy}
              >
                Отмена
              </Button>
            </div>
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap font-medium text-text">
              {pin.expected_behavior}
            </p>
            <p className="mt-1 break-all font-mono text-text-subtle">
              {pin.selector}
            </p>
            <div className="mt-1 flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={onEditStart}
                disabled={busy}
              >
                Изменить
              </Button>
            </div>
          </>
        )}
      </div>
      <button
        type="button"
        aria-label="Удалить шаг"
        className="shrink-0 rounded-md p-1 text-text-subtle hover:text-destructive"
        onClick={onDelete}
        disabled={busy}
        data-testid={`training-step-delete-${pin.id}`}
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}

export function TrainingEditor({
  open,
  onOpenChange,
  nodeId,
  pins,
  userId,
}: Props) {
  const qc = useQueryClient();

  const orderedSteps = useMemo(() => orderTrainingSteps(pins), [pins]);

  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftExpected, setDraftExpected] = useState("");
  const [draftSelector, setDraftSelector] = useState("");

  const [newExpected, setNewExpected] = useState("");
  const [newSelector, setNewSelector] = useState("");

  // Reset transient state whenever the dialog opens.
  useEffect(() => {
    if (!open) {
      setEditingId(null);
      setDraftExpected("");
      setDraftSelector("");
      setNewExpected("");
      setNewSelector("");
      setBusy(false);
    }
  }, [open]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodeDetail(nodeId) });

  const reportError = (err: unknown) => {
    const info = classifyTrainingEditorError(err);
    toast.error(info.userMessage);
  };

  const onDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const fromIndex = orderedSteps.findIndex((p) => p.id === active.id);
    const toIndex = orderedSteps.findIndex((p) => p.id === over.id);
    const changes = computeReorderedSteps(orderedSteps, fromIndex, toIndex);
    if (changes.length === 0) return;
    setBusy(true);
    try {
      for (const ch of changes) {
        const { error } = await updatePin(ch.id, {
          training_step_order: ch.training_step_order,
        });
        if (error) {
          reportError(error);
          break;
        }
      }
      await invalidate();
    } finally {
      setBusy(false);
    }
  };

  const onEditStart = (pin: JourneyPin) => {
    setEditingId(pin.id);
    setDraftExpected(pin.expected_behavior);
    setDraftSelector(pin.selector);
  };

  const onEditCancel = () => {
    setEditingId(null);
    setDraftExpected("");
    setDraftSelector("");
  };

  const onEditSave = async (pin: JourneyPin) => {
    const trimmedExpected = draftExpected.trim();
    const trimmedSelector = draftSelector.trim();
    if (trimmedExpected.length === 0) {
      toast.error("Описание шага не может быть пустым");
      return;
    }
    if (trimmedSelector.length === 0) {
      toast.error("Селектор не может быть пустым");
      return;
    }
    setBusy(true);
    const { error } = await updatePin(pin.id, {
      expected_behavior: trimmedExpected,
      selector: trimmedSelector,
    });
    setBusy(false);
    if (error) {
      reportError(error);
      return;
    }
    toast.success("Шаг обновлён");
    onEditCancel();
    await invalidate();
  };

  const onDeleteStep = async (pin: JourneyPin) => {
    if (!confirm(`Удалить шаг ${pin.training_step_order ?? ""}?`)) return;
    setBusy(true);
    const { error } = await deletePin(pin.id);
    setBusy(false);
    if (error) {
      reportError(error);
      return;
    }
    toast.success("Шаг удалён");
    await invalidate();
  };

  const onCreateStep = async () => {
    const trimmedExpected = newExpected.trim();
    const trimmedSelector = newSelector.trim();
    if (trimmedExpected.length === 0) {
      toast.error("Описание шага не может быть пустым");
      return;
    }
    if (trimmedSelector.length === 0) {
      toast.error("Селектор не может быть пустым");
      return;
    }
    setBusy(true);
    const payload = buildTrainingStepPayload({
      stepOrder: nextTrainingStepOrder(pins),
      expected_behavior: trimmedExpected,
      selector: trimmedSelector,
      node_id: nodeId,
      created_by: userId,
    });
    const { error } = await createPin(payload);
    setBusy(false);
    if (error) {
      reportError(error);
      return;
    }
    toast.success("Шаг добавлен");
    setNewExpected("");
    setNewSelector("");
    await invalidate();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-xl"
        data-testid="training-editor-dialog"
      >
        <DialogHeader>
          <DialogTitle>Шаги обучения</DialogTitle>
          <DialogDescription>
            Поддерживается markdown. Порядок шагов меняется перетаскиванием.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Steps list */}
          {orderedSteps.length === 0 ? (
            <p className="text-xs text-text-subtle">
              Шаги ещё не добавлены.
            </p>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={onDragEnd}
            >
              <SortableContext
                items={orderedSteps.map((p) => p.id)}
                strategy={verticalListSortingStrategy}
              >
                <ul className="space-y-2">
                  {orderedSteps.map((pin, idx) => (
                    <SortableStepRow
                      key={pin.id}
                      pin={pin}
                      index={idx}
                      editing={editingId === pin.id}
                      draftExpected={
                        editingId === pin.id ? draftExpected : ""
                      }
                      draftSelector={
                        editingId === pin.id ? draftSelector : ""
                      }
                      onEditStart={() => onEditStart(pin)}
                      onEditCancel={onEditCancel}
                      onDraftExpectedChange={setDraftExpected}
                      onDraftSelectorChange={setDraftSelector}
                      onSave={() => onEditSave(pin)}
                      onDelete={() => onDeleteStep(pin)}
                      busy={busy}
                    />
                  ))}
                </ul>
              </SortableContext>
            </DndContext>
          )}

          {/* Add-step form */}
          <div className="flex flex-col gap-1.5 rounded-md border border-dashed border-border-light p-3">
            <Label htmlFor="training-new-expected">
              Новый шаг · описание (markdown)
            </Label>
            <Textarea
              id="training-new-expected"
              value={newExpected}
              rows={3}
              onChange={(e) => setNewExpected(e.target.value)}
              placeholder="Нажмите **Сохранить** и подтвердите в модалке"
            />
            <Label htmlFor="training-new-selector">CSS-селектор</Label>
            <Input
              id="training-new-selector"
              value={newSelector}
              onChange={(e) => setNewSelector(e.target.value)}
              placeholder='[data-testid="save"]'
            />
            <div>
              <Button
                onClick={onCreateStep}
                disabled={busy}
                size="sm"
                data-testid="training-step-add"
              >
                + Добавить шаг
              </Button>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={busy}
          >
            Закрыть
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
