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
  // A position is "ready" when it either has a purchase price or is marked
  // unavailable (Н/Д) — unavailable items are excluded from the calculation
  // and intentionally have no price.
  const readyCount = items.filter(
    (i) => i.purchase_price_original != null || i.is_unavailable === true
  ).length;
  const incomplete = totalItems > 0 && readyCount < totalItems;

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
          disabled={completing}
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

      <span
        className={`ml-auto text-sm tabular-nums ${
          incomplete ? "text-warning font-medium" : "text-muted-foreground"
        }`}
      >
        {readyCount}/{totalItems} готово | {assignedCount} назначено
      </span>
    </div>
  );
}
