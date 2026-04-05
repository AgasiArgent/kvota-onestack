"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { createDeliveryAddress } from "@/entities/customer/mutations";

interface AddAddressFormProps {
  customerId: string;
  onCreated: (address: { id: string; address: string }) => void;
  onCancel: () => void;
}

export function AddAddressForm({
  customerId,
  onCreated,
  onCancel,
}: AddAddressFormProps) {
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addressTouched, setAddressTouched] = useState(false);

  const addressInvalid = addressTouched && !address.trim();

  async function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setAddressTouched(true);

    if (!address.trim()) return;

    setSaving(true);
    setError(null);

    try {
      const result = await createDeliveryAddress(customerId, {
        name: name.trim() || undefined,
        address: address.trim(),
      });
      onCreated({ id: result.id, address: result.address });
    } catch {
      setError("Не удалось сохранить адрес");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-2 p-2">
      <div>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Название (напр. Склад Москва)"
          className="w-full rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none focus:border-ring"
        />
      </div>
      <div>
        <input
          type="text"
          value={address}
          onChange={(e) => {
            setAddress(e.target.value);
            if (!addressTouched) setAddressTouched(true);
          }}
          placeholder="Адрес"
          className={cn(
            "w-full rounded-md border bg-transparent px-2 py-1 text-sm outline-none focus:border-ring",
            addressInvalid ? "border-destructive" : "border-input"
          )}
        />
        {addressInvalid && (
          <p className="mt-0.5 text-xs text-destructive">Обязательное поле</p>
        )}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={saving}
          className={cn(
            "rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground",
            "hover:bg-primary/90 disabled:opacity-50"
          )}
        >
          {saving ? (
            <span className="flex items-center gap-1">
              <Loader2 size={12} className="animate-spin" />
              Сохранение...
            </span>
          ) : (
            "Добавить"
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-md px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Отмена
        </button>
      </div>
    </form>
  );
}
