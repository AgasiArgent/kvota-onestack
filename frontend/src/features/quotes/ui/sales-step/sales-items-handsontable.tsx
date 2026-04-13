"use client";

import { useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import type Handsontable from "handsontable";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  createQuoteItemsBatch,
  updateQuoteItem,
  deleteQuoteItem,
} from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

interface SalesItemsHandsontableProps {
  quoteId: string;
  items: QuoteItemRow[];
  currency: string;
}

/** Column field keys in display order */
const COLUMN_KEYS = [
  "brand",
  "product_code",
  "product_name",
  "quantity",
  "unit",
] as const;

interface RowData {
  id: string | null;
  brand: string;
  product_code: string;
  product_name: string;
  quantity: number | null;
  unit: string;
}

function itemToRow(item: QuoteItemRow): RowData {
  return {
    id: item.id,
    brand: item.brand ?? "",
    product_code: item.product_code ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    unit: item.unit ?? "",
  };
}

function emptyRow(): RowData {
  return {
    id: null,
    brand: "",
    product_code: "",
    product_name: "",
    quantity: null,
    unit: "",
  };
}

function hasContent(row: RowData): boolean {
  return !!(
    row.brand ||
    row.product_code ||
    row.product_name ||
    (row.quantity != null && row.quantity > 0) ||
    row.unit
  );
}

function rowToCreatePayload(row: RowData) {
  return {
    product_name: row.product_name || "",
    brand: row.brand || undefined,
    product_code: row.product_code || undefined,
    quantity: row.quantity != null && row.quantity > 0 ? row.quantity : 1,
    unit: row.unit || "шт",
  };
}

/** Ensure there's always one empty spare row at the bottom */
function ensureSpareRow(hot: Handsontable) {
  const rowCount = hot.countRows();
  if (rowCount === 0) {
    hot.alter("insert_row_below");
    return;
  }

  const lastRow = hot.getSourceDataAtRow(rowCount - 1) as RowData | undefined;
  if (lastRow && hasContent(lastRow)) {
    hot.alter("insert_row_below");
  }
}

export function SalesItemsHandsontable({
  quoteId,
  items,
}: SalesItemsHandsontableProps) {
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);

  // Track row IDs so we can map rows to DB records without re-renders
  const rowIdsRef = useRef<(string | null)[]>(items.map((i) => i.id));

  // Pending operations tracker to prevent duplicate saves
  const pendingOps = useRef(new Set<string>());

  const initialData = useMemo(() => {
    const rows = items.map(itemToRow);
    rows.push(emptyRow());
    return rows;
  }, [items]);

  // Keep rowIds in sync with initial data (including spare row)
  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const handleAfterChange = useCallback(
    (changes: Handsontable.CellChange[] | null, source: string) => {
      if (!changes || source === "loadData") return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      // Group changes by row
      const changedRows = new Map<number, Map<string, unknown>>();
      for (const [row, prop, , newVal] of changes) {
        const field =
          typeof prop === "number"
            ? COLUMN_KEYS[prop]
            : typeof prop === "string"
              ? prop
              : undefined;
        if (!field || field === "id") continue;

        if (!changedRows.has(row)) {
          changedRows.set(row, new Map());
        }
        changedRows.get(row)!.set(field, newVal);
      }

      // Split into (a) updates to existing rows, (b) new rows needing creation.
      // New rows are collected so we can batch-insert them in a single request
      // when more than one row was changed (typical for Ctrl-V paste). A single
      // batch avoids the race where parallel createQuoteItem calls all fetched
      // the same next `position` value (see commit 7a4cde8, FB-260403-095930-b42c).
      const newRowsToCreate: {
        rowIndex: number;
        payload: ReturnType<typeof rowToCreatePayload>;
      }[] = [];

      for (const [rowIndex, fieldChanges] of changedRows) {
        const rowId = rowIdsRef.current[rowIndex];
        const rowData = hot.getSourceDataAtRow(rowIndex) as
          | RowData
          | undefined;
        if (!rowData) continue;

        if (rowId) {
          // Existing row: update changed fields immediately.
          const updates: Record<string, unknown> = {};
          for (const [field, val] of fieldChanges) {
            if (field === "quantity") {
              const parsed = parseFloat(String(val));
              updates[field] = isNaN(parsed) || parsed <= 0 ? 1 : parsed;
            } else {
              updates[field] = val || null;
            }
          }

          const lockKey = `update-${rowId}`;
          if (pendingOps.current.has(lockKey)) continue;
          pendingOps.current.add(lockKey);

          updateQuoteItem(rowId, updates)
            .catch(() => toast.error("Не удалось сохранить"))
            .finally(() => pendingOps.current.delete(lockKey));
        } else if (hasContent(rowData)) {
          // New row. Require both Бренд and Артикул before persisting, matching
          // the "*" markers in the column headers — but queue the row regardless
          // of `source`. Previously we skipped all CopyPaste.paste sources here
          // and relied on a separate afterPaste hook; that hook silently dropped
          // pasted rows when any validation or state-sync edge case fired
          // (FB-260413-161304-7ac0). Handling paste via the same afterChange
          // path with batch-insert keeps one code path for both flows.
          if (!rowData.brand?.trim() || !rowData.product_code?.trim()) continue;

          const lockKey = `create-${rowIndex}`;
          if (pendingOps.current.has(lockKey)) continue;
          pendingOps.current.add(lockKey);

          newRowsToCreate.push({
            rowIndex,
            payload: rowToCreatePayload(rowData),
          });
        }
      }

      if (newRowsToCreate.length === 0) return;

      // One request for all new rows — atomic position assignment.
      createQuoteItemsBatch(
        quoteId,
        newRowsToCreate.map((r) => r.payload)
      )
        .then((created) => {
          for (let i = 0; i < created.length; i++) {
            const { rowIndex } = newRowsToCreate[i];
            rowIdsRef.current[rowIndex] = created[i].id;
            hot.setSourceDataAtCell(rowIndex, "id", created[i].id);
          }
          ensureSpareRow(hot);
          router.refresh();
        })
        .catch(() => {
          toast.error(
            newRowsToCreate.length === 1
              ? "Не удалось создать позицию"
              : "Не удалось сохранить позиции"
          );
        })
        .finally(() => {
          for (const { rowIndex } of newRowsToCreate) {
            pendingOps.current.delete(`create-${rowIndex}`);
          }
        });
    },
    [quoteId, router]
  );

  const handleAfterRemoveRow = useCallback(
    (
      index: number,
      amount: number,
      _physicalRows: number[],
      _source?: string
    ) => {
      const removedIds: string[] = [];
      for (let i = 0; i < amount; i++) {
        const id = rowIdsRef.current[index + i];
        if (id) removedIds.push(id);
      }

      rowIdsRef.current.splice(index, amount);

      for (const id of removedIds) {
        deleteQuoteItem(id)
          .then(() => {
            toast.success("Позиция удалена");
            router.refresh();
          })
          .catch(() => toast.error("Не удалось удалить позицию"));
      }

      const hot = hotRef.current?.hotInstance;
      if (hot) ensureSpareRow(hot);
    },
    [router]
  );

  const handleAfterCreateRow = useCallback(
    (index: number, amount: number) => {
      for (let i = 0; i < amount; i++) {
        rowIdsRef.current.splice(index + i, 0, null);
      }
    },
    []
  );

  function handleAddRow() {
    const hot = hotRef.current?.hotInstance;
    if (!hot) return;

    const rowCount = hot.countRows();
    hot.alter("insert_row_above", rowCount - 1);
  }

  return (
    <div>
      <div className="ht-theme-main">
        <HotTable
          ref={hotRef}
          data={initialData}
          licenseKey="non-commercial-and-evaluation"
          colHeaders={["Бренд *", "Артикул *", "Наименование", "Кол-во", "Ед."]}
          columns={[
            { data: "brand", type: "text", width: 120 },
            { data: "product_code", type: "text", width: 150 },
            { data: "product_name", type: "text", width: 300 },
            { data: "quantity", type: "numeric", width: 80 },
            {
              data: "unit",
              type: "dropdown",
              source: [
                "шт",
                "упак",
                "компл",
                "кг",
                "г",
                "т",
                "м",
                "мм",
                "см",
                "м²",
                "м³",
                "л",
                "мл",
              ],
              width: 80,
            },
          ]}
          rowHeaders={false}
          stretchH="all"
          autoWrapRow={true}
          autoWrapCol={true}
          manualColumnResize={true}
          contextMenu={[
            "row_above",
            "row_below",
            "---------",
            "remove_row",
            "---------",
            "copy",
            "cut",
          ]}
          minSpareRows={0}
          height="auto"
          afterChange={handleAfterChange}
          afterRemoveRow={handleAfterRemoveRow}
          afterCreateRow={handleAfterCreateRow}
          className="htLeft"
        />
      </div>

      <div className="px-4 py-3 border-t border-border">
        <Button variant="outline" size="sm" onClick={handleAddRow}>
          <Plus size={14} />
          Добавить позицию
        </Button>
      </div>
    </div>
  );
}
