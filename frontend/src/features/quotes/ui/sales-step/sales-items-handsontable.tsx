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
  createQuoteItem,
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
    unit: row.unit || undefined,
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

      for (const [rowIndex, fieldChanges] of changedRows) {
        const rowId = rowIdsRef.current[rowIndex];
        const rowData = hot.getSourceDataAtRow(rowIndex) as
          | RowData
          | undefined;
        if (!rowData) continue;

        if (rowId) {
          // Existing row: update changed fields
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
          // New row with content: create item
          const lockKey = `create-${rowIndex}`;
          if (pendingOps.current.has(lockKey)) continue;
          pendingOps.current.add(lockKey);

          createQuoteItem(quoteId, rowToCreatePayload(rowData))
            .then((created) => {
              rowIdsRef.current[rowIndex] = created.id;
              hot.setSourceDataAtCell(rowIndex, "id", created.id);
              ensureSpareRow(hot);
              router.refresh();
            })
            .catch(() => toast.error("Не удалось создать позицию"))
            .finally(() => pendingOps.current.delete(lockKey));
        }
      }
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

  const handleAfterPaste = useCallback(
    (data: unknown[][], coords: { startRow: number; endRow: number }[]) => {
      if (!data.length || !coords.length) return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      // afterChange fires per-cell before afterPaste.
      // Delay to let afterChange create individual rows first,
      // then batch-create any rows that afterChange skipped.
      setTimeout(() => {
        const { startRow, endRow } = coords[0];

        const createPromises: Promise<void>[] = [];

        for (let r = startRow; r <= endRow; r++) {
          const rowId = rowIdsRef.current[r];
          if (rowId) continue;

          const lockKey = `create-${r}`;
          if (pendingOps.current.has(lockKey)) continue;

          const rowData = hot.getSourceDataAtRow(r) as RowData | undefined;
          if (!rowData || !hasContent(rowData)) continue;

          pendingOps.current.add(lockKey);

          const promise = createQuoteItem(quoteId, rowToCreatePayload(rowData))
            .then((created) => {
              rowIdsRef.current[r] = created.id;
              hot.setSourceDataAtCell(r, "id", created.id);
            })
            .catch(() => {
              toast.error("Не удалось создать позицию");
            })
            .finally(() => pendingOps.current.delete(lockKey));

          createPromises.push(promise);
        }

        if (createPromises.length > 0) {
          Promise.all(createPromises).then(() => {
            ensureSpareRow(hot);
            router.refresh();
          });
        }
      }, 150);
    },
    [quoteId, router]
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
          colHeaders={["Бренд", "Артикул", "Наименование", "Кол-во", "Ед."]}
          columns={[
            { data: "brand", type: "text", width: 120 },
            { data: "product_code", type: "text", width: 150 },
            { data: "product_name", type: "text", width: 300 },
            { data: "quantity", type: "numeric", width: 80 },
            {
              data: "unit",
              type: "dropdown",
              source: ["шт", "упак", "кг", "м", "л", "компл"],
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
          afterPaste={handleAfterPaste}
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
