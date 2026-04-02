"use client";

import { Plus, CheckCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { QuoteItemRow } from "@/entities/quote/queries";

interface ProcurementActionBarProps {
  items: QuoteItemRow[];
  onCreateInvoice: () => void;
  onCompleteProcurement: () => void;
  completing?: boolean;
  procurementCompleted?: boolean;
}

export function ProcurementActionBar({
  items,
  onCreateInvoice,
  onCompleteProcurement,
  completing = false,
  procurementCompleted = false,
}: ProcurementActionBarProps) {
  const totalItems = items.length;
  const assignedCount = items.filter((i) => i.invoice_id != null).length;
  const pricedCount = items.filter(
    (i) => i.purchase_price_original != null
  ).length;

  const allPriced = totalItems > 0 && pricedCount === totalItems;

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={onCreateInvoice}
        disabled={procurementCompleted}
      >
        <Plus size={14} />
        Создать инвойс
      </Button>

      {procurementCompleted ? (
        <span className="inline-flex items-center gap-1.5 text-sm text-success font-medium">
          <CheckCircle size={14} />
          Закупка завершена
        </span>
      ) : (
        <Button
          size="sm"
          className="bg-success text-white hover:bg-success/90"
          disabled={!allPriced || completing}
          onClick={onCompleteProcurement}
        >
          {completing ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <CheckCircle size={14} />
          )}
          Закупка завершена
        </Button>
      )}

      <span className="ml-auto text-sm text-muted-foreground tabular-nums">
        {pricedCount}/{totalItems} оценено | {assignedCount} назначено
      </span>
    </div>
  );
}
