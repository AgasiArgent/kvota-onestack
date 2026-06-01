"use client";

import { useState, useEffect } from "react";
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
import { findCountryByCode } from "@/shared/ui/geo";
import { extractErrorMessage } from "@/shared/lib/errors";
import {
  fetchSupplierVatRate,
  type VatResolverReason,
} from "@/entities/invoice/queries";
import { Badge } from "@/components/ui/badge";
import {
  InvoiceFieldsForm,
  type InvoiceFieldsSavePartial,
  type InvoiceFieldsValue,
} from "./invoice-fields-form";

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
  // КПП header fields — now rendered by the shared <InvoiceFieldsForm>. This
  // modal stays the source of truth for the draft values + submit; the shared
  // component just renders the fields and reports changes via onFieldSave so
  // CREATE and the EDIT card can't drift (Testing 2 row 91 prep). The contact
  // list + supplier-change reset side effect live inside the shared component.
  const [supplierId, setSupplierId] = useState("");
  const [buyerCompanyId, setBuyerCompanyId] = useState("");
  const [countryCode, setCountryCode] = useState<string | null>(null);
  const [city, setCity] = useState("");
  // Testing 2 row 21: free-text pickup address + supplier-contact picker.
  // pickup_address is optional (Testing 2 row 25); supplier_contact stays
  // mandatory before КПП creation.
  const [pickupAddress, setPickupAddress] = useState("");
  const [supplierContactId, setSupplierContactId] = useState("");
  // Count of contacts the chosen supplier has — reported by the shared form's
  // onContactsLoaded so we can keep the precise "У поставщика нет контактов"
  // validation message (Testing 2 row 21). Null until a supplier is picked.
  const [supplierContactsCount, setSupplierContactsCount] = useState<
    number | null
  >(null);
  const [incoterms, setIncoterms] = useState<string>("");
  const [currency, setCurrency] = useState<string>("USD");
  const [boxes, setBoxes] = useState<
    Array<{ weight_kg: string; length_mm: string; width_mm: string; height_mm: string }>
  >([{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]);
  const [vatRate, setVatRate] = useState("");
  const [vatReason, setVatReason] = useState<VatResolverReason | null>(null);
  // РОЗ-95 / МОЗ-82 (2026-05-05): autofill is now empty-only — a manually
  // typed (or previously autofilled, then edited) value is never overwritten
  // when the user changes country/buyer afterwards. The ``vatManuallyEdited``
  // flag still drives the inline "вручную" badge so the user can see why the
  // auto-resolved reason badge disappeared.
  const [vatManuallyEdited, setVatManuallyEdited] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Auto-fill VAT rate + reason when both supplier country AND buyer company
  // are selected. Empty-only: skips the network round-trip when the user has
  // already entered a rate, so a country change after manual editing leaves
  // the typed value intact.
  useEffect(() => {
    if (!countryCode || !buyerCompanyId) return;
    if (vatRate.trim() !== "") return;

    let cancelled = false;

    fetchSupplierVatRate({
      supplierCountryCode: countryCode,
      buyerCompanyId,
    }).then((result) => {
      if (cancelled) return;
      if (result) {
        // Re-check the empty guard at resolution time — the user may have
        // started typing during the network round-trip.
        setVatRate((prev) => (prev.trim() === "" ? result.rate.toString() : prev));
        setVatReason(result.reason);
        setVatManuallyEdited(false);
      } else {
        // Network / backend failure — keep user's current vatRate, hide badge.
        // Fail silently per Requirement 3.8.
        setVatReason(null);
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countryCode, buyerCompanyId]);

  function handleClose() {
    resetForm();
    onClose();
  }

  function resetForm() {
    setSupplierId("");
    setBuyerCompanyId("");
    setCountryCode(null);
    setCity("");
    setPickupAddress("");
    setSupplierContactId("");
    setSupplierContactsCount(null);
    setIncoterms("");
    setCurrency("USD");
    setVatRate("");
    setVatReason(null);
    setVatManuallyEdited(false);
    setBoxes([{ weight_kg: "", length_mm: "", width_mm: "", height_mm: "" }]);
    setErrors({});
  }

  // Fold a partial change from <InvoiceFieldsForm> into the draft state. The
  // partial keys mirror the `invoices` columns; we map them to the modal's
  // local state. `undefined` means "field not part of this change" — only
  // present keys are applied, so a supplier change that also derived a country
  // updates both without clobbering city/contact.
  function handleFieldSave(partial: InvoiceFieldsSavePartial) {
    if ("supplier_id" in partial) setSupplierId(partial.supplier_id ?? "");
    if ("buyer_company_id" in partial)
      setBuyerCompanyId(partial.buyer_company_id ?? "");
    if ("pickup_country_code" in partial)
      setCountryCode(partial.pickup_country_code ?? null);
    if ("pickup_city" in partial) setCity(partial.pickup_city ?? "");
    if ("pickup_address" in partial)
      setPickupAddress(partial.pickup_address ?? "");
    if ("supplier_contact_id" in partial)
      setSupplierContactId(partial.supplier_contact_id ?? "");
    if ("supplier_incoterms" in partial)
      setIncoterms(partial.supplier_incoterms ?? "");
    if ("currency" in partial && partial.currency != null)
      setCurrency(partial.currency);
  }

  function clearError(field: string) {
    setErrors((prev) => {
      if (!(field in prev)) return prev;
      const rest = { ...prev };
      delete rest[field];
      return rest;
    });
  }

  const fieldsValue: InvoiceFieldsValue = {
    supplierId: supplierId || null,
    buyerCompanyId: buyerCompanyId || null,
    countryCode,
    city,
    pickupAddress,
    supplierContactId: supplierContactId || null,
    incoterms,
    currency,
  };

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

  // Real procurement workflow: КП is created early with only supplier + buyer
  // known. Country, incoterms, currency, cargo dimensions arrive later from
  // the supplier's reply and are filled in afterward. Keep validation minimal
  // so the form matches the workflow.
  function isBoxBlank(box: (typeof boxes)[number]): boolean {
    return !box.weight_kg && !box.length_mm && !box.width_mm && !box.height_mm;
  }

  function isBoxComplete(box: (typeof boxes)[number]): boolean {
    const w = parseFloat(box.weight_kg);
    const l = parseInt(box.length_mm, 10);
    const wd = parseInt(box.width_mm, 10);
    const h = parseInt(box.height_mm, 10);
    return w > 0 && l > 0 && wd > 0 && h > 0;
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!supplierId) e.supplier = "Выберите поставщика";
    if (!buyerCompanyId) e.buyer = "Выберите компанию-покупателя";
    // Testing 2 row 21: supplier_contact_id is the named person on the
    // supplier side responsible for this КПП — still mandatory.
    // Testing 2 row 25 (FB 2026-05-14): pickup_address dropped to optional
    // per tester request — the driver address is often filled later by
    // procurement once the supplier confirms staging warehouse.
    if (!supplierContactId) {
      e.supplier_contact = supplierId
        ? supplierContactsCount === 0
          ? "У поставщика нет контактов — добавьте контакт в карточке поставщика"
          : "Выберите контакт поставщика"
        : "Сначала выберите поставщика";
    }

    // Cargo places are optional. If a row is touched, require all four fields
    // > 0 so we never persist partial garbage (weight without dimensions etc.).
    for (let i = 0; i < boxes.length; i++) {
      const box = boxes[i];
      if (!isBoxBlank(box) && !isBoxComplete(box)) {
        e[`box_${i}`] = `Место ${i + 1}: заполните все поля > 0 или очистите`;
      }
    }

    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate()) return;
    setSubmitting(true);
    try {
      // Drop blank rows so the empty-by-default first row doesn't reach the API.
      const parsedBoxes: CargoPlaceInput[] = boxes
        .filter((b) => !isBoxBlank(b))
        .map((box) => ({
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
        pickup_address: pickupAddress.trim() || undefined,
        supplier_contact_id: supplierContactId || undefined,
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
      <DialogContent
        className="sm:max-w-lg z-[200] overflow-x-hidden"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle>Создать КП поставщику</DialogTitle>
          <DialogDescription>
            Укажите поставщика и компанию-покупателя. Остальные поля можно
            заполнить позже — после получения ответа от поставщика.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <InvoiceFieldsForm
            mode="create"
            value={fieldsValue}
            onFieldSave={handleFieldSave}
            onContactsLoaded={setSupplierContactsCount}
            suppliers={suppliers}
            buyerCompanies={buyerCompanies}
            errors={errors}
            onClearError={clearError}
          />

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
                  setVatManuallyEdited(true);
                }}
                placeholder="Ставка НДС"
                className="h-8 w-28 text-sm tabular-nums"
              />
              {!vatManuallyEdited && vatReason === "domestic" && (
                <Badge variant="secondary" className="text-xs">
                  Внутренний НДС
                </Badge>
              )}
              {!vatManuallyEdited && vatReason === "export_zero_rated" && (
                <Badge variant="outline" className="text-xs">
                  Экспорт, 0%
                </Badge>
              )}
              {!vatManuallyEdited && vatReason === "unknown" && (
                <Badge variant="outline" className="text-xs text-muted-foreground">
                  Неизвестно
                </Badge>
              )}
              {vatManuallyEdited && (
                <Badge variant="outline" className="text-xs">
                  вручную
                </Badge>
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
              <div className="max-h-36 overflow-y-auto overflow-x-hidden rounded-md border border-input bg-muted/30 p-2 space-y-1">
                {selectedItems.map((item) => (
                  <div
                    key={item.id}
                    className="text-xs flex items-center gap-2 min-w-0"
                  >
                    <span className="font-medium truncate max-w-20 shrink-0">
                      {item.brand ?? "—"}
                    </span>
                    <span className="font-mono text-muted-foreground truncate max-w-24 shrink-0">
                      {item.product_code ?? "—"}
                    </span>
                    <span className="truncate flex-1 min-w-0">
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
