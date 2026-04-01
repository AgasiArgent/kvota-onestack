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
  userRoles: string[];
}

export function CustomsItemsEditor({
  items,
  invoiceCountryMap,
  userRoles,
}: CustomsItemsEditorProps) {
  return (
    <CustomsHandsontable
      items={items}
      invoiceCountryMap={invoiceCountryMap}
      userRoles={userRoles}
    />
  );
}
