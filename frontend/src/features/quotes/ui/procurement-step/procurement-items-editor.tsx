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
}

export function ProcurementItemsEditor({
  items,
  invoiceId,
}: ProcurementItemsEditorProps) {
  return <ProcurementHandsontable items={items} invoiceId={invoiceId} />;
}
