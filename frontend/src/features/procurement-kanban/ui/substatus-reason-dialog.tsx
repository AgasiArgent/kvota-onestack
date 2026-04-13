"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  SUBSTATUS_LABELS_RU,
  type ProcurementSubstatus,
} from "@/shared/lib/workflow-substates";

/**
 * Pure helper: returns true when the dialog's submit button should be enabled.
 * Exported for unit testing without a DOM environment.
 */
export function canSubmitReason(reason: string, submitting: boolean): boolean {
  return reason.trim().length > 0 && !submitting;
}

export interface SubstatusReasonDialogProps {
  open: boolean;
  fromSubstatus: ProcurementSubstatus | null;
  toSubstatus: ProcurementSubstatus | null;
  quoteIdn: string | null;
  onConfirm: (reason: string) => void | Promise<void>;
  onCancel: () => void;
  submitting?: boolean;
}

/**
 * Confirmation dialog shown when a user drags a card backward on the kanban.
 * A non-empty reason is required (trimmed). Cancel rolls back the optimistic
 * drag in the parent.
 */
export function SubstatusReasonDialog(props: SubstatusReasonDialogProps) {
  const { open, onCancel, submitting = false, quoteIdn } = props;

  // Remount the form whenever the dialog opens for a new transition — this
  // resets local reason state without an effect+setState.
  const formKey = open
    ? `${quoteIdn ?? ""}-${props.fromSubstatus ?? ""}-${props.toSubstatus ?? ""}`
    : "closed";

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen && !submitting) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Возврат на предыдущий этап</DialogTitle>
          <DialogDescription>
            {quoteIdn ? `${quoteIdn}: ` : ""}
            {props.fromSubstatus
              ? SUBSTATUS_LABELS_RU[props.fromSubstatus]
              : ""}
            {" → "}
            {props.toSubstatus ? SUBSTATUS_LABELS_RU[props.toSubstatus] : ""}
          </DialogDescription>
        </DialogHeader>

        <ReasonForm
          key={formKey}
          onConfirm={props.onConfirm}
          onCancel={onCancel}
          submitting={submitting}
        />
      </DialogContent>
    </Dialog>
  );
}

interface ReasonFormProps {
  onConfirm: (reason: string) => void | Promise<void>;
  onCancel: () => void;
  submitting: boolean;
}

function ReasonForm({ onConfirm, onCancel, submitting }: ReasonFormProps) {
  const [reason, setReason] = useState("");
  const canSubmit = canSubmitReason(reason, submitting);

  return (
    <>
      <div className="flex flex-col gap-2">
        <Label htmlFor="substatus-reason">Причина возврата</Label>
        <Textarea
          id="substatus-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Опишите, почему нужно вернуть заявку на предыдущий этап"
          rows={4}
          disabled={submitting}
          autoFocus
        />
      </div>

      <DialogFooter>
        <Button
          variant="outline"
          onClick={onCancel}
          disabled={submitting}
          type="button"
        >
          Отмена
        </Button>
        <Button
          onClick={() => {
            if (canSubmit) void onConfirm(reason.trim());
          }}
          disabled={!canSubmit}
          type="button"
        >
          {submitting ? "Сохраняем…" : "Подтвердить"}
        </Button>
      </DialogFooter>
    </>
  );
}
