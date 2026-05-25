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

/**
 * Pure helper: returns true when the dialog's submit button should be enabled.
 * Exported for unit testing without a DOM environment. Mirrors the
 * canSubmitReason helper in substatus-reason-dialog.tsx so the two dialogs
 * stay behaviorally aligned.
 */
export function canSubmitPauseReason(
  reason: string,
  submitting: boolean
): boolean {
  return reason.trim().length > 0 && !submitting;
}

export interface PauseReasonDialogProps {
  open: boolean;
  quoteIdn: string | null;
  /**
   * Brand of the (quote, brand) card being paused. `""` → unbranded; `null` →
   * dialog closed / not applicable.
   */
  brand: string | null;
  onConfirm: (reason: string) => void | Promise<void>;
  onCancel: () => void;
  submitting?: boolean;
}

/**
 * Pause-reason dialog shown when a user drags a (quote, brand) card INTO the
 * «На паузе» column on the procurement kanban. Reason is mandatory
 * (non-empty after trim) per Testing 2 row 74 — without it the user can't
 * pause the card. Cancel rolls back the optimistic drag in the parent.
 *
 * Visually distinct from SubstatusReasonDialog (which is for backward
 * transitions): the title speaks specifically about pausing, and the
 * placeholder reflects pause semantics («Поставщик не отвечает» etc.).
 */
export function PauseReasonDialog(props: PauseReasonDialogProps) {
  const { open, onCancel, submitting = false, quoteIdn, brand } = props;

  // Remount the form whenever the dialog opens for a new card — this resets
  // local reason state without an effect+setState.
  const formKey = open ? `${quoteIdn ?? ""}-${brand ?? ""}` : "closed";

  const brandLabel =
    brand === null ? "" : brand === "" ? " (без бренда)" : ` (${brand})`;

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen && !submitting) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Поставить на паузу</DialogTitle>
          <DialogDescription>
            {quoteIdn
              ? `${quoteIdn}${brandLabel}: укажите причину постановки на паузу.`
              : "Укажите причину постановки на паузу."}
          </DialogDescription>
        </DialogHeader>

        <PauseForm
          key={formKey}
          onConfirm={props.onConfirm}
          onCancel={onCancel}
          submitting={submitting}
        />
      </DialogContent>
    </Dialog>
  );
}

interface PauseFormProps {
  onConfirm: (reason: string) => void | Promise<void>;
  onCancel: () => void;
  submitting: boolean;
}

function PauseForm({ onConfirm, onCancel, submitting }: PauseFormProps) {
  const [reason, setReason] = useState("");
  const canSubmit = canSubmitPauseReason(reason, submitting);

  return (
    <>
      <div className="flex flex-col gap-2">
        <Label htmlFor="pause-reason">Причина постановки на паузу</Label>
        <Textarea
          id="pause-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Например: Поставщик не отвечает, ждём подтверждения цены"
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
          {submitting ? "Сохраняем…" : "Поставить на паузу"}
        </Button>
      </DialogFooter>
    </>
  );
}
