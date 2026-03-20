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
      const body = new URLSearchParams(formValues).toString();
      const res = await fetch(`/proxy/calculate/${quoteId}`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      toast.success("Расчёт выполнен");
      router.refresh();
    } catch {
      toast.error("Не удалось выполнить расчёт");
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
