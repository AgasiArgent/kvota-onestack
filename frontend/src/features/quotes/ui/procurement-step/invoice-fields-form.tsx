"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CityAutocomplete, CountryCombobox, findCountryByCode, findCountryByName } from "@/shared/ui/geo";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import { INCOTERMS_2020 } from "@/shared/lib/incoterms";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { createClient } from "@/shared/lib/supabase/client";
// Type-only import: kept off the runtime path so we don't transitively pull
// `next/headers` into this Client Component (the server-side
// `fetchSupplierContacts` imports the admin client which imports `next/headers`,
// banned in Client Components). Contact rows come from the inline browser-side
// SELECT below — same SQL the create modal and card used before this refactor.
import type { SupplierContact } from "@/entities/supplier/types";

/**
 * Single source of truth for the КПП (КП поставщику) header field definitions.
 *
 * Before this component, the CREATE modal (`invoice-create-modal.tsx`) and the
 * EDIT card (`invoice-card.tsx`) each rendered their own copy of these fields
 * with their own labels, ordering, and (crucially) their own field SET — which
 * drifted: supplier_id + buyer_company_id were settable at creation but were
 * display-only on the card (Testing 2 row 91). Both consumers now render the
 * same fields here, so adding/removing a КПП field is a one-line change that
 * lands in both surfaces at once.
 *
 * The component is intentionally NOT a form: it owns no submit, no validation
 * orchestration, no totals, no items grid, no cargo-place persistence, no
 * letter draft, no split/merge — those stay on each consumer. It owns the
 * scalar header FIELDS and the supplier-change side effect (contact reset +
 * reload), nothing more.
 *
 * Persistence is mode-driven:
 *  - "create": every change calls `onFieldSave(partial)`; the create modal
 *    folds the partials into its draft state and submits once at the end.
 *  - "edit": every change calls `onFieldSave(partial)`; the card persists it
 *    immediately via Supabase `update(...).eq("id", invoice.id)`.
 *
 * When `locked` is true (edit-gate: the invoice's procurement is completed),
 * every field renders read-only/disabled. A locked edit must go through the
 * existing unlock → approval flow on the card — this component never bypasses
 * the gate, it only respects it.
 */

export interface InvoiceFieldsSupplier {
  id: string;
  name: string;
  country: string | null;
}

export interface InvoiceFieldsBuyerCompany {
  id: string;
  name: string;
  company_code: string;
}

/**
 * Current КПП header values the form renders. `null`/empty mean "not set".
 * VAT and payment fields are strings here so the inputs stay controlled
 * without numeric-coercion surprises mid-typing; parsing happens in the
 * consumer's save handler.
 */
export interface InvoiceFieldsValue {
  supplierId: string | null;
  buyerCompanyId: string | null;
  countryCode: string | null;
  city: string;
  pickupAddress: string;
  supplierContactId: string | null;
  incoterms: string;
  currency: string;
}

/**
 * Partial save payload. Keys mirror the column names persisted on
 * `kvota.invoices` so the edit card can forward them straight to
 * `handleSaveInvoiceField`, and the create modal can map them into its
 * `createInvoice` payload. A `supplier_contact_reset` marker rides along when
 * a supplier change cleared the contact, so the create modal can also drop its
 * staged contact (the card reads supplier_contact_id off the saved row).
 */
export interface InvoiceFieldsSavePartial {
  supplier_id?: string | null;
  buyer_company_id?: string | null;
  pickup_country_code?: string | null;
  pickup_country?: string | null;
  pickup_city?: string | null;
  pickup_address?: string | null;
  supplier_contact_id?: string | null;
  supplier_incoterms?: string | null;
  currency?: string;
}

export interface InvoiceFieldsFormProps {
  mode: "create" | "edit";
  /** Edit-gate. When true, every field is read-only/disabled. */
  locked?: boolean;
  /** Current КПП values. */
  value: InvoiceFieldsValue;
  /**
   * Persist a partial change. In "create" mode the consumer folds it into a
   * draft; in "edit" mode it issues the Supabase PATCH immediately.
   */
  onFieldSave: (partial: InvoiceFieldsSavePartial) => void;
  /**
   * Notifies the consumer that a supplier change reset the staged/saved
   * contact, so it can clear any local mirror of supplier_contact_id. The
   * inline warning is rendered by this component regardless.
   */
  onSupplierContactReset?: () => void;
  /**
   * Reports how many contacts the current supplier has after each load. The
   * create modal uses this to tailor its mandatory-contact validation message
   * ("У поставщика нет контактов" when the count is 0). Edit mode ignores it.
   */
  onContactsLoaded?: (count: number) => void;
  /** Suppliers available to the user (already role-scoped by the parent). */
  suppliers: readonly InvoiceFieldsSupplier[];
  /** Buyer companies for the org. */
  buyerCompanies: readonly InvoiceFieldsBuyerCompany[];
  /** Field-level validation errors keyed by field name (create mode only). */
  errors?: Record<string, string>;
  /** Clears one field's error after the user edits it (create mode only). */
  onClearError?: (field: string) => void;
}

/**
 * Loads the contacts for a supplier via the browser-side Supabase client.
 * Ordered is_primary DESC then name — same as the server-side
 * `fetchSupplierContacts`, re-issued here because the admin client is banned
 * in Client Components.
 */
function useSupplierContacts(supplierId: string | null) {
  const [contacts, setContacts] = useState<SupplierContact[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // No supplier yet: resolve to an empty list asynchronously so we never
    // call setState synchronously in the effect body (react-hooks rule).
    if (!supplierId) {
      Promise.resolve().then(() => {
        if (!cancelled) setContacts([]);
      });
      return () => {
        cancelled = true;
      };
    }
    // Synchronizing with an external system (Supabase): flip the loading flag
    // before the fetch starts. This is the legitimate data-fetch case the
    // rule's docs allow; the codebase uses the same targeted disable elsewhere
    // (shared/ui/geo/city-autocomplete.tsx, quote-detail-shell.tsx).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    (async () => {
      const supabase = createClient();
      const { data, error } = await supabase
        .from("supplier_contacts")
        .select("*")
        .eq("supplier_id", supplierId)
        .order("is_primary", { ascending: false })
        .order("name");
      if (cancelled) return;
      if (error) {
        console.error("[invoice-fields-form] fetch supplier_contacts:", error);
        setContacts([]);
        setLoading(false);
        return;
      }
      setContacts((data ?? []) as SupplierContact[]);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [supplierId]);

  return { contacts, loading };
}

export function InvoiceFieldsForm({
  mode,
  locked = false,
  value,
  onFieldSave,
  onSupplierContactReset,
  onContactsLoaded,
  suppliers,
  buyerCompanies,
  errors = {},
  onClearError,
}: InvoiceFieldsFormProps) {
  const { contacts, loading: contactsLoading } = useSupplierContacts(
    value.supplierId,
  );

  // Report contact count to the consumer after each resolved load so the
  // create modal can tailor its mandatory-contact validation message.
  useEffect(() => {
    if (contactsLoading) return;
    onContactsLoaded?.(contacts.length);
    // Fire on each settled load for the current supplier; onContactsLoaded is
    // a stable closure read at call-time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contacts, contactsLoading, value.supplierId]);
  // Inline warning shown right after a supplier change cleared the contact.
  // Cleared the next time the user picks a contact (or changes supplier again
  // — the new supplier's effect resets contacts anyway).
  const [contactResetWarning, setContactResetWarning] = useState(false);

  // Pickup address is free text. CREATE commits on every change so the modal's
  // draft tracks the value before submit (clicking «Создать» does not blur the
  // input under fireEvent). EDIT commits on BLUR — preserving the card's
  // pre-refactor behaviour of one PATCH per finished edit, not one per
  // keystroke. The internal draft keeps the input controlled between keystrokes
  // in edit mode (where `value.pickupAddress` only updates on blur).
  const [addressDraft, setAddressDraft] = useState(value.pickupAddress);
  useEffect(() => {
    setAddressDraft(value.pickupAddress);
  }, [value.pickupAddress]);

  // Create mode auto-selects the supplier's primary contact once contacts
  // load and nothing is selected yet. Edit mode never auto-picks — the saved
  // КПП already carries its supplier_contact_id and silently overwriting it on
  // a refetch would be surprising.
  useEffect(() => {
    if (mode !== "create") return;
    if (!value.supplierId) return;
    if (value.supplierContactId) return;
    if (contacts.length === 0) return;
    const primary = contacts.find((c) => c.is_primary) ?? contacts[0];
    if (primary) {
      onFieldSave({ supplier_contact_id: primary.id });
    }
    // Run only when the contact list for the current supplier resolves.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contacts, mode, value.supplierId]);

  function handleSupplierChange(nextSupplierId: string | null) {
    if (nextSupplierId === value.supplierId) return;
    onClearError?.("supplier");

    // Supplier change has a side effect: the previously selected contact
    // belongs to the OLD supplier. Reset it so a stale contact can't ride
    // into the КПП under a new supplier (mirrors create-modal behaviour).
    const hadContact = value.supplierContactId != null;

    // Auto-derive the pickup country from the supplier's stored country when
    // creating, matching the create modal's prior behaviour. Edit mode leaves
    // the saved pickup country alone — procurement may have corrected it.
    const partial: InvoiceFieldsSavePartial = {
      supplier_id: nextSupplierId,
      supplier_contact_id: null,
    };
    if (mode === "create" && nextSupplierId) {
      const supplier = suppliers.find((s) => s.id === nextSupplierId);
      if (supplier?.country) {
        const match =
          findCountryByName(supplier.country, "ru") ??
          findCountryByName(supplier.country, "en");
        if (match) {
          partial.pickup_country_code = match.code;
          partial.pickup_country = match.nameRu;
        }
      }
    }
    onFieldSave(partial);
    if (hadContact) {
      setContactResetWarning(true);
      onSupplierContactReset?.();
    }
  }

  function handleBuyerChange(nextBuyerId: string | null) {
    if (nextBuyerId === value.buyerCompanyId) return;
    onClearError?.("buyer");
    onFieldSave({ buyer_company_id: nextBuyerId });
  }

  const supplierContactPlaceholder = !value.supplierId
    ? "Сначала выберите поставщика"
    : contactsLoading
      ? "Загрузка контактов…"
      : contacts.length === 0
        ? "У поставщика нет контактов"
        : "Выберите контакт";

  return (
    <>
      <div className="space-y-1.5">
        <Label>
          Поставщик{" "}
          {mode === "create" && <span className="text-destructive">*</span>}
        </Label>
        <SearchableCombobox<InvoiceFieldsSupplier>
          value={value.supplierId}
          onChange={handleSupplierChange}
          items={suppliers}
          getLabel={(s) => s.name}
          getSearchableExtras={(s) => (s.country ? [s.country] : [])}
          placeholder="Выберите поставщика"
          searchPlaceholder="Поиск поставщика..."
          emptyMessage="Список поставщиков пуст"
          ariaLabel="Поставщик"
          disabled={locked}
          invalid={Boolean(errors.supplier)}
        />
        {errors.supplier && (
          <p className="text-xs text-destructive">{errors.supplier}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label>
          Компания-покупатель{" "}
          {mode === "create" && <span className="text-destructive">*</span>}
        </Label>
        <SearchableCombobox<InvoiceFieldsBuyerCompany>
          value={value.buyerCompanyId}
          onChange={handleBuyerChange}
          items={buyerCompanies}
          getLabel={(b) => b.name}
          getSecondary={(b) => b.company_code}
          getSearchableExtras={(b) => [b.company_code]}
          placeholder="Выберите компанию"
          searchPlaceholder="Поиск компании..."
          emptyMessage="Список компаний пуст"
          ariaLabel="Компания-покупатель"
          disabled={locked}
          invalid={Boolean(errors.buyer)}
        />
        {errors.buyer && (
          <p className="text-xs text-destructive">{errors.buyer}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label>Страна отгрузки</Label>
        <CountryCombobox
          value={value.countryCode}
          onChange={(code) => {
            if (code === value.countryCode) return;
            const ruName = code ? findCountryByCode(code)?.nameRu ?? null : null;
            onFieldSave({ pickup_country_code: code, pickup_country: ruName });
          }}
          placeholder="Выберите страну…"
          ariaLabel="Страна отгрузки"
          disabled={locked}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Город</Label>
        <CityAutocomplete
          value={value.city}
          countryCode={value.countryCode}
          onChange={(next) => {
            if (next === value.city) return;
            const trimmed = next.trim();
            onFieldSave({ pickup_city: trimmed === "" ? null : next });
          }}
          placeholder="Начните вводить город…"
          ariaLabel="Город отгрузки"
          disabled={locked}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="invoice-pickup-address">Адрес забора груза</Label>
        <Input
          id="invoice-pickup-address"
          type="text"
          value={addressDraft}
          onChange={(e) => {
            const next = e.target.value;
            setAddressDraft(next);
            if (next.trim()) onClearError?.("pickup_address");
            // CREATE commits live so the draft is ready at submit; EDIT defers
            // the PATCH to blur.
            if (mode === "create") {
              onFieldSave({ pickup_address: next.trim() === "" ? null : next });
            }
          }}
          onBlur={() => {
            if (mode !== "edit") return;
            const trimmed = addressDraft.trim();
            onFieldSave({ pickup_address: trimmed === "" ? null : addressDraft });
          }}
          placeholder="Например, ул. Промышленная, 12, склад 4"
          disabled={locked}
          aria-invalid={Boolean(errors.pickup_address)}
          className={`h-8 text-sm ${errors.pickup_address ? "border-destructive" : ""}`}
          data-testid="invoice-pickup-address"
        />
        {errors.pickup_address && (
          <p className="text-xs text-destructive">{errors.pickup_address}</p>
        )}
      </div>

      <div className="space-y-1.5" data-testid="invoice-supplier-contact">
        <Label>
          Контакт поставщика{" "}
          {mode === "create" && <span className="text-destructive">*</span>}
        </Label>
        <SearchableCombobox<SupplierContact>
          value={value.supplierContactId}
          onChange={(nextId) => {
            if (nextId === value.supplierContactId) return;
            setContactResetWarning(false);
            onClearError?.("supplier_contact");
            onFieldSave({ supplier_contact_id: nextId });
          }}
          items={contacts}
          getLabel={(c) => c.name}
          getSecondary={(c) => {
            const parts = [c.position, c.phone, c.email].filter(Boolean);
            return parts.length > 0 ? parts.join(" · ") : null;
          }}
          getSearchableExtras={(c) =>
            [c.position, c.phone, c.email].filter(
              (v): v is string => Boolean(v),
            )
          }
          placeholder={supplierContactPlaceholder}
          searchPlaceholder="Поиск контакта…"
          emptyMessage="Контакты не найдены"
          ariaLabel="Контакт поставщика"
          disabled={locked || !value.supplierId || contactsLoading}
          invalid={Boolean(errors.supplier_contact)}
        />
        {contactResetWarning && (
          <p className="text-xs text-amber-600">
            Контакт сброшен — выберите контакт нового поставщика.
          </p>
        )}
        {errors.supplier_contact && (
          <p className="text-xs text-destructive">{errors.supplier_contact}</p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label>Условия поставки</Label>
        <select
          value={value.incoterms}
          disabled={locked}
          onChange={(e) => {
            const next = e.target.value;
            if (next === value.incoterms) return;
            onFieldSave({ supplier_incoterms: next || null });
          }}
          aria-label="Условия поставки"
          className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring disabled:opacity-50 disabled:pointer-events-none"
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
          value={value.currency}
          disabled={locked}
          onChange={(e) => {
            const next = e.target.value;
            if (next === value.currency) return;
            onFieldSave({ currency: next });
          }}
          aria-label="Валюта"
          className="w-full h-8 px-2.5 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring disabled:opacity-50 disabled:pointer-events-none"
        >
          {SUPPORTED_CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
