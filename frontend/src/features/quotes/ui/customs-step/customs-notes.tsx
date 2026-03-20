"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/shared/lib/supabase/client";

interface CustomsNotesProps {
  quoteId: string;
  initialNotes: string;
}

export function CustomsNotes({ quoteId, initialNotes }: CustomsNotesProps) {
  const router = useRouter();
  const [notes, setNotes] = useState(initialNotes);

  const saveNotes = useCallback(async () => {
    const supabase = createClient();
    try {
      await supabase
        .from("quotes")
        .update({ customs_notes: notes } as Record<string, unknown>)
        .eq("id", quoteId);
      router.refresh();
    } catch {
      toast.error("Не удалось сохранить примечания");
    }
  }, [notes, quoteId, router]);

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Примечания
      </h4>
      <textarea
        className="w-full min-h-[80px] px-3 py-2 text-sm border border-border rounded-md bg-background resize-vertical focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        onBlur={saveNotes}
        placeholder="Примечания таможенника"
        rows={3}
      />
    </div>
  );
}
