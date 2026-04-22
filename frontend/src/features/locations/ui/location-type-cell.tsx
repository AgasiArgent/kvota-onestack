"use client";

import { useTransition } from "react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { updateLocationType } from "@/entities/location/server-actions";
import type { LocationType } from "@/entities/location/ui/location-chip";

interface Props {
  locationId: string;
  type: LocationType;
  canEdit: boolean;
}

const TYPE_CONFIG: Record<LocationType, { label: string; className: string }> = {
  supplier: {
    label: "Поставщик",
    className: "bg-blue-50 text-blue-700 border-blue-200",
  },
  hub: {
    label: "Хаб",
    className: "bg-violet-50 text-violet-700 border-violet-200",
  },
  customs: {
    label: "Таможня",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  own_warehouse: {
    label: "Склад",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  client: {
    label: "Клиент",
    className: "bg-rose-50 text-rose-700 border-rose-200",
  },
};

const TYPE_OPTIONS: LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

/**
 * LocationTypeCell — read-only chip (non-editors) or inline `<select>`
 * (admins + head_of_*). Using a native select avoids popover plumbing
 * for a 5-option list and keeps the row height stable.
 */
export function LocationTypeCell({ locationId, type, canEdit }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const cfg = TYPE_CONFIG[type];

  if (!canEdit) {
    return (
      <span
        className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium ${cfg.className}`}
      >
        {cfg.label}
      </span>
    );
  }

  const handleChange = (next: LocationType) => {
    if (next === type) return;
    startTransition(async () => {
      try {
        await updateLocationType({ id: locationId, type: next });
        toast.success("Тип локации обновлён");
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : "Не удалось обновить тип",
        );
      }
    });
  };

  return (
    <select
      className={`rounded-sm border px-2 py-0.5 text-xs font-medium outline-none focus:ring-2 focus:ring-accent disabled:opacity-60 ${cfg.className}`}
      value={type}
      onChange={(e) => handleChange(e.target.value as LocationType)}
      disabled={isPending}
      aria-label="Тип локации"
    >
      {TYPE_OPTIONS.map((t) => (
        <option key={t} value={t}>
          {TYPE_CONFIG[t].label}
        </option>
      ))}
    </select>
  );
}
