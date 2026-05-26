"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calculator, FileDown, Loader2, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { downloadValidationExcel } from "@/features/quotes/lib/download-validation-excel";
import { isMarkupBelowMinimum } from "@/features/quotes/lib/markup";
import { extractErrorMessage } from "@/shared/lib/errors";

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
      if (!res.ok) {
        // Recoverable: backend returns MISSING_PRICES + items_without_price[].
        // Show a persistent, descriptive toast listing the failing items in
        // Russian so the user can act on it (the backend message is in EN).
        const errorCode =
          (data as { error?: { code?: unknown } } | null)?.error?.code;
        const itemsWithoutPrice = (data as { items_without_price?: unknown } | null)
          ?.items_without_price;
        if (
          errorCode === "MISSING_PRICES" &&
          Array.isArray(itemsWithoutPrice) &&
          itemsWithoutPrice.length > 0
        ) {
          const items = itemsWithoutPrice.filter(
            (it): it is string => typeof it === "string",
          );
          if (items.length > 0) {
            toast.error("Не у всех позиций есть цена", {
              description: `Без цены: ${items.join(", ")}`,
              duration: Infinity,
            });
            return;
          }
        }
        // Hard-stop markup guard (Testing 2 row 47). FE button is disabled
        // when markup < 5, but direct API callers / form-state edge cases
        // can still produce this response — surface a persistent toast in
        // Russian using the backend message (already localized).
        if (errorCode === "MARKUP_TOO_LOW") {
          const msg =
            extractErrorMessage(data) ?? "Наценка должна быть не менее 5%";
          toast.error(msg, { duration: Infinity });
          return;
        }
        // Testing 2 row 87 — every position is excluded (МОП refused or
        // customs banned). Backend already returns a localized message; we
        // just need to surface it persistently.
        if (errorCode === "NO_CALCULABLE_ITEMS") {
          const msg =
            extractErrorMessage(data) ??
            "Все позиции исключены из расчёта (нет в наличии или запрещены к ввозу)";
          toast.error(msg, { duration: Infinity });
          return;
        }
        throw new Error(extractErrorMessage(data) ?? "Calculation failed");
      }

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

  async function handleExportValidation() {
    await downloadValidationExcel(quoteId);
  }

  // Show "Передать на контроль" after calculation, before control
  const canSubmitToControl = hasCalculation && (
    workflowStatus === "calculated" ||
    workflowStatus === "pending_sales_review" ||
    workflowStatus === "procurement_complete"
  );

  // Hard stop: markup must be ≥ 5% (Testing 2 row 47). Mirrors the
  // MARKUP_TOO_LOW backend guard in api/quotes.py::calculate_quote.
  const markupBlocked = isMarkupBelowMinimum(formValues.markup);

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-2">
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={handleCalculate}
        disabled={loading !== null || markupBlocked}
        title={markupBlocked ? "Наценка не может быть меньше 5%" : undefined}
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
          >
            <FileDown size={14} />
            Validation Excel
          </Button>
        </>
      )}
    </div>
  );
}
