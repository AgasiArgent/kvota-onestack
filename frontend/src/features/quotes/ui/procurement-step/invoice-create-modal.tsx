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
import { CityAutocomplete, CountryCombobox, findCountryByCode, findCountryByName } from "@/shared/ui/geo";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import { INCOTERMS_2020 } from "@/shared/lib/incoterms";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { extractErrorMessage } from "@/shared/lib/errors";
import {
  fetchSupplierVatRate,
  type VatResolverReason,
} from "@/entities/invoice/queries";
// NOTE: `fetchSupplierContacts` (in `@/entities/supplier/queries`) uses the
// server-side Supabase admin client which transitively imports `next/headers`.
// That's banned in Client Components — Turbopack fails the production build.
// We inline the same SELECT against the browser-side client below.
// Type-only import is safe: TypeScript types are erased at build time.
import type { SupplierContact } from "@/entities/supplier/types";
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
  // Testing 2 row 21: free-text pickup address + supplier-contact picker.
  // Both are mandatory before КПП creation — the supplier needs the literal
  // pickup street address and a named contact responsible for the КПП on
  // their side. The contact list is loaded reactively once a supplier is
  // chosen (kvota.supplier_contacts is keyed on supplier_id).
  const [pickupAddress, setPickupAddress] = useState("");
  const [supplierContactId, setSupplierContactId] = useState("");
  const [supplierContacts, setSupplierContacts] = useState<SupplierContact[]>([]);
  const [supplierContactsLoading, setSupplierContactsLoading] = useState(false);
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

  // Load supplier contacts when supplier changes (Testing 2 row 21). Resets
  // any previously picked contact so the user can't carry a stale selection
  // from another supplier into the new КПП. Default-selects the primary
  // contact (is_primary=true) when present — fetchSupplierContacts orders by
  // is_primary DESC, so it's just `contacts[0]` when the supplier has any
  // primary marked.
  useEffect(() => {
    if (!supplierId) {
      setSupplierContacts([]);
      setSupplierContactId("");
      return;
    }
    let cancelled = false;
    setSupplierContactsLoading(true);

    // Inline browser-side query — the server-side `fetchSupplierContacts`
    // pulls in `next/headers` via the admin client which is banned in
    // Client Components. Same SQL: order by is_primary DESC, then name.
    (async () => {
      const { createClient } = await import("@/shared/lib/supabase/client");
      const supabase = createClient();
      const { data, error } = await supabase
        .from("supplier_contacts")
        .select("*")
        .eq("supplier_id", supplierId)
        .order("is_primary", { ascending: false })
        .order("name");
      if (cancelled) return;
      if (error) {
        console.error("[invoice-create-modal] fetchSupplierContacts:", error);
        setSupplierContacts([]);
        setSupplierContactsLoading(false);
        return;
      }
      const contacts = (data ?? []) as SupplierContact[];
      setSupplierContacts(contacts);
      // Auto-pick the primary contact (is_primary=true → first in the
      // ordered list) when nothing is selected yet. Don't clobber an
      // explicit pick if the user already changed it.
      setSupplierContactId((prev) => {
        if (prev) return prev;
        const primary = contacts.find((c) => c.is_primary) ?? contacts[0];
        return primary?.id ?? "";
      });
      setSupplierContactsLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [supplierId]);

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
    setSupplierContacts([]);
    setIncoterms("");
    setCurrency("USD");
    setVatRate("");
    setVatReason(null);
    setVatManuallyEdited(false);
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
    // Testing 2 row 21: both new fields are mandatory before КПП creation.
    // pickup_address is free-text (street address driver visits), distinct
    // from pickup_city. supplier_contact_id is the named person on the
    // supplier side responsible for this КПП.
    if (!pickupAddress.trim()) e.pickup_address = "Укажите адрес забора груза";
    if (!supplierContactId) {
      e.supplier_contact = supplierId
        ? supplierContacts.length === 0
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
      <DialogContent className="sm:max-w-lg z-[200]" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Создать КП поставщику</DialogTitle>
          <DialogDescription>
            Укажите поставщика и компанию-покупателя. Остальные поля можно
            заполнить позже — после получения ответа от поставщика.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>
              Поставщик <span className="text-destructive">*</span>
            </Label>
            <SearchableCombobox<Supplier>
              value={supplierId || null}
              onChange={(newSupplierId) => {
                setSupplierId(newSupplierId ?? "");
                setErrors((prev) => {
                  const { supplier: _supplier, ...rest } = prev;
                  return rest;
                });
                // Auto-fill country from supplier; useEffect on countryCode
                // then re-resolves VAT (strategy B always overwrites). Try RU
                // locale first, fall back to EN so suppliers stored with
                // English country names ("Germany", "Turkey") also resolve.
                if (newSupplierId) {
                  const supplier = suppliers.find((s) => s.id === newSupplierId);
                  if (supplier?.country) {
                    const match =
                      findCountryByName(supplier.country, "ru") ??
                      findCountryByName(supplier.country, "en");
                    if (match) setCountryCode(match.code);
                  }
                }
              }}
              items={suppliers}
              getLabel={(s) => s.name}
              getSearchableExtras={(s) => (s.country ? [s.country] : [])}
              placeholder="Выберите поставщика"
              searchPlaceholder="Поиск поставщика..."
              emptyMessage="Список поставщиков пуст"
              ariaLabel="Поставщик"
              invalid={Boolean(errors.supplier)}
            />
            {errors.supplier && <p className="text-xs text-destructive">{errors.supplier}</p>}
          </div>

          <div className="space-y-1.5">
            <Label>
              Компания-покупатель <span className="text-destructive">*</span>
            </Label>
            <SearchableCombobox<BuyerCompany>
              value={buyerCompanyId || null}
              onChange={(newBuyerId) => {
                setBuyerCompanyId(newBuyerId ?? "");
                setErrors((prev) => {
                  const { buyer: _buyer, ...rest } = prev;
                  return rest;
                });
              }}
              items={buyerCompanies}
              getLabel={(b) => b.name}
              getSecondary={(b) => b.company_code}
              getSearchableExtras={(b) => [b.company_code]}
              placeholder="Выберите компанию"
              searchPlaceholder="Поиск компании..."
              emptyMessage="Список компаний пуст"
              ariaLabel="Компания-покупатель"
              invalid={Boolean(errors.buyer)}
            />
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
            <CityAutocomplete
              value={city}
              onChange={setCity}
              countryCode={countryCode}
              placeholder="Начните вводить город…"
              ariaLabel="Город отгрузки"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="invoice-pickup-address">
              Адрес забора груза <span className="text-destructive">*</span>
            </Label>
            <Input
              id="invoice-pickup-address"
              type="text"
              value={pickupAddress}
              onChange={(e) => {
                setPickupAddress(e.target.value);
                if (e.target.value.trim()) {
                  setErrors((prev) => {
                    const { pickup_address: _pa, ...rest } = prev;
                    return rest;
                  });
                }
              }}
              placeholder="Например, ул. Промышленная, 12, склад 4"
              aria-invalid={Boolean(errors.pickup_address)}
              aria-describedby={
                errors.pickup_address ? "invoice-pickup-address-error" : undefined
              }
              className={`h-8 text-sm ${errors.pickup_address ? "border-destructive" : ""}`}
            />
            {errors.pickup_address && (
              <p id="invoice-pickup-address-error" className="text-xs text-destructive">
                {errors.pickup_address}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label>
              Контакт поставщика <span className="text-destructive">*</span>
            </Label>
            <SearchableCombobox<SupplierContact>
              value={supplierContactId || null}
              onChange={(newContactId) => {
                setSupplierContactId(newContactId ?? "");
                setErrors((prev) => {
                  const { supplier_contact: _sc, ...rest } = prev;
                  return rest;
                });
              }}
              items={supplierContacts}
              getLabel={(c) => c.name}
              getSecondary={(c) => {
                const parts = [c.position, c.phone, c.email].filter(Boolean);
                return parts.length > 0 ? parts.join(" · ") : null;
              }}
              getSearchableExtras={(c) =>
                [c.position, c.phone, c.email].filter(
                  (v): v is string => Boolean(v)
                )
              }
              placeholder={
                !supplierId
                  ? "Сначала выберите поставщика"
                  : supplierContactsLoading
                    ? "Загрузка контактов…"
                    : supplierContacts.length === 0
                      ? "У поставщика нет контактов"
                      : "Выберите контакт"
              }
              searchPlaceholder="Поиск контакта…"
              emptyMessage="Контакты не найдены"
              ariaLabel="Контакт поставщика"
              disabled={!supplierId || supplierContactsLoading}
              invalid={Boolean(errors.supplier_contact)}
            />
            {errors.supplier_contact && (
              <p className="text-xs text-destructive">{errors.supplier_contact}</p>
            )}
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
