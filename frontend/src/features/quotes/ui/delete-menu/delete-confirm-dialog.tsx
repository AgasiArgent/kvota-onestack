"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
import { softDeleteQuote } from "@/entities/quote/mutations";

interface DeleteConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  quoteId: string;
  entityName: string;
}

/**
 * Confirmation dialog for soft-deleting a quote (cascades to spec + deal).
 *
 * Action hierarchy is inverted per ux-complexity.md — the safe "Отмена"
 * action is the primary filled button; the destructive "Удалить" is
 * outlined/destructive to give more visual weight to the escape hatch.
 */
export function DeleteConfirmDialog({
  open,
  onClose,
  quoteId,
  entityName,
}: DeleteConfirmDialogProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await softDeleteQuote(quoteId);
      toast.success(`Квота ${entityName} удалена`);
      onClose();
      router.push("/quotes");
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось удалить квоту"
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleClose() {
    if (submitting) return;
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Удалить квоту {entityName}?</DialogTitle>
          <DialogDescription>
            Будет удалена: квота, спецификация (если есть), сделка (если
            есть). Восстановить можно в разделе «Администрирование →
            Корзина» в течение 365 дней.
          </DialogDescription>
        </DialogHeader>

        <DialogFooter>
          <Button
            variant="outline"
            className="border-destructive text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Удалить
          </Button>
          <Button onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
