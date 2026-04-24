"use client";

/**
 * Pin-creation dialog (Task 21).
 *
 * Open via "+ Добавить пин" in the drawer's pin-list section. Accepts either
 * a manually-typed CSS selector or a selector picked via the DOM picker
 * (Req 8.5). Enforces Req 8.1 (field shape) and Req 8.2 (training mode
 * requires training_step_order).
 *
 * The visible copy is Russian — users are Russian-speaking sales / QA staff.
 *
 * Caller (`pin-list-section.tsx`) gates visibility on `canCreatePin` before
 * mounting this component; the dialog itself does not re-check roles. RLS on
 * `journey_pins` denies INSERT for non-writers, and
 * `classifyPinCreateError` surfaces that as a toast (Req 8.1 + 12.6).
 */

import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";

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
  JOURNEY_QUERY_KEYS,
  type JourneyNodeId,
  type PinMode,
} from "@/entities/journey";

import {
  EMPTY_PIN_FORM,
  buildPinPayload,
  classifyPinCreateError,
  validatePinForm,
  type PinFormValues,
} from "./_pin-helpers";
import { DomPicker } from "./dom-picker";

interface Props {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly nodeId: JourneyNodeId;
  readonly nodeRoute: string;
  readonly userId: string;
}

export function PinCreator({
  open,
  onOpenChange,
  nodeId,
  nodeRoute,
  userId,
}: Props) {
  const qc = useQueryClient();
  const [form, setForm] = useState<PinFormValues>(EMPTY_PIN_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  const { valid, errors } = validatePinForm(form);

  const reset = () => {
    setForm(EMPTY_PIN_FORM);
    setPickerOpen(false);
  };

  const onClose = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const onSubmit = async () => {
    if (!valid || submitting) return;
    setSubmitting(true);
    const payload = buildPinPayload({
      form,
      node_id: nodeId,
      created_by: userId,
    });
    const { error } = await createPin(payload);
    setSubmitting(false);
    if (error) {
      const info = classifyPinCreateError(error);
      toast.error(info.userMessage);
      return;
    }
    toast.success("Пин создан");
    qc.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodeDetail(nodeId) });
    reset();
    onOpenChange(false);
  };

  const update = <K extends keyof PinFormValues>(
    key: K,
    value: PinFormValues[K],
  ) => setForm((f) => ({ ...f, [key]: value }));

  const onPicked = (selector: string) => {
    update("selector", selector);
    setPickerOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent
        className="sm:max-w-lg"
        data-testid="pin-creator-dialog"
      >
        <DialogHeader>
          <DialogTitle>Новый пин</DialogTitle>
          <DialogDescription>
            QA-пин закрепляет ожидаемое поведение на элементе экрана. Обучающий
            пин — шаг онбординга.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 py-2">
          {/* Mode toggle */}
          <div className="flex flex-col gap-1.5">
            <Label>Режим</Label>
            <div className="inline-flex rounded-md border border-border-light p-0.5 w-fit">
              {(["qa", "training"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  data-testid={`pin-mode-${m}`}
                  onClick={() => update("mode", m as PinMode)}
                  className={`px-3 py-1 text-xs rounded-sm ${
                    form.mode === m
                      ? "bg-primary text-white"
                      : "text-text-subtle hover:bg-background"
                  }`}
                >
                  {m === "qa" ? "QA" : "Обучение"}
                </button>
              ))}
            </div>
          </div>

          {/* Selector */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pin-selector">CSS-селектор *</Label>
            <div className="flex gap-2">
              <Input
                id="pin-selector"
                value={form.selector}
                onChange={(e) => update("selector", e.target.value)}
                placeholder='[data-testid="save-button"]'
                className={errors.selector ? "border-error" : undefined}
                autoFocus
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => setPickerOpen(true)}
                disabled={submitting}
                data-testid="pin-picker-open"
              >
                Выбрать элемент
              </Button>
            </div>
            {errors.selector && (
              <p className="text-xs text-error">{errors.selector}</p>
            )}
          </div>

          {/* Expected behavior */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pin-expected">Ожидаемое поведение *</Label>
            <Textarea
              id="pin-expected"
              value={form.expected_behavior}
              onChange={(e) => update("expected_behavior", e.target.value)}
              rows={3}
              placeholder="Кнопка сохраняет форму и закрывает модалку"
              className={errors.expected_behavior ? "border-error" : undefined}
            />
            {errors.expected_behavior && (
              <p className="text-xs text-error">{errors.expected_behavior}</p>
            )}
          </div>

          {/* Training step order (training mode only) */}
          {form.mode === "training" && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pin-step-order">Порядок шага *</Label>
              <Input
                id="pin-step-order"
                type="number"
                min={1}
                value={form.training_step_order ?? ""}
                onChange={(e) => {
                  const raw = e.target.value;
                  update(
                    "training_step_order",
                    raw === "" ? null : Number(raw),
                  );
                }}
                className={
                  errors.training_step_order ? "border-error" : undefined
                }
              />
              {errors.training_step_order && (
                <p className="text-xs text-error">
                  {errors.training_step_order}
                </p>
              )}
            </div>
          )}

          {/* Linked story ref (optional) */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pin-story-ref">Связанная история</Label>
            <Input
              id="pin-story-ref"
              value={form.linked_story_ref ?? ""}
              onChange={(e) =>
                update(
                  "linked_story_ref",
                  e.target.value.trim().length === 0 ? null : e.target.value,
                )
              }
              placeholder="phase-5b#3"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onClose(false)}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button
            onClick={onSubmit}
            disabled={!valid || submitting}
            data-testid="pin-create-submit"
          >
            {submitting ? "Создание…" : "Создать"}
          </Button>
        </DialogFooter>

        {pickerOpen && (
          <DomPicker
            targetRoute={nodeRoute}
            onPick={onPicked}
            onCancel={() => setPickerOpen(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
