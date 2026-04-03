"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { createContact } from "@/entities/customer/mutations";

interface AddContactFormProps {
  customerId: string;
  onCreated: (contact: { id: string; name: string }) => void;
  onCancel: () => void;
}

export function AddContactForm({
  customerId,
  onCreated,
  onCancel,
}: AddContactFormProps) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [position, setPosition] = useState("");
  const [nameError, setNameError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError(true);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const contact = await createContact(customerId, {
        name: trimmedName,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
        position: position.trim() || undefined,
      });

      onCreated({ id: contact.id, name: contact.name });
    } catch {
      setError("Не удалось создать контакт");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-3 space-y-2">
      <div>
        <label className="block text-xs text-muted-foreground mb-0.5">
          Имя <span className="text-destructive">*</span>
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (nameError) setNameError(false);
          }}
          className={`w-full rounded-md border bg-transparent px-2 py-1 text-sm outline-none focus:border-ring ${
            nameError ? "border-destructive" : "border-input"
          }`}
          autoFocus
        />
        {nameError && (
          <p className="text-xs text-destructive mt-0.5">Обязательное поле</p>
        )}
      </div>

      <div>
        <label className="block text-xs text-muted-foreground mb-0.5">
          Телефон
        </label>
        <input
          type="text"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
        />
      </div>

      <div>
        <label className="block text-xs text-muted-foreground mb-0.5">
          Email
        </label>
        <input
          type="text"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
        />
      </div>

      <div>
        <label className="block text-xs text-muted-foreground mb-0.5">
          Должность
        </label>
        <input
          type="text"
          value={position}
          onChange={(e) => setPosition(e.target.value)}
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
        />
      </div>

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      <div className="flex items-center gap-2 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1 text-sm text-accent-foreground hover:bg-accent/90 disabled:opacity-50 transition-colors"
        >
          {saving && <Loader2 size={12} className="animate-spin" />}
          {saving ? "Сохранение..." : "Добавить"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-md px-3 py-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}
