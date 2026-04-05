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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, Plus, X } from "lucide-react";
import type { CustomerContact, PhoneEntry } from "@/entities/customer";
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

const PHONE_LABELS = [
  { value: "основной", label: "Основной" },
  { value: "рабочий", label: "Рабочий" },
  { value: "мобильный", label: "Мобильный" },
  { value: "добавочный", label: "Добавочный" },
];

function emptyPhone(): PhoneEntry {
  return { number: "", ext: null, label: "основной" };
}

interface FormState {
  name: string;
  last_name: string;
  patronymic: string;
  position: string;
  email: string;
  phones: PhoneEntry[];
  is_signatory: boolean;
  is_primary: boolean;
  is_lpr: boolean;
  notes: string;
}

const EMPTY_FORM: FormState = {
  name: "",
  last_name: "",
  patronymic: "",
  position: "",
  email: "",
  phones: [emptyPhone()],
  is_signatory: false,
  is_primary: false,
  is_lpr: false,
  notes: "",
};

function contactToFormState(contact: CustomerContact): FormState {
  let phones: PhoneEntry[];
  if (contact.phones && contact.phones.length > 0) {
    phones = contact.phones.map((p) => ({ ...p }));
  } else if (contact.phone) {
    phones = [{ number: contact.phone, ext: null, label: "основной" }];
  } else {
    phones = [emptyPhone()];
  }

  return {
    name: contact.name,
    last_name: contact.last_name ?? "",
    patronymic: contact.patronymic ?? "",
    position: contact.position ?? "",
    email: contact.email ?? "",
    phones,
    is_signatory: contact.is_signatory,
    is_primary: contact.is_primary,
    is_lpr: contact.is_lpr,
    notes: contact.notes ?? "",
  };
}

function formStateToContactData(form: FormState): ContactFormData {
  const phones = form.phones.filter((p) => p.number.trim() !== "");
  return {
    name: form.name,
    last_name: form.last_name || undefined,
    patronymic: form.patronymic || undefined,
    position: form.position || undefined,
    email: form.email || undefined,
    phone: phones[0]?.number ?? "",
    phones,
    is_signatory: form.is_signatory,
    is_primary: form.is_primary,
    is_lpr: form.is_lpr,
    notes: form.notes || undefined,
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

  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(contact ? contactToFormState(contact) : EMPTY_FORM);
      setError(null);
    }
  }, [open, contact]);

  function updateField<K extends keyof FormState>(
    key: K,
    value: FormState[K]
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updatePhone(index: number, field: keyof PhoneEntry, value: string | null) {
    setForm((prev) => ({
      ...prev,
      phones: prev.phones.map((p, i) =>
        i === index ? { ...p, [field]: value } : p
      ),
    }));
  }

  function addPhone() {
    setForm((prev) => ({
      ...prev,
      phones: [...prev.phones, emptyPhone()],
    }));
  }

  function removePhone(index: number) {
    setForm((prev) => ({
      ...prev,
      phones: prev.phones.filter((_, i) => i !== index),
    }));
  }

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!form.name.trim()) {
      setError("Имя обязательно для заполнения");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const data = formStateToContactData(form);
      if (isEditing) {
        await updateContact(contact.id, data);
      } else {
        await createContact(customerId, data);
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
                value={form.last_name}
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
                value={form.patronymic}
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
              value={form.position}
              onChange={(e) => updateField("position", e.target.value)}
              placeholder="Должность"
            />
          </fieldset>

          {/* Email */}
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
              value={form.email}
              onChange={(e) => updateField("email", e.target.value)}
              placeholder="email@example.com"
            />
          </fieldset>

          {/* Phones */}
          <fieldset className="flex flex-col gap-1.5">
            <Label className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Телефоны
            </Label>
            <div className="space-y-2">
              {form.phones.map((phone, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <Input
                    type="tel"
                    value={phone.number}
                    onChange={(e) => updatePhone(idx, "number", e.target.value)}
                    placeholder="+7 (999) 123-45-67"
                    className="flex-1"
                  />
                  <Input
                    value={phone.ext ?? ""}
                    onChange={(e) =>
                      updatePhone(idx, "ext", e.target.value || null)
                    }
                    placeholder="Доб."
                    className="w-20"
                  />
                  <Select
                    value={phone.label}
                    onValueChange={(val) => updatePhone(idx, "label", val)}
                  >
                    <SelectTrigger className="w-[130px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PHONE_LABELS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {form.phones.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removePhone(idx)}
                      className="p-1 rounded hover:bg-sidebar text-text-subtle hover:text-error"
                      title="Удалить телефон"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={addPhone}
              className="self-start mt-1 text-accent"
            >
              <Plus size={14} />
              Добавить телефон
            </Button>
          </fieldset>

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
              value={form.notes}
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
                checked={form.is_primary}
                onChange={(e) => updateField("is_primary", e.target.checked)}
                className="size-4 rounded accent-accent"
              />
              <span className="text-text">Основной контакт</span>
            </label>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_lpr}
                onChange={(e) => updateField("is_lpr", e.target.checked)}
                className="size-4 rounded accent-accent"
              />
              <span className="text-text">ЛПР</span>
            </label>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={form.is_signatory}
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
