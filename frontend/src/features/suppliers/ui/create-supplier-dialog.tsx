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

const COUNTRY_SUGGESTIONS = [
  "Россия", "Китай", "Турция", "Германия", "Италия", "Франция",
  "Испания", "Польша", "Литва", "Латвия", "Эстония", "Финляндия",
  "Швеция", "Норвегия", "Нидерланды", "Бельгия", "Австрия", "Чехия",
  "Болгария", "Румыния", "Великобритания", "Индия", "Южная Корея",
  "Япония", "Тайвань", "Вьетнам", "Индонезия", "Малайзия", "Таиланд",
  "ОАЭ", "Казахстан", "Узбекистан", "Беларусь", "Украина", "Грузия",
  "США", "Канада", "Бразилия", "Мексика", "Португалия", "Греция",
];

export function CreateSupplierDialog({
  orgId,
  open,
  onOpenChange,
}: CreateSupplierDialogProps) {
  const router = useRouter();

  const [name, setName] = useState("");
  const [country, setCountry] = useState("");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setCountry("");
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
        country: country.trim() || undefined,
        registration_number: registrationNumber.trim() || undefined,
      });

      onOpenChange(false);
      router.push(`/suppliers/${result.id}`);
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err);
      const message = raw.includes("row-level security")
        ? "Недостаточно прав для создания поставщика"
        : raw.includes("unique") || raw.includes("duplicate")
          ? "Поставщик с таким названием уже существует"
          : "Ошибка создания поставщика";
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
            <Input
              id="supplier-country"
              list="country-suggestions"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="Начните вводить..."
            />
            <datalist id="country-suggestions">
              {COUNTRY_SUGGESTIONS.map((c) => (
                <option key={c} value={c} />
              ))}
            </datalist>
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
