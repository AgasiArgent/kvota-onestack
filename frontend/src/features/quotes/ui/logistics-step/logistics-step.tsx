"use client";

import { useMemo } from "react";
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

  function handleCompleteLogistics() {
    console.log("Complete logistics for quote:", quote.id);
  }

  return (
    <div className="flex-1 min-w-0">
      <LogisticsActionBar
        invoices={invoices}
        onCompleteLogistics={handleCompleteLogistics}
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
