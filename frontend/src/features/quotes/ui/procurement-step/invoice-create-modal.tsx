"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Plus, RotateCcw, X } from "lucide-react";
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
import { CountryCombobox, findCountryByCode, findCountryByName } from "@/shared/ui/geo";
import { INCOTERMS_2020 } from "@/shared/lib/incoterms";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { extractErrorMessage } from "@/shared/lib/errors";
import {
  fetchSupplierVatRate,
  type VatResolverReason,
} from "@/entities/invoice/queries";
import { Badge } from "@/components/ui/badge";

interface Supplier {
  id: string;
  name: string;
  country: string | null;
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
  const [countryCode, setCountryCode] = useState<string | null>(null);
  const [city, setCity] = useState("");
  const [incoterms, setIncoterms] = useState<string>("");
  const [currency, setCurrency] = useState<string>("USD");
  const [boxes, setBoxes] = useState<
    Array<{ weight_kg: string; length_mm: string; width_mm: string; height_mm: string }>
  >([{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]);
  const [vatRate, setVatRate] = useState("");
  const [vatReason, setVatReason] = useState<VatResolverReason | null>(null);
  const [vatManuallyOverridden, setVatManuallyOverridden] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Auto-fill VAT rate + reason when both supplier country AND buyer company
  // are selected. Reason is surfaced as an inline badge next to the rate.
  // Manual override suppresses the auto-fill (but we still keep the user's
  // value — no mutation of vatRate here).
  useEffect(() => {
    if (!countryCode || !buyerCompanyId || vatManuallyOverridden) return;

    let cancelled = false;

    fetchSupplierVatRate({
      supplierCountryCode: countryCode,
      buyerCompanyId,
    }).then((result) => {
      if (cancelled) return;
      if (result) {
        setVatRate(result.rate.toString());
        setVatReason(result.reason);
      } else {
        // Network / backend failure — keep user's current vatRate, hide badge.
        // Fail silently per Requirement 3.8.
        setVatReason(null);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [countryCode, buyerCompanyId, vatManuallyOverridden]);

  function handleClose() {
    resetForm();
    onClose();
  }

  function resetForm() {
    setSupplierId("");
    setBuyerCompanyId("");
    setCountryCode(null);
    setCity("");
    setIncoterms("");
    setCurrency("USD");
    setVatRate("");
    setVatReason(null);
    setVatManuallyOverridden(false);
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
        pickup_country_override: countryCode
          ? findCountryByCode(countryCode)?.nameRu
          : undefined,
        pickup_country_code: countryCode || undefined,
        pickup_city: city || undefined,
        supplier_incoterms: incoterms || undefined,
        currency,
        boxes: parsedBoxes,
      });

      if (selectedItems.length > 0) {
        await assignItemsToInvoice(
          selectedItems.map((i) => i.id),
          invoice.id
        );

        // Write VAT rate to assigned items when provided
        const parsedVat = vatRate.trim() ? parseFloat(vatRate) : null;
        if (parsedVat !== null && !isNaN(parsedVat)) {
          const supabase = (await import("@/shared/lib/supabase/client")).createClient();
          const { error } = await supabase
            .from("quote_items")
            .update({ vat_rate: parsedVat })
            .in("id", selectedItems.map((i) => i.id));
          if (error) throw error;
        }
      }

      toast.success("КП поставщику создано");
      handleClose();
      router.refresh();
    } catch (err) {
      console.error("[invoice-create-modal] submit failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось создать КП поставщику");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = !submitting;

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogContent className="sm:max-w-lg z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Создать КП поставщику</DialogTitle>
          <DialogDescription>
            Заполните данные КП поставщика и назначьте позиции
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>
              Поставщик <span className="text-destructive">*</span>
            </Label>
            <select
              value={supplierId}
              onChange={(e) => {
                const newSupplierId = e.target.value;
                setSupplierId(newSupplierId);
                setErrors((prev) => { const { supplier, ...rest } = prev; return rest; });
                // Auto-fill country from supplier when user hasn't manually picked one.
                // Try RU locale first, fall back to EN so suppliers stored with
                // English country names ("Germany", "Turkey") also resolve.
                // useEffect on countryCode then triggers VAT autofill.
                if (!vatManuallyOverridden && newSupplierId) {
                  const supplier = suppliers.find((s) => s.id === newSupplierId);
                  if (supplier?.country) {
                    const match =
                      findCountryByName(supplier.country, "ru") ??
                      findCountryByName(supplier.country, "en");
                    if (match) setCountryCode(match.code);
                  }
                }
              }}
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
            <Label>Страна отгрузки</Label>
            <CountryCombobox
              value={countryCode}
              onChange={setCountryCode}
              placeholder="Выберите страну…"
              ariaLabel="Страна отгрузки"
            />
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
            <Label>Условия поставки</Label>
            <select
              value={incoterms}
              onChange={(e) => setIncoterms(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              <option value="">— не указано —</option>
              {INCOTERMS_2020.map((term) => (
                <option key={term.code} value={term.code}>
                  {term.code} — {term.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>Валюта</Label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
            >
              {SUPPORTED_CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>Ставка НДС, %</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                step="0.01"
                min="0"
                max="100"
                value={vatRate}
                onChange={(e) => {
                  setVatRate(e.target.value);
                  if (!vatManuallyOverridden) {
                    setVatManuallyOverridden(true);
                  }
                }}
                placeholder="Ставка НДС"
                className="h-8 w-28 text-sm tabular-nums"
              />
              {!vatManuallyOverridden && vatReason === "domestic" && (
                <Badge variant="secondary" className="text-xs">
                  Внутренний НДС
                </Badge>
              )}
              {!vatManuallyOverridden && vatReason === "export_zero_rated" && (
                <Badge variant="outline" className="text-xs">
                  Экспорт, 0%
                </Badge>
              )}
              {!vatManuallyOverridden && vatReason === "unknown" && (
                <Badge variant="outline" className="text-xs text-muted-foreground">
                  Неизвестно
                </Badge>
              )}
              {vatManuallyOverridden && (
                <>
                  <Badge variant="outline" className="text-xs">
                    вручную
                  </Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-xs text-muted-foreground"
                    onClick={() => {
                      setVatManuallyOverridden(false);
                      // Trigger re-fetch by clearing override — useEffect will pick up countryCode
                      if (countryCode) {
                        setVatRate("");
                      }
                    }}
                  >
                    <RotateCcw size={12} className="mr-1" />
                    Сбросить
                  </Button>
                </>
              )}
            </div>
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
                    className={`h-8 text-sm ${errors[`box_${i}`] ? "border-destructive" : ""}`}
                    placeholder="Вес, кг"
                    value={box.weight_kg}
                    onChange={(e) => updateBox(i, "weight_kg", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className={`h-8 text-sm ${errors[`box_${i}`] ? "border-destructive" : ""}`}
                    placeholder="Длина, мм"
                    value={box.length_mm}
                    onChange={(e) => updateBox(i, "length_mm", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className={`h-8 text-sm ${errors[`box_${i}`] ? "border-destructive" : ""}`}
                    placeholder="Ширина, мм"
                    value={box.width_mm}
                    onChange={(e) => updateBox(i, "width_mm", e.target.value)}
                  />
                  <Input
                    type="number"
                    step="1"
                    min="0"
                    className={`h-8 text-sm ${errors[`box_${i}`] ? "border-destructive" : ""}`}
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
            <Label>Файл КП поставщика</Label>
            <Input type="file" />
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
