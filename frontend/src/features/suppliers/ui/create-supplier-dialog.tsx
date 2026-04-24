"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { createSupplier } from "@/entities/supplier/mutations";
import { extractErrorMessage } from "@/shared/lib/errors";
import {
  CityAutocomplete,
  CountryCombobox,
  findCountryByCode,
} from "@/shared/ui/geo";

interface CreateSupplierDialogProps {
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateSupplierDialog({
  orgId,
  open,
  onOpenChange,
}: CreateSupplierDialogProps) {
  const router = useRouter();

  const [name, setName] = useState("");
  // Store ISO-2 code — the display name is derived via findCountryByCode.
  const [countryCode, setCountryCode] = useState<string | null>(null);
  const [city, setCity] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setCountryCode(null);
      setCity("");
      setRegistrationNumber("");
    }
  }, [open]);

  function handleCountryChange(next: string | null) {
    // Prior city selection is scoped to the prior country — clear on change
    // (REQ 2.1). Event-handler path avoids an effect that would trip the
    // set-state-in-effect lint rule.
    setCountryCode(next);
    if (next !== countryCode) {
      setCity("");
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Введите название поставщика");
      return;
    }

    const countryRu = countryCode
      ? findCountryByCode(countryCode)?.nameRu ?? null
      : null;

    setSubmitting(true);
    try {
      const result = await createSupplier(orgId, {
        name: trimmedName,
        country: countryRu ?? undefined,
        country_code: countryCode ?? undefined,
        city: city.trim() || undefined,
        registration_number: registrationNumber.trim() || undefined,
      });

      onOpenChange(false);
      router.push(`/suppliers/${result.id}`);
    } catch (err) {
      console.error("[create-supplier-dialog] create failed:", err);
      // UX niceties: surface common PG error classes in Russian. These text
      // matches are fragile to PG wording changes, so they're best-effort —
      // any miss falls through to extractErrorMessage which handles Postgrest
      // shape, then a final generic Russian fallback.
      const raw = err instanceof Error ? err.message : String(err);
      let message: string;
      if (raw.includes("row-level security")) {
        message = "Нет прав для создания поставщика";
      } else if (raw.includes("unique") || raw.includes("duplicate")) {
        message = "Поставщик с таким названием уже существует";
      } else {
        message =
          extractErrorMessage(err) ?? "Не удалось создать поставщика";
      }
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Новый поставщик</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Название
            </Label>
            <Input
              id="supplier-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название компании-поставщика"
              autoFocus
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-country"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Страна
            </Label>
            <CountryCombobox
              value={countryCode}
              onChange={handleCountryChange}
              ariaLabel="Страна поставщика"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-city"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Город
            </Label>
            <CityAutocomplete
              value={city}
              onChange={setCity}
              countryCode={countryCode}
              ariaLabel="Город поставщика"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-vat"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Рег. номер / VAT
            </Label>
            <Input
              id="supplier-vat"
              value={registrationNumber}
              onChange={(e) => setRegistrationNumber(e.target.value)}
              placeholder="VAT / Tax ID"
            />
          </fieldset>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={!name.trim() || submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              Создать
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
