"use client";

import dynamic from "next/dynamic";
import type { ProcurementEditorItem } from "./procurement-handsontable";

export type { ProcurementEditorItem } from "./procurement-handsontable";

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
  items: ProcurementEditorItem[];
  invoiceId: string;
  procurementCompleted: boolean;
  /**
   * Sales-side display columns (quote_items.product_code + product_name)
   * joined via invoice_item_coverage. Read-only in the handsontable.
   * Optional — empty map disables the columns gracefully.
   */
  salesByItemId?: Record<string, { product_code: string; product_name: string }>;
  /**
   * Per-row eligibility for the inline split action. Map key is the
   * invoice_item.id; value carries the source quote_item info needed to
   * open the split dialog. Rows missing from this map don't get the split
   * icon (i.e., they're already part of a split/merge or not 1:1).
   */
  splitableByItemId?: Record<
    string,
    {
      sourceQuoteItemId: string;
      sourceQuantity: number;
      sourceProductName: string;
    }
  >;
  /**
   * Per-row "this is a split child" info. Drives the inline ↪ undo-split
   * icon. Map key is the invoice_item.id; rows missing from this map
   * aren't part of a split.
   */
  splitChildByItemId?: Record<
    string,
    { sourceQuoteItemId: string; sourceProductName: string }
  >;
  /**
   * Per-row merge eligibility. Same 1:1 condition as splitableByItemId,
   * but ONLY populated when there are ≥ 2 such candidates total — a row
   * with no peer to merge with doesn't get the ⋃ icon.
   */
  mergeableByItemId?: Record<
    string,
    {
      sourceQuoteItemId: string;
      sourceProductName: string;
      sourceQuantity: number;
    }
  >;
  /**
   * Per-row "this is a merge result" map (covers ≥ 2 quote_items). Drives
   * the inline ↩ undo-merge icon.
   */
  mergeResultByItemId?: Record<string, true>;
  /** Fired when the user clicks the row's split icon. */
  onSplitRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's undo-split icon. */
  onUndoSplitRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's merge icon. */
  onMergeRow?: (invoiceItemId: string) => void;
  /** Fired when the user clicks the row's undo-merge icon. */
  onUndoMergeRow?: (invoiceItemId: string) => void;
}

export function ProcurementItemsEditor({
  items,
  invoiceId,
  procurementCompleted,
  salesByItemId,
  splitableByItemId,
  splitChildByItemId,
  mergeableByItemId,
  mergeResultByItemId,
  onSplitRow,
  onUndoSplitRow,
  onMergeRow,
  onUndoMergeRow,
}: ProcurementItemsEditorProps) {
  return (
    <ProcurementHandsontable
      items={items}
      invoiceId={invoiceId}
      procurementCompleted={procurementCompleted}
      salesByItemId={salesByItemId}
      splitableByItemId={splitableByItemId}
      splitChildByItemId={splitChildByItemId}
      mergeableByItemId={mergeableByItemId}
      mergeResultByItemId={mergeResultByItemId}
      onSplitRow={onSplitRow}
      onUndoSplitRow={onUndoSplitRow}
      onMergeRow={onMergeRow}
      onUndoMergeRow={onUndoMergeRow}
    />
  );
}
