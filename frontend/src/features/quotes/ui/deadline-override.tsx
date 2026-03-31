"use client";

import { useState } from "react";
import { Pencil, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { createClient } from "@/shared/lib/supabase/client";

interface DeadlineOverrideProps {
  quoteId: string;
  currentOverrideHours: number | null;
  globalDeadlineHours: number | null;
}

export function DeadlineOverride({
  quoteId,
  currentOverrideHours,
  globalDeadlineHours,
}: DeadlineOverrideProps) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(
    currentOverrideHours?.toString() ?? ""
  );
  const [saving, setSaving] = useState(false);

  const effectiveDeadline = currentOverrideHours ?? globalDeadlineHours;

  async function handleSave() {
    setSaving(true);
    try {
      const supabase = createClient();
      const parsed = value.trim() === "" ? null : parseInt(value, 10);

      if (value.trim() !== "" && (isNaN(parsed!) || parsed! <= 0)) {
        return;
      }

      // stage_deadline_override_hours is from migration 238, not yet in generated types.
      // Use type assertion to pass the update through PostgREST.
      await supabase
        .from("quotes")
        .update({ stage_deadline_override_hours: parsed } as Record<string, unknown>)
        .eq("id", quoteId);

      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function handleCancel() {
    setValue(currentOverrideHours?.toString() ?? "");
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      handleCancel();
    }
  }

  if (editing) {
    return (
      <span className="inline-flex items-center gap-0.5 ml-1">
        <input
          type="number"
          min={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={globalDeadlineHours?.toString() ?? "48"}
          disabled={saving}
          className="w-10 h-4 rounded border border-input bg-transparent px-1 text-[10px] text-foreground outline-none focus:border-ring"
          autoFocus
        />
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="text-green-600 hover:text-green-700 disabled:opacity-50"
          aria-label="Сохранить"
        >
          <Check size={10} strokeWidth={3} />
        </button>
        <button
          type="button"
          onClick={handleCancel}
          className="text-muted-foreground hover:text-foreground"
          aria-label="Отмена"
        >
          <X size={10} strokeWidth={3} />
        </button>
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className={cn(
        "inline-flex items-center gap-0.5 ml-1 text-muted-foreground hover:text-foreground",
        "opacity-0 group-hover/step:opacity-100 transition-opacity"
      )}
      title={
        effectiveDeadline
          ? `Норматив: ${effectiveDeadline}ч${currentOverrideHours ? " (переопределено)" : ""}`
          : "Задать норматив"
      }
      aria-label="Изменить дедлайн"
    >
      <Pencil size={9} />
    </button>
  );
}
