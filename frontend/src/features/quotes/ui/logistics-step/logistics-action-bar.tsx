"use client";

import { CheckCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";

interface LogisticsActionBarProps {
  invoices: QuoteInvoiceRow[];
  onCompleteLogistics: () => void;
  completing?: boolean;
}

export function LogisticsActionBar({
  invoices,
  onCompleteLogistics,
  completing = false,
}: LogisticsActionBarProps) {
  const totalInvoices = invoices.length;
  const routedCount = invoices.filter(
    (inv) =>
      inv.logistics_supplier_to_hub != null ||
      inv.logistics_hub_to_customs != null ||
      inv.logistics_customs_to_customer != null
  ).length;

  const allRouted = totalInvoices > 0 && routedCount === totalInvoices;

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      <Button
        size="sm"
        className="bg-success text-white hover:bg-success/90"
        disabled={!allRouted || completing}
        onClick={onCompleteLogistics}
      >
        {completing ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <CheckCircle size={14} />
        )}
        Логистика завершена
      </Button>

      <span className="ml-auto text-sm text-muted-foreground tabular-nums">
        {routedCount}/{totalInvoices} маршрутов заполнено
      </span>
    </div>
  );
}
