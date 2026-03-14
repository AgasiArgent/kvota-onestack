"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import type { CustomerContact } from "@/entities/customer";
import {
  createContact,
  updateContact,
  type ContactFormData,
} from "@/entities/customer/mutations";

interface ContactFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  customerId: string;
  contact?: CustomerContact;
}

const EMPTY_FORM: ContactFormData = {
  name: "",
  last_name: "",
  patronymic: "",
  position: "",
  email: "",
  phone: "",
  is_signatory: false,
  is_primary: false,
  is_lpr: false,
  notes: "",
};

function contactToFormData(contact: CustomerContact): ContactFormData {
  return {
    name: contact.name,
    last_name: contact.last_name ?? "",
    patronymic: contact.patronymic ?? "",
    position: contact.position ?? "",
    email: contact.email ?? "",
    phone: contact.phone ?? "",
    is_signatory: contact.is_signatory,
    is_primary: contact.is_primary,
    is_lpr: contact.is_lpr,
    notes: contact.notes ?? "",
  };
}

export function ContactFormModal({
  open,
  onClose,
  onSaved,
  customerId,
  contact,
}: ContactFormModalProps) {
  const router = useRouter();
  const isEditing = !!contact;

  const [form, setForm] = useState<ContactFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(contact ? contactToFormData(contact) : EMPTY_FORM);
      setError(null);
    }
  }, [open, contact]);

  function updateField<K extends keyof ContactFormData>(
    key: K,
    value: ContactFormData[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!form.name.trim()) {
      setError("Имя обязательно для заполнения");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      if (isEditing) {
        await updateContact(contact.id, form);
      } else {
        await createContact(customerId, form);
      }
      router.refresh();
      onSaved();
      onClose();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Ошибка при сохранении";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEditing ? "Редактировать контакт" : "Новый контакт"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Name (required) */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contact-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Имя <span className="text-error">*</span>
            </Label>
            <Input
              id="contact-name"
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
              placeholder="Имя"
              autoFocus
            />
          </fieldset>

          {/* Last name + Patronymic row */}
          <div className="grid grid-cols-2 gap-3">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="contact-last-name"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Фамилия
              </Label>
              <Input
                id="contact-last-name"
                value={form.last_name ?? ""}
                onChange={(e) => updateField("last_name", e.target.value)}
                placeholder="Фамилия"
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="contact-patronymic"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Отчество
              </Label>
              <Input
                id="contact-patronymic"
                value={form.patronymic ?? ""}
                onChange={(e) => updateField("patronymic", e.target.value)}
                placeholder="Отчество"
              />
            </fieldset>
          </div>

          {/* Position */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contact-position"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Должность
            </Label>
            <Input
              id="contact-position"
              value={form.position ?? ""}
              onChange={(e) => updateField("position", e.target.value)}
              placeholder="Должность"
            />
          </fieldset>

          {/* Email + Phone row */}
          <div className="grid grid-cols-2 gap-3">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="contact-email"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Email
              </Label>
              <Input
                id="contact-email"
                type="email"
                value={form.email ?? ""}
                onChange={(e) => updateField("email", e.target.value)}
                placeholder="email@example.com"
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="contact-phone"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Телефон
              </Label>
              <Input
                id="contact-phone"
                type="tel"
                value={form.phone ?? ""}
                onChange={(e) => updateField("phone", e.target.value)}
                placeholder="+7 (999) 123-45-67"
              />
            </fieldset>
          </div>

          {/* Notes */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="contact-notes"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Заметки
            </Label>
            <Textarea
              id="contact-notes"
              value={form.notes ?? ""}
              onChange={(e) => updateField("notes", e.target.value)}
              placeholder="Дополнительная информация"
              rows={2}
            />
          </fieldset>

          {/* Checkboxes */}
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_primary ?? false}
                onChange={(e) => updateField("is_primary", e.target.checked)}
                className="size-4 rounded accent-accent"
              />
              <span className="text-text">Основной контакт</span>
            </label>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_lpr ?? false}
                onChange={(e) => updateField("is_lpr", e.target.checked)}
                className="size-4 rounded accent-accent"
              />
              <span className="text-text">ЛПР</span>
            </label>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_signatory ?? false}
                onChange={(e) => updateField("is_signatory", e.target.checked)}
                className="size-4 rounded accent-accent"
              />
              <span className="text-text">Подписант</span>
            </label>
          </div>

          {/* Error message */}
          {error && (
            <p className="text-xs text-error">{error}</p>
          )}

          {/* Footer */}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={saving}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              disabled={saving}
              className="bg-accent text-white hover:bg-accent-hover"
            >
              {saving && <Loader2 className="animate-spin" />}
              Сохранить
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
