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
import type { SupplierContact } from "@/entities/supplier/types";
import {
  createSupplierContact,
  updateSupplierContact,
  type SupplierContactFormData,
} from "@/entities/supplier/mutations";

interface ContactFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  supplierId: string;
  contact?: SupplierContact;
}

const EMPTY_FORM: SupplierContactFormData = {
  name: "",
  position: "",
  email: "",
  phone: "",
  is_primary: false,
  notes: "",
};

function contactToFormData(contact: SupplierContact): SupplierContactFormData {
  return {
    name: contact.name,
    position: contact.position ?? "",
    email: contact.email ?? "",
    phone: contact.phone ?? "",
    is_primary: contact.is_primary,
    notes: contact.notes ?? "",
  };
}

export function ContactFormModal({
  open,
  onClose,
  onSaved,
  supplierId,
  contact,
}: ContactFormModalProps) {
  const router = useRouter();
  const isEditing = !!contact;

  const [form, setForm] = useState<SupplierContactFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setForm(contact ? contactToFormData(contact) : EMPTY_FORM);
      setError(null);
    }
  }, [open, contact]);

  function updateField<K extends keyof SupplierContactFormData>(
    key: K,
    value: SupplierContactFormData[K]
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
        await updateSupplierContact(contact.id, form);
      } else {
        await createSupplierContact(supplierId, form);
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
              htmlFor="supplier-contact-name"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Имя <span className="text-error">*</span>
            </Label>
            <Input
              id="supplier-contact-name"
              value={form.name}
              onChange={(e) => updateField("name", e.target.value)}
              placeholder="Имя контактного лица"
              autoFocus
            />
          </fieldset>

          {/* Position */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-contact-position"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Должность
            </Label>
            <Input
              id="supplier-contact-position"
              value={form.position ?? ""}
              onChange={(e) => updateField("position", e.target.value)}
              placeholder="Должность"
            />
          </fieldset>

          {/* Email + Phone row */}
          <div className="grid grid-cols-2 gap-3">
            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="supplier-contact-email"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Email
              </Label>
              <Input
                id="supplier-contact-email"
                type="email"
                value={form.email ?? ""}
                onChange={(e) => updateField("email", e.target.value)}
                placeholder="email@example.com"
              />
            </fieldset>

            <fieldset className="flex flex-col gap-1.5">
              <Label
                htmlFor="supplier-contact-phone"
                className="text-xs font-semibold uppercase tracking-wide text-text-muted"
              >
                Телефон
              </Label>
              <Input
                id="supplier-contact-phone"
                type="tel"
                value={form.phone ?? ""}
                onChange={(e) => updateField("phone", e.target.value)}
                placeholder="+1 (555) 123-4567"
              />
            </fieldset>
          </div>

          {/* Notes */}
          <fieldset className="flex flex-col gap-1.5">
            <Label
              htmlFor="supplier-contact-notes"
              className="text-xs font-semibold uppercase tracking-wide text-text-muted"
            >
              Заметки
            </Label>
            <Textarea
              id="supplier-contact-notes"
              value={form.notes ?? ""}
              onChange={(e) => updateField("notes", e.target.value)}
              placeholder="Дополнительная информация"
              rows={2}
            />
          </fieldset>

          {/* Primary checkbox */}
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
