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
import { CityAutocomplete, CountryCombobox, findCountryByCode } from "@/shared/ui/geo";
import { SearchableCombobox } from "@/shared/ui/searchable-combobox";
import { createLocation } from "@/entities/location/server-actions";
import { extractErrorMessage } from "@/shared/lib/errors";
import type { LocationType } from "@/entities/location/ui/location-chip";

interface CreateLocationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface TypeOption {
  id: LocationType;
  label: string;
}

// Mirrors the 5-value CHECK constraint on kvota.locations.location_type
// (migration 287). Russian labels match the rest of the /locations page UI
// (filter dropdown, LocationTypeCell).
const TYPE_OPTIONS: readonly TypeOption[] = [
  { id: "supplier", label: "Поставщик" },
  { id: "hub", label: "Хаб" },
  { id: "customs", label: "Таможня" },
  { id: "own_warehouse", label: "Склад" },
  { id: "client", label: "Клиент" },
] as const;

export function CreateLocationDialog({
  open,
  onOpenChange,
}: CreateLocationDialogProps) {
  const router = useRouter();

  // Store ISO-2 code — the display name is derived via findCountryByCode at
  // submit time, mirroring the supplier-creation dialog.
  const [countryCode, setCountryCode] = useState<string | null>(null);
  const [city, setCity] = useState("");
  const [code, setCode] = useState("");
  const [locationType, setLocationType] = useState<LocationType>("hub");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setCountryCode(null);
      setCity("");
      setCode("");
      setLocationType("hub");
      setSubmitting(false);
    }
  }, [open]);

  function handleCountryChange(next: string | null) {
    // City is scoped to the prior country — clear when the country changes
    // to avoid orphaned city values (e.g. "Шанхай" left over after switching
    // to RU). Same pattern as create-supplier-dialog.tsx.
    setCountryCode(next);
    if (next !== countryCode) {
      setCity("");
    }
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!countryCode) {
      toast.error("Выберите страну");
      return;
    }
    const countryRu = findCountryByCode(countryCode)?.nameRu ?? null;
    if (!countryRu) {
      toast.error("Не удалось определить название страны");
      return;
    }

    setSubmitting(true);
    try {
      await createLocation({
        country: countryRu,
        city: city.trim() || undefined,
        code: code.trim() || undefined,
        location_type: locationType,
      });

      toast.success("Локация создана");
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err);
      let message: string;
      if (raw.includes("row-level security") || raw.includes("permission denied")) {
        message = "Нет прав для создания локации";
      } else if (raw.includes("unique") || raw.includes("duplicate")) {
        message = "Такая локация уже существует";
      } else {
        message = extractErrorMessage(err) ?? "Не удалось создать локацию";
      }
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit = countryCode !== null && !submitting;

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Новая локация</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="location-country"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Страна <span className="text-error">*</span>
            </Label>
            <CountryCombobox
              value={countryCode}
              onChange={handleCountryChange}
              ariaLabel="Страна локации"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="location-city"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Город
            </Label>
            <CityAutocomplete
              value={city}
              onChange={setCity}
              countryCode={countryCode}
              ariaLabel="Город локации"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="location-type"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Тип <span className="text-error">*</span>
            </Label>
            <SearchableCombobox
              value={locationType}
              onChange={(next) => {
                if (next) setLocationType(next as LocationType);
              }}
              items={TYPE_OPTIONS}
              getLabel={(item) => item.label}
              ariaLabel="Тип локации"
              clearable={false}
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="location-code"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Код
            </Label>
            <Input
              id="location-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="MSK / SH / SPB"
              maxLength={10}
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
              disabled={!canSubmit}
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
