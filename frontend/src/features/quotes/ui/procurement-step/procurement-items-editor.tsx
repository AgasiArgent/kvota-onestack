"use client";

import dynamic from "next/dynamic";
import type { QuoteItemRow } from "@/entities/quote/queries";

const ProcurementHandsontable = dynamic(
  () =>
    import("./procurement-handsontable").then((m) => ({
      default: m.ProcurementHandsontable,
    })),
  {
    ssr: false,
    loading: () => (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Загрузка...
      </div>
    ),
  }
);

interface ProcurementItemsEditorProps {
  items: QuoteItemRow[];
  invoiceId: string;
  invoiceCurrency: string;
  procurementCompleted: boolean;
}

export function ProcurementItemsEditor({
  items,
  invoiceId,
  invoiceCurrency,
  procurementCompleted,
}: ProcurementItemsEditorProps) {
  return (
    <ProcurementHandsontable
      items={items}
      invoiceId={invoiceId}
      invoiceCurrency={invoiceCurrency}
      procurementCompleted={procurementCompleted}
    />
  );
}
