"use client";

import { useState, useMemo } from "react";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { ProcurementActionBar } from "./procurement-action-bar";
import { UnassignedItems } from "./unassigned-items";
import { InvoiceCard } from "./invoice-card";
import { InvoiceCreateModal } from "./invoice-create-modal";

interface ProcurementStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
}

export function ProcurementStep({
  items,
  invoices,
}: ProcurementStepProps) {
  const [createModalOpen, setCreateModalOpen] = useState(false);

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

  function handleCreateInvoice() {
    setCreateModalOpen(true);
  }

  function handleCompleteProcurement() {
    console.log("Complete procurement");
  }

  return (
    <div className="flex-1 min-w-0">
      <ProcurementActionBar
        items={items}
        onCreateInvoice={handleCreateInvoice}
        onCompleteProcurement={handleCompleteProcurement}
      />

      <div className="p-6 space-y-4">
        <UnassignedItems items={items} invoices={invoices} />

        {invoices.map((invoice, idx) => (
          <InvoiceCard
            key={invoice.id}
            invoice={invoice}
            items={invoiceItemsMap.get(invoice.id) ?? []}
            defaultExpanded={invoices.length === 1 && idx === 0}
          />
        ))}

        {invoices.length === 0 && items.every((i) => i.invoice_id != null) && (
          <div className="text-center py-12 text-muted-foreground">
            Нет инвойсов
          </div>
        )}
      </div>

      <InvoiceCreateModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        selectedItems={[]}
        suppliers={[]}
        buyerCompanies={[]}
      />
    </div>
  );
}
