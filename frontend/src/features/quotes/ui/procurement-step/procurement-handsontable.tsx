"use client";

import { useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import Handsontable from "handsontable";
import { toast } from "sonner";
import { updateQuoteItem } from "@/entities/quote/mutations";
import type { QuoteItemRow } from "@/entities/quote/queries";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

type ItemExtras = {
  dimension_height_mm?: number | null;
  dimension_width_mm?: number | null;
  dimension_length_mm?: number | null;
  vat_rate?: number | null;
  supplier_sku_note?: string | null;
};

function ext<T>(row: unknown): T {
  return row as T;
}



const COLUMN_KEYS = [
  "brand",
  "product_code",
  "supplier_sku",
  "product_name",
  "quantity",
  "purchase_price_original",
  "production_time_days",
  "weight_in_kg",
  "dimensions",
  "vat_rate",
  "supplier_sku_note",
] as const;

interface RowData {
  id: string;
  brand: string;
  product_code: string;
  supplier_sku: string;
  product_name: string;
  quantity: number | null;
  purchase_price_original: number | null;
  purchase_currency: string;
  production_time_days: number | null;
  weight_in_kg: number | null;
  dimensions: string;
  vat_rate: number | null;
  supplier_sku_note: string;
}

function formatDimensions(
  height: number | null | undefined,
  width: number | null | undefined,
  length: number | null | undefined
): string {
  if (height == null && width == null && length == null) return "";
  return `${height ?? 0}\u00D7${width ?? 0}\u00D7${length ?? 0}`;
}

function parseDimensions(
  value: string
): { height: number | null; width: number | null; length: number | null } {
  if (!value || !value.trim()) {
    return { height: null, width: null, length: null };
  }
  // Accept "H\u00D7W\u00D7L", "HxWxL", "H*W*L", "H W L"
  const parts = value.split(/[\u00D7xX*\s]+/).map((p) => {
    const n = parseFloat(p.trim());
    return isNaN(n) ? null : n;
  });
  return {
    height: parts[0] ?? null,
    width: parts[1] ?? null,
    length: parts[2] ?? null,
  };
}

function itemToRow(item: QuoteItemRow): RowData {
  const extras = ext<ItemExtras>(item);
  return {
    id: item.id,
    brand: item.brand ?? "",
    product_code: item.product_code ?? "",
    supplier_sku: item.supplier_sku ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    purchase_price_original: item.purchase_price_original ?? null,
    purchase_currency: item.purchase_currency ?? "",
    production_time_days: item.production_time_days ?? null,
    weight_in_kg: item.weight_in_kg ?? null,
    dimensions: formatDimensions(
      extras.dimension_height_mm,
      extras.dimension_width_mm,
      extras.dimension_length_mm
    ),
    vat_rate: extras.vat_rate ?? null,
    supplier_sku_note: extras.supplier_sku_note ?? "",
  };
}

interface ProcurementHandsontableProps {
  items: QuoteItemRow[];
  invoiceId: string;
  invoiceCurrency: string;
}

export function ProcurementHandsontable({
  items,
  invoiceCurrency,
}: ProcurementHandsontableProps) {
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);
  const pendingOps = useRef(new Set<string>());
  const rowIdsRef = useRef<string[]>(items.map((i) => i.id));

  const initialData = useMemo(
    () => items.map(itemToRow),
    [items]
  );

  // Keep rowIds in sync with items
  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const skuMismatchRenderer = useCallback(
    (
      instance: Handsontable,
      td: HTMLTableCellElement,
      row: number,
      col: number,
      prop: string | number,
      value: unknown,
      cellProperties: Handsontable.CellProperties
    ) => {
      // Use the default text renderer first
      Handsontable.renderers.TextRenderer(
        instance,
        td,
        row,
        col,
        prop,
        value,
        cellProperties
      );

      const idnSku = instance.getDataAtRowProp(row, "product_code") as string;
      const supplierSku = value as string;

      if (supplierSku && idnSku && supplierSku !== idnSku) {
        td.style.backgroundColor = "#fef3c7"; // amber-100
      }
    },
    []
  );

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
        if (!rowId) continue;

        const updates: Record<string, unknown> = {};

        for (const [field, val] of fieldChanges) {
          if (field === "dimensions") {
            // Parse "HxWxL" into three separate DB columns
            const dims = parseDimensions(String(val ?? ""));
            updates.dimension_height_mm = dims.height;
            updates.dimension_width_mm = dims.width;
            updates.dimension_length_mm = dims.length;
          } else if (
            field === "purchase_price_original" ||
            field === "weight_in_kg" ||
            field === "vat_rate" ||
            field === "production_time_days"
          ) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (field === "purchase_currency") {
            updates[field] = val || null;
          } else {
            // Text fields: supplier_sku, supplier_sku_note
            updates[field] = val || null;
          }
        }

        if (Object.keys(updates).length === 0) continue;

        const lockKey = `update-${rowId}`;
        if (pendingOps.current.has(lockKey)) continue;
        pendingOps.current.add(lockKey);

        updateQuoteItem(rowId, updates)
          .then(() => router.refresh())
          .catch(() => toast.error("Не удалось сохранить"))
          .finally(() => pendingOps.current.delete(lockKey));
      }
    },
    [router]
  );

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Нет позиций в этом инвойсе
      </div>
    );
  }

  return (
    <div className="ht-theme-main">
      <HotTable
        ref={hotRef}
        data={initialData}
        licenseKey="non-commercial-and-evaluation"
        colHeaders={[
          "Бренд",
          "Арт.(запрос)",
          "Арт.(произв.)",
          "Наименование",
          "Кол-во",
          "Цена",
          "Готовность",
          "Вес, кг",
          "Габариты",
          "НДС %",
          "Примечание",
        ]}
        columns={[
          { data: "brand", type: "text", width: 55, readOnly: true },
          { data: "product_code", type: "text", width: 70, readOnly: true },
          {
            data: "supplier_sku",
            type: "text",
            width: 70,
            renderer: skuMismatchRenderer,
          },
          { data: "product_name", type: "text", width: 120, readOnly: true },
          { data: "quantity", type: "numeric", width: 35, readOnly: true },
          { data: "purchase_price_original", type: "numeric", width: 55 },
          { data: "production_time_days", type: "numeric", width: 45 },
          { data: "weight_in_kg", type: "numeric", width: 45 },
          { data: "dimensions", type: "text", width: 60 },
          { data: "vat_rate", type: "numeric", width: 40 },
          { data: "supplier_sku_note", type: "text", width: 80 },
        ]}
        rowHeaders={false}
        stretchH="all"
        autoWrapRow={true}
        autoWrapCol={true}
        manualColumnResize={true}
        contextMenu={false}
        minSpareRows={0}
        height="auto"
        afterChange={handleAfterChange}
        className="htLeft"
      />
    </div>
  );
}
