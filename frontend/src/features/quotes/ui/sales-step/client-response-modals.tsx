"use client";

import { useState } from "react";
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
import type { ClientResponseModal } from "./sales-action-bar";

const CHANGE_TYPES = [
  { value: "change_quantity", label: "Изменить количество" },
  { value: "change_items", label: "Изменить позиции" },
  { value: "request_discount", label: "Запросить скидку" },
] as const;

const DECLINE_REASONS = [
  { value: "price_higher", label: "Цена выше конкурентов" },
  { value: "deadlines", label: "Сроки не устраивают" },
  { value: "lost_tender", label: "Проиграли тендер" },
  { value: "client_cancelled", label: "Клиент отменил закупку" },
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
  function handleConfirm() {
    console.log("Accept quote:", quoteId);
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Клиент принимает</DialogTitle>
          <DialogDescription>
            КП {idnQuote} будет переведена в статус &laquo;Принято&raquo;
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Отмена
          </Button>
          <Button
            className="bg-success text-white hover:bg-success/90"
            onClick={handleConfirm}
          >
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
  const [changeType, setChangeType] = useState<string>("");
  const [comment, setComment] = useState("");

  function handleConfirm() {
    console.log("Changes requested:", { quoteId, changeType, comment });
    setChangeType("");
    setComment("");
    onClose();
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
          <Button variant="outline" onClick={handleClose}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleConfirm}
            disabled={!changeType}
          >
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
  const [reason, setReason] = useState<string>("");
  const [comment, setComment] = useState("");

  function handleConfirm() {
    console.log("Quote declined:", { quoteId, reason, comment });
    setReason("");
    setComment("");
    onClose();
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
          <Button variant="outline" onClick={handleClose}>
            Отмена
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!reason}
          >
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
  function handleConfirm() {
    console.log("Cancel quote:", quoteId);
    onClose();
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
          <Button variant="outline" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="destructive" onClick={handleConfirm}>
            Отменить КП
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
