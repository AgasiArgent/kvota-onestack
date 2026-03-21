"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calculator, FileDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { config } from "@/shared/config";

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

  function handleCalculate() {
    // Open Python calculation page — it has its own session auth
    // When user completes calculation there and returns, page refreshes
    const calcUrl = `${config.legacyAppUrl}/quotes/${quoteId}?tab=overview`;
    const popup = window.open(calcUrl, "calculate", "width=1200,height=800");

    // Poll for popup close, then refresh data
    if (popup) {
      const interval = setInterval(() => {
        if (popup.closed) {
          clearInterval(interval);
          router.refresh();
          toast.success("Данные обновлены");
        }
      }, 500);
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
