"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { submitToProcurementWithChecklist, patchQuote } from "@/entities/quote/mutations";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Pre-transfer validation
// ---------------------------------------------------------------------------

const FIELD_LABELS: Record<string, string> = {
  customer_id: "Клиент",
  seller_company_id: "Продавец",
  delivery_city: "Город доставки",
  delivery_country: "Страна",
  delivery_method: "Способ доставки",
  incoterms: "Условия поставки",
};

export function validateForTransfer(
  quote: QuoteDetailRow,
  items: QuoteItemRow[]
): string[] {
  const errors: string[] = [];

  for (const [field, label] of Object.entries(FIELD_LABELS)) {
    const value = (quote as Record<string, unknown>)[field];
    if (!value || (typeof value === "string" && !value.trim())) {
      errors.push(label);
    }
  }

  const validItems = items.filter(
    (item) =>
      item.product_name?.trim() &&
      item.quantity != null &&
      Number(item.quantity) > 0 &&
      item.unit?.trim()
  );

  if (validItems.length === 0) {
    errors.push("Хотя бы одна позиция (наименование, количество, ед.изм.)");
  }

  return errors;
}

// ---------------------------------------------------------------------------
// Transfer Dialog
// ---------------------------------------------------------------------------

interface TransferDialogProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
}

export function TransferDialog({ quote, items }: TransferDialogProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [equipmentDescription, setEquipmentDescription] = useState("");
  const [isEstimate, setIsEstimate] = useState(false);
  const [isTender, setIsTender] = useState(false);
  const [directRequest, setDirectRequest] = useState(false);
  const [tradingOrgRequest, setTradingOrgRequest] = useState(false);
  const [deliveryPriority, setDeliveryPriority] = useState(
    quote.delivery_priority ?? ""
  );
  const [error, setError] = useState<string | null>(null);

  function handleOpenClick() {
    const errors = validateForTransfer(quote, items);
    if (errors.length > 0) {
      toast.error("Заполните обязательные поля: " + errors.join(", "));
      return;
    }
    setOpen(true);
  }

  function handleClose() {
    if (submitting) return;
    setOpen(false);
    setEquipmentDescription("");
    setIsEstimate(false);
    setIsTender(false);
    setDirectRequest(false);
    setTradingOrgRequest(false);
    setDeliveryPriority(quote.delivery_priority ?? "");
    setError(null);
  }

  async function handleSubmit() {
    const desc = equipmentDescription.trim();
    if (!desc) {
      setError("Это поле обязательно для заполнения");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      if (deliveryPriority) {
        await patchQuote(quote.id, { delivery_priority: deliveryPriority });
      }
      await submitToProcurementWithChecklist(quote.id, {
        is_estimate: isEstimate,
        is_tender: isTender,
        direct_request: directRequest,
        trading_org_request: tradingOrgRequest,
        equipment_description: desc,
      });
      toast.success("КП передана в закупки");
      setOpen(false);
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось передать в закупки"
      );
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = equipmentDescription.trim().length > 0 && !submitting;

  return (
    <>
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={handleOpenClick}
      >
        <ArrowRight size={14} />
        Передать в закупки
      </Button>

      <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Контрольный список</DialogTitle>
            <DialogDescription>
              Заполните информацию перед передачей в закупки
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {/* Checkboxes */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Checkbox
                  id="chk-is-estimate"
                  checked={isEstimate}
                  onCheckedChange={(checked) =>
                    setIsEstimate(checked === true)
                  }
                />
                <Label htmlFor="chk-is-estimate" className="cursor-pointer text-sm">
                  Это проценка?
                </Label>
              </div>

              <div className="flex items-center gap-2">
                <Checkbox
                  id="chk-is-tender"
                  checked={isTender}
                  onCheckedChange={(checked) =>
                    setIsTender(checked === true)
                  }
                />
                <Label htmlFor="chk-is-tender" className="cursor-pointer text-sm">
                  Это тендер?
                </Label>
              </div>

              <div className="flex items-center gap-2">
                <Checkbox
                  id="chk-direct-request"
                  checked={directRequest}
                  onCheckedChange={(checked) =>
                    setDirectRequest(checked === true)
                  }
                />
                <Label htmlFor="chk-direct-request" className="cursor-pointer text-sm">
                  Запрашивал ли клиент напрямую?
                </Label>
              </div>

              <div className="flex items-center gap-2">
                <Checkbox
                  id="chk-trading-org"
                  checked={tradingOrgRequest}
                  onCheckedChange={(checked) =>
                    setTradingOrgRequest(checked === true)
                  }
                />
                <Label htmlFor="chk-trading-org" className="cursor-pointer text-sm">
                  Запрашивал ли клиент через торгующих организаций?
                </Label>
              </div>
            </div>

            {/* Delivery priority */}
            <div className="space-y-2">
              <Label className="text-sm font-medium">Тип доставки</Label>
              <div className="flex gap-3">
                {([
                  { value: "fast", label: "Быстрее" },
                  { value: "normal", label: "Обычно" },
                  { value: "cheap", label: "Дешевле" },
                ] as const).map((opt) => (
                  <label
                    key={opt.value}
                    className="flex items-center gap-1.5 cursor-pointer text-sm"
                  >
                    <input
                      type="radio"
                      name="delivery_priority"
                      value={opt.value}
                      checked={deliveryPriority === opt.value}
                      onChange={() => setDeliveryPriority(opt.value)}
                      className="accent-accent"
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Required textarea */}
            <div className="space-y-1.5">
              <Label htmlFor="checklist-equipment" className="text-sm font-medium">
                Что это за оборудование и для чего оно необходимо?{" "}
                <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="checklist-equipment"
                value={equipmentDescription}
                onChange={(e) => {
                  setEquipmentDescription(e.target.value);
                  if (error) setError(null);
                }}
                placeholder="Опишите оборудование и его назначение..."
                rows={3}
                className={error ? "border-destructive" : ""}
              />
              {error && (
                <p className="text-xs text-destructive">{error}</p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              className="bg-accent text-white hover:bg-accent-hover"
              onClick={handleSubmit}
              disabled={!canSubmit}
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Передать в закупки
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
