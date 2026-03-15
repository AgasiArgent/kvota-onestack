"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { PhmbVersion } from "@/entities/phmb-quote/types";
import { createPhmbVersion } from "@/entities/phmb-quote/mutations";

interface VersionPillsProps {
  quoteId: string;
  versions: PhmbVersion[];
  activeVersionId: string | null;
  currentTerms: {
    phmb_advance_pct: number;
    phmb_payment_days: number;
    phmb_markup_pct: number;
  };
  onSwitch: (version: PhmbVersion | null) => void;
  onCreate: (version: PhmbVersion) => void;
}

export function VersionPills({
  quoteId,
  versions,
  activeVersionId,
  currentTerms,
  onSwitch,
  onCreate,
}: VersionPillsProps) {
  const [isCreating, setIsCreating] = useState(false);

  async function handleCreateVersion() {
    setIsCreating(true);
    try {
      const newVersion = await createPhmbVersion(quoteId, currentTerms);
      onCreate(newVersion);
      toast.success(`Версия ${newVersion.label} создана.`);
    } catch {
      toast.error("Не удалось создать версию.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      {/* "Current" pill — the live quote terms (no version selected) */}
      <button
        type="button"
        onClick={() => onSwitch(null)}
        className={cn(
          "px-3 py-1 text-xs font-semibold rounded-md transition-colors",
          activeVersionId === null
            ? "bg-accent text-white"
            : "bg-surface-raised text-text-muted hover:text-text"
        )}
      >
        Текущая
      </button>

      {versions.map((v) => (
        <button
          key={v.id}
          type="button"
          onClick={() => onSwitch(v)}
          className={cn(
            "px-3 py-1 text-xs font-semibold rounded-md transition-colors",
            activeVersionId === v.id
              ? "bg-accent text-white"
              : "bg-surface-raised text-text-muted hover:text-text"
          )}
        >
          {v.label}
        </button>
      ))}

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0 text-text-muted hover:text-text"
        onClick={handleCreateVersion}
        disabled={isCreating}
      >
        <Plus size={14} />
      </Button>
    </div>
  );
}
