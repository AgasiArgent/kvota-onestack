"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calculator, FileDown, Loader2, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { config } from "@/shared/config";

interface CalculationActionBarProps {
  quoteId: string;
  formValues: Record<string, string>;
  hasCalculation: boolean;
  workflowStatus: string;
  isApproved: boolean;
}

export function CalculationActionBar({
  quoteId,
  formValues,
  hasCalculation,
  workflowStatus,
  isApproved,
}: CalculationActionBarProps) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);

  async function handleCalculate() {
    setLoading("calc");
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
      setLoading(null);
    }
  }

  async function handleSubmitToControl() {
    setLoading("control");
    try {
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { error } = await supabase
        .from("quotes")
        .update({ workflow_status: "pending_quote_control" })
        .eq("id", quoteId);
      if (error) throw error;
      toast.success("КП отправлено на контроль");
      router.refresh();
    } catch {
      toast.error("Не удалось отправить на контроль");
    } finally {
      setLoading(null);
    }
  }

  function handleExportPdf() {
    window.open(`/export/kp/${quoteId}`, "_blank");
  }

  function handleExportValidation() {
    window.open(`${config.legacyAppUrl}/quotes/${quoteId}/export/validation`, "_blank");
  }

  // Show "Передать на контроль" after calculation, before control
  const canSubmitToControl = hasCalculation && (
    workflowStatus === "calculated" ||
    workflowStatus === "pending_sales_review" ||
    workflowStatus === "procurement_complete"
  );

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-2">
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={handleCalculate}
        disabled={loading !== null}
      >
        {loading === "calc" ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Calculator size={14} />
        )}
        {hasCalculation ? "Пересчитать" : "Рассчитать"}
      </Button>

      {canSubmitToControl && (
        <Button
          size="sm"
          className="bg-green-600 text-white hover:bg-green-700"
          onClick={handleSubmitToControl}
          disabled={loading !== null}
        >
          {loading === "control" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <ArrowRight size={14} />
          )}
          Передать на контроль
        </Button>
      )}

      {hasCalculation && (
        <>
          <Button
            size="sm"
            variant="outline"
            onClick={handleExportPdf}
            disabled={!isApproved}
            title={!isApproved ? "Доступно после одобрения на контроле" : undefined}
          >
            <FileDown size={14} />
            КП PDF
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleExportValidation}
            disabled={!isApproved}
            title={!isApproved ? "Доступно после одобрения на контроле" : undefined}
          >
            <FileDown size={14} />
            Validation Excel
          </Button>
        </>
      )}
    </div>
  );
}
