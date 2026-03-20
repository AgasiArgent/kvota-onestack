"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import type { QuoteItemRow } from "@/entities/quote/queries";

interface SalesItemsEditorProps {
  quoteId: string;
  items: QuoteItemRow[];
  currency: string;
}

const SalesItemsHandsontable = dynamic(
  () =>
    import("./sales-items-handsontable").then(
      (mod) => mod.SalesItemsHandsontable
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
        <Loader2 size={16} className="animate-spin" />
        Загрузка редактора...
      </div>
    ),
  }
);

export function SalesItemsEditor({
  quoteId,
  items,
  currency,
}: SalesItemsEditorProps) {
  return (
    <SalesItemsHandsontable
      quoteId={quoteId}
      items={items}
      currency={currency}
    />
  );
}
