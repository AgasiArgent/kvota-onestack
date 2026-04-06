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
  const [supplierCode, setSupplierCode] = useState("");
  const [country, setCountry] = useState("");
  const [city, setCity] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setSupplierCode("");
      setCountry("");
      setCity("");
      setRegistrationNumber("");
    }
  }, [open]);

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Введите название поставщика");
      return;
    }

    setSubmitting(true);
    try {
      const result = await createSupplier(orgId, {
        name: trimmedName,
        supplier_code: supplierCode.trim() || undefined,
        country: country.trim() || undefined,
        city: city.trim() || undefined,
        registration_number: registrationNumber.trim() || undefined,
      });

      onOpenChange(false);
      router.push(`/suppliers/${result.id}`);
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err);
      const message = raw.includes("row-level security")
        ? "Недостаточно прав для создания поставщика"
        : raw.includes("unique") || raw.includes("duplicate")
          ? "Поставщик с таким кодом уже существует"
          : "Ошибка создания поставщика";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Новый поставщик</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Название <span className="text-error">*</span>
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
              htmlFor="supplier-code"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Код
            </Label>
            <Input
              id="supplier-code"
              value={supplierCode}
              onChange={(e) => setSupplierCode(e.target.value)}
              placeholder="Краткий код (необязательно)"
            />
          </fieldset>

          <div className="grid grid-cols-2 gap-3">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="supplier-country"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Страна
              </Label>
              <Input
                id="supplier-country"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="Страна"
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="supplier-city"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Город
              </Label>
              <Input
                id="supplier-city"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="Город"
              />
            </fieldset>
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-reg-number"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Рег. номер / VAT
            </Label>
            <Input
              id="supplier-reg-number"
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
              Создать поставщика
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
