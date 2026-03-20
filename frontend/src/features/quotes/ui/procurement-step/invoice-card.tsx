"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Paperclip } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ProcurementItemsEditor } from "./procurement-items-editor";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

type InvoiceExtras = {
  invoice_file_url?: string | null;
};

function ext<T>(row: unknown): T {
  return row as T;
}

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

interface InvoiceCardProps {
  invoice: QuoteInvoiceRow;
  items: QuoteItemRow[];
  defaultExpanded?: boolean;
}

export function InvoiceCard({
  invoice,
  items,
  defaultExpanded = false,
}: InvoiceCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";
  const totalAmount = items.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    return sum + price * item.quantity;
  }, 0);
  const currency = invoice.currency ?? "USD";
  const hasFile = ext<InvoiceExtras>(invoice).invoice_file_url != null;

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={16} className="shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight size={16} className="shrink-0 text-muted-foreground" />
        )}

        <span className="font-medium text-sm truncate">
          {invoice.invoice_number}
        </span>

        <span className="text-sm text-muted-foreground truncate">
          {supplierName}
        </span>

        <Badge variant="secondary" className="ml-auto shrink-0">
          {items.length} поз.
        </Badge>

        <span className="text-sm font-mono tabular-nums shrink-0">
          {numberFmt.format(totalAmount)} {currency}
        </span>

        {invoice.status && (
          <Badge variant="outline" className="shrink-0">
            {invoice.status}
          </Badge>
        )}

        {hasFile && (
          <Paperclip size={14} className="shrink-0 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-border overflow-x-auto">
          <ProcurementItemsEditor items={items} invoiceId={invoice.id} />
        </div>
      )}
    </Card>
  );
}

