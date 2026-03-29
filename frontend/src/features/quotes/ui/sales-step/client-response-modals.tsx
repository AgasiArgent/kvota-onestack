"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  acceptQuote,
  requestChanges,
  rejectQuote,
  cancelQuote,
} from "@/entities/quote/mutations";
import type { ClientResponseModal } from "./sales-action-bar";

// Match Python backend change_type values (see /quotes/{id}/client-change-request)
const CHANGE_TYPES = [
  { value: "add_item", label: "Добавить/изменить позицию" },
  { value: "logistics", label: "Изменить логистику" },
  { value: "price", label: "Изменить цену/скидку" },
  { value: "full", label: "Полный пересчёт" },
] as const;

// Match Python backend rejection_reason values (see /quotes/{id}/client-rejected)
const DECLINE_REASONS = [
  { value: "price_too_high", label: "Цена слишком высокая" },
  { value: "delivery_time", label: "Сроки не устраивают" },
  { value: "competitor", label: "Выбрали другого поставщика" },
  { value: "project_cancelled", label: "Проект отменён / заморожен" },
  { value: "no_budget", label: "Нет бюджета" },
  { value: "requirements_changed", label: "Изменились требования" },
  { value: "other", label: "Другое" },
] as const;

interface ClientResponseModalsProps {
  quoteId: string;
  idnQuote: string;
  activeModal: ClientResponseModal;
  onClose: () => void;
}

export function ClientResponseModals({
  quoteId,
  idnQuote,
  activeModal,
  onClose,
}: ClientResponseModalsProps) {
  return (
    <>
      <AcceptModal
        open={activeModal === "accept"}
        onClose={onClose}
        quoteId={quoteId}
        idnQuote={idnQuote}
      />
      <ChangesModal
        open={activeModal === "changes"}
        onClose={onClose}
        quoteId={quoteId}
      />
      <DeclineModal
        open={activeModal === "decline"}
        onClose={onClose}
        quoteId={quoteId}
      />
      <CancelModal
        open={activeModal === "cancel"}
        onClose={onClose}
        quoteId={quoteId}
        idnQuote={idnQuote}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Accept Modal
// ---------------------------------------------------------------------------

function AcceptModal({
  open,
  onClose,
  quoteId,
  idnQuote,
}: {
  open: boolean;
  onClose: () => void;
  quoteId: string;
  idnQuote: string;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await acceptQuote(quoteId);
      toast.success("Клиент принял — спецификация заказана");
      onClose();
      router.refresh();
    } catch {
      toast.error("Не удалось обновить статус");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Клиент принимает — заказать спецификацию</DialogTitle>
          <DialogDescription>
            КП {idnQuote} будет переведена на этап оформления спецификации
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-success text-white hover:bg-success/90"
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Подтвердить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Changes Modal
// ---------------------------------------------------------------------------

function ChangesModal({
  open,
  onClose,
  quoteId,
}: {
  open: boolean;
  onClose: () => void;
  quoteId: string;
}) {
  const router = useRouter();
  const [changeType, setChangeType] = useState<string>("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await requestChanges(quoteId, changeType, comment);
      toast.success("Запрос на изменения отправлен");
      setChangeType("");
      setComment("");
      onClose();
      router.refresh();
    } catch {
      toast.error("Не удалось отправить запрос");
    } finally {
      setSubmitting(false);
    }
  }

  function handleClose() {
    setChangeType("");
    setComment("");
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Клиент просит изменения</DialogTitle>
          <DialogDescription>
            Выберите тип изменения и оставьте комментарий
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Тип изменения</legend>
            {CHANGE_TYPES.map((option) => (
              <label
                key={option.value}
                className="flex items-center gap-2 text-sm cursor-pointer"
              >
                <input
                  type="radio"
                  name="change_type"
                  value={option.value}
                  checked={changeType === option.value}
                  onChange={(e) => setChangeType(e.target.value)}
                  className="accent-accent"
                />
                {option.label}
              </label>
            ))}
          </fieldset>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Комментарий</label>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Опишите, что именно хочет клиент"
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleConfirm}
            disabled={!changeType || submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Отправить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Decline Modal
// ---------------------------------------------------------------------------

function DeclineModal({
  open,
  onClose,
  quoteId,
}: {
  open: boolean;
  onClose: () => void;
  quoteId: string;
}) {
  const router = useRouter();
  const [reason, setReason] = useState<string>("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await rejectQuote(quoteId, reason, comment);
      toast.success("КП отмечена как отклонённая");
      setReason("");
      setComment("");
      onClose();
      router.refresh();
    } catch {
      toast.error("Не удалось обновить статус");
    } finally {
      setSubmitting(false);
    }
  }

  function handleClose() {
    setReason("");
    setComment("");
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Клиент отказался</DialogTitle>
          <DialogDescription>
            Укажите причину отказа
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">
              Причина отказа <span className="text-destructive">*</span>
            </label>
            <select
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              <option value="">Выберите причину</option>
              {DECLINE_REASONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Комментарий</label>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Дополнительная информация"
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!reason || submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Подтвердить отказ
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Cancel Modal
// ---------------------------------------------------------------------------

function CancelModal({
  open,
  onClose,
  quoteId,
  idnQuote,
}: {
  open: boolean;
  onClose: () => void;
  quoteId: string;
  idnQuote: string;
}) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await cancelQuote(quoteId);
      toast.success("КП отменена");
      onClose();
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось отменить КП"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Отменить КП</DialogTitle>
          <DialogDescription>
            КП {idnQuote} будет отменена. Это действие необратимо.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Отменить КП
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
