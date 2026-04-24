"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Save, X } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { SupplierDetail } from "@/entities/supplier/types";
import { updateSupplier } from "@/entities/supplier/mutations";
import { extractErrorMessage } from "@/shared/lib/errors";
import {
  CityAutocomplete,
  CountryCombobox,
  findCountryByCode,
  findCountryByName,
} from "@/shared/ui/geo";

interface Props {
  supplier: SupplierDetail;
}

/**
 * Resolve the initial country code for the edit form. If the row already
 * has a canonical `country_code` (post-migration 295), use it; otherwise
 * attempt a best-effort match against the free-text `country` column so
 * the picker starts with a reasonable selection even for un-backfilled rows.
 */
function resolveInitialCountryCode(
  supplier: SupplierDetail,
): string | null {
  if (supplier.country_code) return supplier.country_code;
  if (!supplier.country) return null;
  const match =
    findCountryByName(supplier.country, "ru") ??
    findCountryByName(supplier.country, "en");
  return match?.code ?? null;
}

export function TabOverview({ supplier }: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [name, setName] = useState(supplier.name);
  const [supplierCode, setSupplierCode] = useState(supplier.supplier_code ?? "");
  const [countryCode, setCountryCode] = useState<string | null>(() =>
    resolveInitialCountryCode(supplier),
  );
  const [city, setCity] = useState(supplier.city ?? "");
  const [registrationNumber, setRegistrationNumber] = useState(
    supplier.registration_number ?? ""
  );
  const [paymentTerms, setPaymentTerms] = useState(
    supplier.default_payment_terms ?? ""
  );
  const [notes, setNotes] = useState(supplier.notes ?? "");

  function handleCountryChange(next: string | null) {
    // When the editor picks a different country, the prior city is scoped to
    // the old country — clear it so CityAutocomplete can re-suggest under the
    // new country. Event-handler path is preferred over an effect so we don't
    // wipe the city on mount or when toggling into edit mode.
    setCountryCode(next);
    if (next !== countryCode) {
      setCity("");
    }
  }

  function resetForm() {
    setName(supplier.name);
    setSupplierCode(supplier.supplier_code ?? "");
    setCountryCode(resolveInitialCountryCode(supplier));
    setCity(supplier.city ?? "");
    setRegistrationNumber(supplier.registration_number ?? "");
    setPaymentTerms(supplier.default_payment_terms ?? "");
    setNotes(supplier.notes ?? "");
  }

  async function handleSave() {
    const countryRu = countryCode
      ? findCountryByCode(countryCode)?.nameRu ?? null
      : null;

    setSaving(true);
    try {
      await updateSupplier(supplier.id, {
        name,
        supplier_code: supplierCode,
        country: countryRu ?? "",
        country_code: countryCode ?? "",
        city,
        registration_number: registrationNumber,
        default_payment_terms: paymentTerms,
        notes,
      });
      setEditing(false);
      router.refresh();
    } catch (err) {
      console.error("[tab-overview] save failed:", err);
      toast.error(
        extractErrorMessage(err) ?? "Не удалось сохранить поставщика",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    resetForm();
    setEditing(false);
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Basic Info */}
        <Card>
          <CardHeader className="pb-3 flex flex-row items-center justify-between">
            <CardTitle className="text-base">Основная информация</CardTitle>
            {!editing && (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                <Pencil size={14} />
                Редактировать
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {editing ? (
              <div className="space-y-3">
                <Field label="Название" value={name} onChange={setName} required />
                <Field label="Код" value={supplierCode} onChange={setSupplierCode} placeholder="Краткий код" />
                <Field label="Рег. номер / VAT" value={registrationNumber} onChange={setRegistrationNumber} placeholder="VAT / Tax ID" />
                <Field label="Условия оплаты" value={paymentTerms} onChange={setPaymentTerms} placeholder="Условия оплаты по умолчанию" />
                <fieldset className="flex flex-col gap-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Комментарии
                  </Label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Заметки о поставщике"
                    rows={3}
                    className="w-full px-3 py-2 text-sm border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring resize-y"
                  />
                </fieldset>
                <div className="flex gap-2 pt-2">
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={saving || !name.trim()}
                    className="bg-accent text-white hover:bg-accent-hover"
                  >
                    <Save size={14} />
                    {saving ? "Сохранение..." : "Сохранить"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleCancel} disabled={saving}>
                    <X size={14} />
                    Отмена
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <Row label="Название" value={supplier.name} />
                <Row label="Код" value={supplier.supplier_code} />
                <Row label="Рег. номер / VAT" value={supplier.registration_number} />
                <Row label="Условия оплаты" value={supplier.default_payment_terms} />
                <Row label="Комментарии" value={supplier.notes} />
                <Row
                  label="Статус"
                  value={
                    <Badge variant={supplier.is_active ? "default" : "secondary"}>
                      {supplier.is_active ? "Активен" : "Неактивен"}
                    </Badge>
                  }
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Location */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Местоположение</CardTitle>
          </CardHeader>
          <CardContent>
            {editing ? (
              <div className="space-y-3">
                <fieldset className="flex flex-col gap-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Страна
                  </Label>
                  <CountryCombobox
                    value={countryCode}
                    onChange={handleCountryChange}
                    ariaLabel="Страна поставщика"
                  />
                </fieldset>
                <fieldset className="flex flex-col gap-1.5">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Город
                  </Label>
                  <CityAutocomplete
                    value={city}
                    onChange={setCity}
                    countryCode={countryCode}
                    ariaLabel="Город поставщика"
                  />
                </fieldset>
              </div>
            ) : (
              <div className="space-y-2 text-sm">
                <Row label="Страна" value={supplier.country} />
                <Row label="Город" value={supplier.city} />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Dates */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Даты</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <Row
            label="Создан"
            value={
              supplier.created_at
                ? new Date(supplier.created_at).toLocaleDateString("ru-RU")
                : null
            }
          />
          <Row
            label="Обновлён"
            value={
              supplier.updated_at
                ? new Date(supplier.updated_at).toLocaleDateString("ru-RU")
                : null
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}

function Row({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined | React.ReactNode;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span className="font-medium">
        {typeof value === "string" || value === null || value === undefined
          ? value ?? "—"
          : value}
      </span>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
        {label}
        {required && <span className="text-error"> *</span>}
      </Label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? label}
      />
    </fieldset>
  );
}
