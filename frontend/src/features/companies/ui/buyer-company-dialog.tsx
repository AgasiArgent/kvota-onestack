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
import { Checkbox } from "@/components/ui/checkbox";
import {
  createBuyerCompany,
  updateBuyerCompany,
  type BuyerCompanyFormData,
} from "../api/mutations";
import type { BuyerCompany } from "../model/types";

interface Props {
  orgId: string;
  /** When passed, the dialog opens in "edit" mode pre-filled from this row.
   *  When omitted, the dialog opens in "create" mode with empty fields. */
  initial?: BuyerCompany | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const EMPTY_FORM: BuyerCompanyFormData = {
  name: "",
  company_code: "",
  country: "",
  inn: "",
  kpp: "",
  ogrn: "",
  registration_address: "",
  general_director_name: "",
  general_director_position: "",
  is_active: true,
};

function fromBuyerCompany(row: BuyerCompany): BuyerCompanyFormData {
  return {
    name: row.name,
    company_code: row.company_code,
    country: row.country ?? "",
    inn: row.inn ?? "",
    kpp: row.kpp ?? "",
    ogrn: "",
    registration_address: "",
    general_director_name: "",
    general_director_position: "",
    is_active: row.is_active ?? true,
  };
}

export function BuyerCompanyDialog({
  orgId,
  initial,
  open,
  onOpenChange,
}: Props) {
  const router = useRouter();
  const isEdit = Boolean(initial);

  const [form, setForm] = useState<BuyerCompanyFormData>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  // Reset / hydrate form whenever the dialog opens. Edit mode mirrors the
  // selected row's visible columns (full enrichment fields like ОГРН live in
  // the row but aren't surfaced on the list endpoint, so we don't pre-fill
  // them — the user types them in if they want to change them).
  useEffect(() => {
    if (!open) return;
    setForm(initial ? fromBuyerCompany(initial) : EMPTY_FORM);
    setSubmitting(false);
  }, [open, initial]);

  function setField<K extends keyof BuyerCompanyFormData>(
    key: K,
    value: BuyerCompanyFormData[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const name = form.name.trim();
    const code = form.company_code.trim().toUpperCase();

    if (!name) {
      toast.error("Введите название юрлица");
      return;
    }
    if (!/^[A-Z]{3}$/.test(code)) {
      toast.error("Код должен быть 3 латинскими буквами (например, CMT)");
      return;
    }

    const payload: BuyerCompanyFormData = {
      name,
      company_code: code,
      country: form.country?.toString().trim() || null,
      inn: form.inn?.toString().trim() || null,
      kpp: form.kpp?.toString().trim() || null,
      ogrn: form.ogrn?.toString().trim() || null,
      registration_address:
        form.registration_address?.toString().trim() || null,
      general_director_name:
        form.general_director_name?.toString().trim() || null,
      general_director_position:
        form.general_director_position?.toString().trim() || null,
      is_active: form.is_active ?? true,
    };

    setSubmitting(true);
    try {
      if (isEdit && initial) {
        await updateBuyerCompany(initial.id, payload);
        toast.success("Юрлицо обновлено");
      } else {
        await createBuyerCompany(orgId, payload);
        toast.success("Юрлицо создано");
      }
      onOpenChange(false);
      router.refresh();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось сохранить юрлицо";
      if (message.includes("duplicate") || message.includes("unique")) {
        toast.error("Юрлицо с таким кодом уже существует в организации");
      } else if (
        message.includes("buyer_companies_code_format") ||
        message.includes("check constraint")
      ) {
        toast.error("Код должен быть 3 латинскими буквами (A-Z)");
      } else if (
        message.includes("row-level security") ||
        message.includes("permission denied")
      ) {
        toast.error(
          "Нет прав на изменение юрлица. Обратитесь к администратору."
        );
      } else {
        toast.error(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const title = isEdit ? "Редактировать юрлицо" : "Новое юрлицо-закупки";
  const submitLabel = isEdit ? "Сохранить" : "Создать юрлицо";

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onOpenChange(false)}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="buyer-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Название <span className="text-error">*</span>
            </Label>
            <Input
              id="buyer-name"
              value={form.name}
              onChange={(e) => setField("name", e.target.value)}
              placeholder="ООО «Компания»"
              autoFocus
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="buyer-code"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Код (3 латинские буквы) <span className="text-error">*</span>
            </Label>
            <Input
              id="buyer-code"
              value={form.company_code}
              onChange={(e) =>
                setField(
                  "company_code",
                  e.target.value.replace(/[^a-zA-Z]/g, "").toUpperCase().slice(0, 3)
                )
              }
              placeholder="CMT"
              maxLength={3}
              className="uppercase tracking-widest"
            />
          </fieldset>

          <div className="grid grid-cols-2 gap-4">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="buyer-inn"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                ИНН
              </Label>
              <Input
                id="buyer-inn"
                value={form.inn ?? ""}
                onChange={(e) =>
                  setField("inn", e.target.value.replace(/\D/g, "").slice(0, 12))
                }
                placeholder="10 или 12 цифр"
                inputMode="numeric"
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="buyer-kpp"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                КПП
              </Label>
              <Input
                id="buyer-kpp"
                value={form.kpp ?? ""}
                onChange={(e) =>
                  setField("kpp", e.target.value.replace(/\D/g, "").slice(0, 9))
                }
                placeholder="9 цифр"
                inputMode="numeric"
              />
            </fieldset>
          </div>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="buyer-ogrn"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              ОГРН
            </Label>
            <Input
              id="buyer-ogrn"
              value={form.ogrn ?? ""}
              onChange={(e) =>
                setField("ogrn", e.target.value.replace(/\D/g, "").slice(0, 13))
              }
              placeholder="13 цифр"
              inputMode="numeric"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="buyer-country"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Страна
            </Label>
            <Input
              id="buyer-country"
              value={form.country ?? ""}
              onChange={(e) => setField("country", e.target.value)}
              placeholder="Россия"
            />
          </fieldset>

          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="buyer-address"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Юридический адрес
            </Label>
            <Input
              id="buyer-address"
              value={form.registration_address ?? ""}
              onChange={(e) =>
                setField("registration_address", e.target.value)
              }
              placeholder="г. Москва, ..."
            />
          </fieldset>

          <div className="grid grid-cols-2 gap-4">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="buyer-director"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Руководитель
              </Label>
              <Input
                id="buyer-director"
                value={form.general_director_name ?? ""}
                onChange={(e) =>
                  setField("general_director_name", e.target.value)
                }
                placeholder="Иванов И.И."
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="buyer-director-position"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Должность
              </Label>
              <Input
                id="buyer-director-position"
                value={form.general_director_position ?? ""}
                onChange={(e) =>
                  setField("general_director_position", e.target.value)
                }
                placeholder="Генеральный директор"
              />
            </fieldset>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <Checkbox
              checked={form.is_active === true}
              onCheckedChange={(checked) =>
                setField("is_active", checked === true)
              }
            />
            <span className="text-sm text-text-secondary">Активна</span>
          </label>

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
              disabled={submitting}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
