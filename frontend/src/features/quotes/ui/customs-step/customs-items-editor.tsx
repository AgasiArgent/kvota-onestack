"use client";

import dynamic from "next/dynamic";
import type { QuoteItemRow } from "@/entities/quote/queries";
import type { CustomsAutofillSuggestion } from "@/features/customs-autofill";

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
  },
);

interface CustomsItemsEditorProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
  supplierByQuoteItemId: Map<
    string,
    { supplier_country: string | null; invoice_id: string | null }
  >;
  userRoles: string[];
  autofillSuggestions?: CustomsAutofillSuggestion[];
  onSelectRow?: (rowId: string | null) => void;
  onExpandRow?: (rowId: string) => void;
}

export function CustomsItemsEditor({
  items,
  invoiceCountryMap,
  supplierByQuoteItemId,
  userRoles,
  autofillSuggestions,
  onSelectRow,
  onExpandRow,
}: CustomsItemsEditorProps) {
  return (
    <CustomsHandsontable
      items={items}
      invoiceCountryMap={invoiceCountryMap}
      supplierByQuoteItemId={supplierByQuoteItemId}
      userRoles={userRoles}
      autofillSuggestions={autofillSuggestions}
      onSelectRow={onSelectRow}
      onExpandRow={onExpandRow}
    />
  );
}
