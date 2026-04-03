"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  createInvoice,
  assignItemsToInvoice,
  type CargoPlaceInput,
} from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

const CURRENCIES = ["USD", "EUR", "CNY", "RUB"] as const;

interface Supplier {
  id: string;
  name: string;
}

interface BuyerCompany {
  id: string;
  name: string;
  company_code: string;
}

interface InvoiceCreateModalProps {
  open: boolean;
  onClose: () => void;
  quoteId: string;
  idnQuote: string;
  selectedItems: QuoteItemRow[];
  suppliers: Supplier[];
  buyerCompanies: BuyerCompany[];
}

export function InvoiceCreateModal({
  open,
  onClose,
  quoteId,
  idnQuote,
  selectedItems,
  suppliers,
  buyerCompanies,
}: InvoiceCreateModalProps) {
  const router = useRouter();
  const [supplierId, setSupplierId] = useState("");
  const [buyerCompanyId, setBuyerCompanyId] = useState("");
  const [city, setCity] = useState("");
  const [currency, setCurrency] = useState<string>("USD");
  const [boxes, setBoxes] = useState<
    Array<{ weight_kg: string; length_mm: string; width_mm: string; height_mm: string }>
  >([{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  function handleClose() {
    resetForm();
    onClose();
  }

  function resetForm() {
    setSupplierId("");
    setBuyerCompanyId("");
    setCity("");
    setCurrency("USD");
    setBoxes([{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]);
    setErrors({});
  }

  function updateBox(index: number, field: string, value: string) {
    setBoxes((prev) =>
      prev.map((box, i) => (i === index ? { ...box, [field]: value } : box))
    );
  }

  function addBox() {
    setBoxes((prev) => [
      ...prev,
      { weight_kg: "", length_mm: "", width_mm: "", height_mm: "" },
    ]);
  }

  function removeBox(index: number) {
    setBoxes((prev) => prev.filter((_, i) => i !== index));
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!supplierId) e.supplier = "Выберите поставщика";
    if (!buyerCompanyId) e.buyer = "Выберите компанию-покупателя";
    if (!currency) e.currency = "Выберите валюту";

    for (let i = 0; i < boxes.length; i++) {
      const box = boxes[i];
      const w = parseFloat(box.weight_kg);
      const l = parseInt(box.length_mm, 10);
      const wd = parseInt(box.width_mm, 10);
      const h = parseInt(box.height_mm, 10);
      if (!w || w <= 0 || !l || l <= 0 || !wd || wd <= 0 || !h || h <= 0) {
        e[`box_${i}`] = `Место ${i + 1}: все поля обязательны и > 0`;
      }
    }

    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const parsedBoxes: CargoPlaceInput[] = boxes.map((box) => ({
        weight_kg: parseFloat(box.weight_kg),
        length_mm: parseInt(box.length_mm, 10),
        width_mm: parseInt(box.width_mm, 10),
        height_mm: parseInt(box.height_mm, 10),
      }));

      const invoice = await createInvoice({
        quote_id: quoteId,
        idn_quote: idnQuote,
        supplier_id: supplierId || undefined,
        buyer_company_id: buyerCompanyId || undefined,
        pickup_city: city || undefined,
        currency,
        boxes: parsedBoxes,
      });

      if (selectedItems.length > 0) {
        await assignItemsToInvoice(
          selectedItems.map((i) => i.id),
          invoice.id
        );
      }

      toast.success("Инвойс создан");
      handleClose();
      router.refresh();
    } catch {
      toast.error("Не удалось создать инвойс");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-lg z-[200]">
        <DialogHeader>
          <DialogTitle>Создать инвойс</DialogTitle>
          <DialogDescription>
            Заполните данные инвойса и назначьте позиции
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>
              Поставщик <span className="text-destructive">*</span>
            </Label>
            <select
              value={supplierId}
              onChange={(e) => { setSupplierId(e.target.value); setErrors((prev) => { const { supplier, ...rest } = prev; return rest; }); }}
              className={`w-full h-8 px-2.5 text-sm border rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring ${errors.supplier ? "border-destructive" : "border-input"}`}
            >
              <option value="">Выберите поставщика</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {errors.supplier && <p className="text-xs text-destructive">{errors.supplier}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>
              Компания-покупатель <span className="text-destructive">*</span>
            </Label>
            <select
              value={buyerCompanyId}
              onChange={(e) => { setBuyerCompanyId(e.target.value); setErrors((prev) => { const { buyer, ...rest } = prev; return rest; }); }}
              className={`w-full h-8 px-2.5 text-sm border rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring ${errors.buyer ? "border-destructive" : "border-input"}`}
            >
              <option value="">Выберите компанию</option>
              {buyerCompanies.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name} ({b.company_code})
                </option>
              ))}
            </select>
            {errors.buyer && <p className="text-xs text-destructive">{errors.buyer}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>Город</Label>
            <Input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Город отгрузки"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Валюта</Label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <Label>Грузовые места</Label>
            {boxes.map((box, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground font-medium">
                    Место {i + 1}
                  </span>
                  {boxes.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeBox(i)}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    className="h-8 text-sm"
                    placeholder="Вес, кг"
                    value={box.weight_kg}
                    onChange={(e) => updateBox(i, "weight_kg", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className="h-8 text-sm"
                    placeholder="Длина, мм"
                    value={box.length_mm}
                    onChange={(e) => updateBox(i, "length_mm", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className="h-8 text-sm"
                    placeholder="Ширина, мм"
                    value={box.width_mm}
                    onChange={(e) => updateBox(i, "width_mm", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className="h-8 text-sm"
                    placeholder="Высота, мм"
                    value={box.height_mm}
                    onChange={(e) => updateBox(i, "height_mm", e.target.value)}
                  />
                </div>
                {errors[`box_${i}`] && (
                  <p className="text-xs text-destructive">{errors[`box_${i}`]}</p>
                )}
              </div>
            ))}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={addBox}
            >
              <Plus size={14} />
              Добавить место
            </Button>
          </div>

          <div className="space-y-1.5">
            <Label>Файл инвойса</Label>
            <Input type="file" accept=".pdf,.jpg,.png,.xlsx" />
          </div>

          {selectedItems.length > 0 && (
            <div className="space-y-1.5">
              <Label>
                Назначаемые позиции ({selectedItems.length})
              </Label>
              <div className="max-h-36 overflow-y-auto rounded-md border border-input bg-muted/30 p-2 space-y-1">
                {selectedItems.map((item) => (
                  <div
                    key={item.id}
                    className="text-xs flex items-center gap-2"
                  >
                    <span className="font-medium truncate max-w-20">
                      {item.brand ?? "\u2014"}
                    </span>
                    <span className="font-mono text-muted-foreground truncate max-w-24">
                      {item.product_code ?? "\u2014"}
                    </span>
                    <span className="truncate flex-1">
                      {item.product_name}
                    </span>
                    <span className="font-mono shrink-0">
                      {item.quantity}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Отмена
          </Button>
          <Button
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSubmit}
            disabled={!canSubmit}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Создать
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
