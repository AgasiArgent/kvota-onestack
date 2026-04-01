"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { recordActualPayment } from "@/features/plan-fact/api";
import type { PlanFactItem, PlanFactCurrency } from "@/entities/finance";

interface PlanFactSheetProps {
  item: PlanFactItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

const CURRENCY_OPTIONS: { value: PlanFactCurrency; label: string }[] = [
  { value: "RUB", label: "RUB" },
  { value: "USD", label: "USD" },
  { value: "EUR", label: "EUR" },
];

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "---";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function getTodayISO(): string {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

interface FormErrors {
  actual_amount?: string;
  actual_currency?: string;
  actual_date?: string;
}

export function PlanFactSheet({
  item,
  open,
  onOpenChange,
  onSuccess,
}: PlanFactSheetProps) {
  const [actualAmount, setActualAmount] = useState("");
  const [actualCurrency, setActualCurrency] = useState<PlanFactCurrency>(
    item.planned_currency,
  );
  const [actualDate, setActualDate] = useState(getTodayISO());
  const [paymentDocument, setPaymentDocument] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  function resetForm() {
    setActualAmount("");
    setActualCurrency(item.planned_currency);
    setActualDate(getTodayISO());
    setPaymentDocument("");
    setNotes("");
    setErrors({});
  }

  function validate(): FormErrors {
    const errs: FormErrors = {};
    const parsed = parseFloat(actualAmount);
    if (!actualAmount || isNaN(parsed) || parsed <= 0) {
      errs.actual_amount = "Введите корректную сумму";
    }
    if (!actualCurrency) {
      errs.actual_currency = "Выберите валюту";
    }
    if (!actualDate) {
      errs.actual_date = "Укажите дату";
    }
    return errs;
  }

  async function handleSubmit() {
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setErrors({});
    setSubmitting(true);

    try {
      await recordActualPayment(item.deal_id, item.id, {
        actual_amount: parseFloat(actualAmount),
        actual_currency: actualCurrency,
        actual_date: actualDate,
        payment_document: paymentDocument.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      resetForm();
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось записать оплату";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetForm();
    }
    onOpenChange(nextOpen);
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Отметить оплаченным</SheetTitle>
          <SheetDescription>
            Заполните фактические данные об оплате
          </SheetDescription>
        </SheetHeader>

        {/* Read-only plan card */}
        <div className="mx-4 rounded-lg border bg-muted/30 p-3 space-y-2">
          <div className="flex items-center gap-2">
            <Badge
              className={
                item.category.is_income
                  ? "bg-green-100 text-green-700"
                  : "bg-red-100 text-red-700"
              }
            >
              {item.category.name}
            </Badge>
          </div>
          {item.description && (
            <p className="text-sm text-foreground">{item.description}</p>
          )}
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted-foreground">План:</span>
            <span className="font-medium tabular-nums">
              {formatAmount(item.planned_amount, item.planned_currency)}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted-foreground">Дата план:</span>
            <span className="tabular-nums">
              {formatDate(item.planned_date)}
            </span>
          </div>
        </div>

        {/* Form */}
        <div className="flex flex-col gap-4 px-4">
          {/* Actual amount */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Сумма факт <span className="text-destructive">*</span>
            </Label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={actualAmount}
              onChange={(e) => {
                setActualAmount(e.target.value);
                if (errors.actual_amount) {
                  setErrors((prev) => ({ ...prev, actual_amount: undefined }));
                }
              }}
              placeholder="0.00"
              className={errors.actual_amount ? "border-destructive" : ""}
            />
            {errors.actual_amount && (
              <p className="text-xs text-destructive">{errors.actual_amount}</p>
            )}
          </div>

          {/* Actual currency */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Валюта <span className="text-destructive">*</span>
            </Label>
            <Select
              value={actualCurrency}
              onValueChange={(val) => {
                if (val) setActualCurrency(val as PlanFactCurrency);
                if (errors.actual_currency) {
                  setErrors((prev) => ({
                    ...prev,
                    actual_currency: undefined,
                  }));
                }
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.actual_currency && (
              <p className="text-xs text-destructive">
                {errors.actual_currency}
              </p>
            )}
          </div>

          {/* Actual date */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Дата оплаты <span className="text-destructive">*</span>
            </Label>
            <Input
              type="date"
              value={actualDate}
              onChange={(e) => {
                setActualDate(e.target.value);
                if (errors.actual_date) {
                  setErrors((prev) => ({ ...prev, actual_date: undefined }));
                }
              }}
              className={errors.actual_date ? "border-destructive" : ""}
            />
            {errors.actual_date && (
              <p className="text-xs text-destructive">{errors.actual_date}</p>
            )}
          </div>

          {/* Payment document */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Платёжный документ
            </Label>
            <Input
              value={paymentDocument}
              onChange={(e) => setPaymentDocument(e.target.value)}
              placeholder="Номер п/п, счёт и т.д."
            />
          </div>

          {/* Notes */}
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Примечание
            </Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Комментарий к оплате..."
              rows={3}
            />
          </div>

          {/* Submit */}
          <Button
            onClick={handleSubmit}
            disabled={submitting}
            className="w-full"
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Отметить оплаченным
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
