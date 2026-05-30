"use client";

import dynamic from "next/dynamic";
import type { QuoteItemRow } from "@/entities/quote/queries";
import type { CustomsAutofillSuggestion } from "@/features/customs-autofill";
import type { SupplierByQuoteItem } from "./customs-handsontable";

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
  supplierByQuoteItemId: Map<string, SupplierByQuoteItem>;
  userRoles: string[];
  autofillSuggestions?: CustomsAutofillSuggestion[];
  onSelectRow?: (rowId: string | null) => void;
  onExpandRow?: (rowId: string) => void;
  /** Ordered list of visible column keys — passed through to the table. */
  visibleColumns?: readonly string[];
  /**
   * Row 10 — OKSM digital → `name_ru` lookup so the read-only
   * «Страна происх.» column renders the Russian country name
   * (Китай) instead of the raw numeric code (156). Empty map =
   * fall back to digit.
   */
  oksmNameMap?: Map<number, string>;
  /**
   * Row 8 — synchronous optimistic patch callback. Invoked by HoT
   * inline edits (e.g. duty-mode chip) before the async server save
   * completes, so the dialog reseed sees the fresh value.
   */
  onItemPatched?: (rowId: string, patch: Partial<QuoteItemRow>) => void;
}

export function CustomsItemsEditor({
  items,
  invoiceCountryMap,
  supplierByQuoteItemId,
  userRoles,
  autofillSuggestions,
  onSelectRow,
  onExpandRow,
  visibleColumns,
  oksmNameMap,
  onItemPatched,
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
      visibleColumns={visibleColumns}
      oksmNameMap={oksmNameMap}
      onItemPatched={onItemPatched}
    />
  );
}
