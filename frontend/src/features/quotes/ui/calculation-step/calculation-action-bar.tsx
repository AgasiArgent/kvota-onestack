"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calculator, FileDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

interface CalculationActionBarProps {
  quoteId: string;
  formValues: Record<string, string>;
  hasCalculation: boolean;
}

export function CalculationActionBar({
  quoteId,
  formValues,
  hasCalculation,
}: CalculationActionBarProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleCalculate() {
    setLoading(true);
    try {
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { data: { session } } = await supabase.auth.getSession();

      const res = await fetch(`/api/quotes/${quoteId}/calculate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(session?.access_token ? { "Authorization": `Bearer ${session.access_token}` } : {}),
        },
        body: JSON.stringify(formValues),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Calculation failed");

      toast.success("Расчёт выполнен");
      router.refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Не удалось выполнить расчёт");
    } finally {
      setLoading(false);
    }
  }

  function handleExportPdf() {
    window.open(`/export/kp/${quoteId}`, "_blank");
  }

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-2">
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={handleCalculate}
        disabled={loading}
      >
        {loading ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Calculator size={14} />
        )}
        {hasCalculation ? "Пересчитать" : "Рассчитать"}
      </Button>

      {hasCalculation && (
        <Button size="sm" variant="outline" onClick={handleExportPdf}>
          <FileDown size={14} />
          КП PDF
        </Button>
      )}
    </div>
  );
}
