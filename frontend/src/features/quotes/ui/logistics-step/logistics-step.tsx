"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { completeLogistics } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { LogisticsActionBar } from "./logistics-action-bar";
import { LogisticsInvoiceRow } from "./logistics-invoice-row";

interface LogisticsStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
}

export function LogisticsStep({
  quote,
  items,
  invoices,
}: LogisticsStepProps) {
  const router = useRouter();
  const [completing, setCompleting] = useState(false);

  const invoiceItemsMap = useMemo(() => {
    const map = new Map<string, QuoteItemRow[]>();
    for (const item of items) {
      if (item.invoice_id != null) {
        const existing = map.get(item.invoice_id) ?? [];
        existing.push(item);
        map.set(item.invoice_id, existing);
      }
    }
    return map;
  }, [items]);

  const deliveryCity = quote.delivery_city ?? null;

  async function handleCompleteLogistics() {
    setCompleting(true);
    try {
      await completeLogistics(quote.id);
      toast.success("Логистика завершена");
      router.refresh();
    } catch {
      toast.error("Не удалось завершить логистику");
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="flex-1 min-w-0">
      <LogisticsActionBar
        invoices={invoices}
        onCompleteLogistics={handleCompleteLogistics}
        completing={completing}
      />

      <div className="p-6 space-y-4">
        {invoices.map((invoice, idx) => (
          <LogisticsInvoiceRow
            key={invoice.id}
            invoice={invoice}
            items={invoiceItemsMap.get(invoice.id) ?? []}
            deliveryCity={deliveryCity}
            defaultExpanded={invoices.length === 1 && idx === 0}
          />
        ))}

        {invoices.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            Нет инвойсов для логистики. Сначала завершите закупку.
          </div>
        )}
      </div>
    </div>
  );
}
