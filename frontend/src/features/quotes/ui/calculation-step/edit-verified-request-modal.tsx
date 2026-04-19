"use client";

/**
 * EditVerifiedRequestModal — Phase 5b Task 12.
 *
 * When a procurement user attempts to edit an invoice with verified_at
 * set, this modal intercepts the save and converts it into an approval
 * request to head_of_procurement. The diff and the user's reason are
 * stored in kvota.approvals.modifications; on approval, the diff is
 * applied atomically to the invoice.
 *
 * Ready to be wired into any existing invoice edit flow via:
 *   1. Detect invoice.verified_at IS NOT NULL
 *   2. Build proposed_changes as {field: {old, new}}
 *   3. Render <EditVerifiedRequestModal ... />
 *   4. Keep the modal open until onClose; on success call router.refresh()
 *
 * The modal is intentionally decoupled from a specific edit UI so it
 * can be integrated where/when the procurement Next.js migration
 * reaches the invoice-edit screen.
 */

import { useState } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";

export interface ProposedFieldChange {
  /** Current value — displayed as "было" for context. */
  old: unknown;
  /** Proposed value — displayed as "станет". */
  new: unknown;
}

export interface EditVerifiedRequestModalProps {
  /** Invoice to edit. Must have verified_at NOT NULL — modal assumes caller checked. */
  invoice: { id: string; invoice_number: string };
  /** Field-level diff. Empty object → modal refuses to open (nothing to request). */
  proposedChanges: Record<string, ProposedFieldChange>;
  /** Modal visibility. Controlled by parent. */
  open: boolean;
  /** Called when modal should close (cancel button, X, success, etc). */
  onClose: () => void;
  /** Optional: called after a successful request submission. Parent can
      use this to refresh the UI or close a parent dialog. */
  onSuccess?: () => void;
}

const MIN_REASON_LENGTH = 10;

export function EditVerifiedRequestModal({
  invoice,
  proposedChanges,
  open,
  onClose,
  onSuccess,
}: EditVerifiedRequestModalProps) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fields = Object.entries(proposedChanges);
  const hasChanges = fields.length > 0;
  const reasonValid = reason.trim().length >= MIN_REASON_LENGTH;
  const canSubmit = hasChanges && reasonValid && !submitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const { createClient } = await import("@/shared/lib/supabase/client");
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();

      const res = await fetch(
        `/api/invoices/${invoice.id}/procurement-unlock-request`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(session?.access_token
              ? { Authorization: `Bearer ${session.access_token}` }
              : {}),
          },
          body: JSON.stringify({
            proposed_changes: proposedChanges,
            reason: reason.trim(),
          }),
        }
      );

      const payload = await res.json();

      if (!res.ok || !payload.success) {
        const code: string | undefined = payload.error?.code;
        const message: string = payload.error?.message || "Не удалось создать заявку";
        if (code === "INVOICE_NOT_VERIFIED") {
          toast.error(
            "Инвойс не в верифицированном состоянии — редактируйте напрямую"
          );
        } else if (code === "VALIDATION_ERROR") {
          toast.error(`Ошибка валидации: ${message}`);
        } else {
          toast.error(message);
        }
        return;
      }

      toast.success("Заявка на редактирование отправлена head_of_procurement");
      setReason("");
      onSuccess?.();
      onClose();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Сетевая ошибка");
    } finally {
      setSubmitting(false);
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next && !submitting) {
      onClose();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle size={18} className="text-amber-500" />
            Требуется согласование
          </DialogTitle>
          <DialogDescription>
            Инвойс <span className="font-mono">{invoice.invoice_number}</span>{" "}
            был верифицирован. Прямые изменения невозможны — отправьте заявку
            на согласование head_of_procurement.
          </DialogDescription>
        </DialogHeader>

        {!hasChanges ? (
          <p className="text-sm text-muted-foreground py-4">
            Нет предложенных изменений.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="overflow-x-auto border border-border rounded-md">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/30 text-left text-muted-foreground">
                    <th className="py-2 px-3 font-medium">Поле</th>
                    <th className="py-2 px-3 font-medium">Было</th>
                    <th className="py-2 px-3 font-medium">Станет</th>
                  </tr>
                </thead>
                <tbody>
                  {fields.map(([fieldName, change]) => (
                    <tr
                      key={fieldName}
                      className="border-t border-border/60"
                    >
                      <td className="py-2 px-3 font-mono text-xs text-muted-foreground">
                        {fieldName}
                      </td>
                      <td className="py-2 px-3">{formatValue(change.old)}</td>
                      <td className="py-2 px-3 font-medium">
                        {formatValue(change.new)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <label
                htmlFor="edit-verified-reason"
                className="text-sm font-medium block mb-1.5"
              >
                Обоснование
                <span className="text-muted-foreground font-normal">
                  {" "}
                  (минимум {MIN_REASON_LENGTH} символов)
                </span>
              </label>
              <Textarea
                id="edit-verified-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Опишите, почему нужно изменить верифицированный инвойс (например: поставщик изменил условия отгрузки после верификации)"
                rows={3}
                disabled={submitting}
              />
              {reason.length > 0 && !reasonValid && (
                <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                  Ещё {MIN_REASON_LENGTH - reason.trim().length} символов
                </p>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={onClose}
            disabled={submitting}
          >
            Отмена
          </Button>
          <Button onClick={handleSubmit} disabled={!canSubmit}>
            {submitting ? (
              <>
                <Loader2 size={14} className="animate-spin mr-1" />
                Отправка...
              </>
            ) : (
              "Отправить на согласование"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "да" : "нет";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
