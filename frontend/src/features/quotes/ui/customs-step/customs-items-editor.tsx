"use client";

import dynamic from "next/dynamic";
import type { QuoteItemRow } from "@/entities/quote/queries";

const CustomsHandsontable = dynamic(
  () =>
    import("./customs-handsontable").then((m) => ({
      default: m.CustomsHandsontable,
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

interface CustomsItemsEditorProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
  supplierByQuoteItemId: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >;
  userRoles: string[];
}

export function CustomsItemsEditor({
  items,
  invoiceCountryMap,
  supplierByQuoteItemId,
  userRoles,
}: CustomsItemsEditorProps) {
  return (
    <CustomsHandsontable
      items={items}
      invoiceCountryMap={invoiceCountryMap}
      supplierByQuoteItemId={supplierByQuoteItemId}
      userRoles={userRoles}
    />
  );
}
