"use client";

import { useRef, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { HotTable } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import Handsontable from "handsontable";
import { toast } from "sonner";
import { updateInvoiceItem, unassignInvoiceItem } from "@/entities/quote/mutations";
import { isMoqViolation } from "./moq-warning";

import "handsontable/styles/handsontable.css";
import "handsontable/styles/ht-theme-main.css";

registerAllModules();

/**
 * Phase 5d Group 5 Appendix — supplier-side row shape bound by the editor.
 *
 * Mirrors the `kvota.invoice_items` columns the handsontable COLUMN_KEYS
 * read. Declared locally (and re-exported via `procurement-items-editor`)
 * so callers can type their rows without reaching into the handsontable
 * internals.
 */
export interface ProcurementEditorItem {
  id: string;
  invoice_id: string;
  position: number;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  purchase_price_original: number | null;
  purchase_currency: string;
  minimum_order_quantity: number | null;
  production_time_days: number | null;
  weight_in_kg: number | null;
  dimension_height_mm: number | null;
  dimension_width_mm: number | null;
  dimension_length_mm: number | null;
}

/**
 * Phase 5d Task 14 — column keys rebound to `invoice_items` schema.
 *
 * Post-migration 284 drops the following from `quote_items`:
 *   purchase_price_original, weight_in_kg, production_time_days,
 *   minimum_order_quantity, dimension_*_mm
 * The editor therefore binds these supplier-side keys to `invoice_items`.
 * Customer-side columns (product_code, manufacturer_product_name, name_en,
 * is_unavailable, supplier_sku_note) remain on quote_items but are NOT
 * exposed through this editor — the handsontable is supplier-side only.
 */
export const PROCUREMENT_COLUMN_KEYS = [
  "brand",
  "supplier_sku",
  "product_name",
  "quantity",
  "minimum_order_quantity",
  "purchase_price_original",
  "production_time_days",
  "weight_in_kg",
  "dimensions",
] as const;

// Back-compat alias for internal array math.
const COLUMN_KEYS = PROCUREMENT_COLUMN_KEYS;

interface RowData {
  id: string;
  brand: string;
  supplier_sku: string;
  product_name: string;
  quantity: number | null;
  minimum_order_quantity: number | null;
  purchase_price_original: number | null;
  purchase_currency: string;
  production_time_days: number | null;
  weight_in_kg: number | null;
  dimensions: string;
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

/**
 * Phase 5d Group 5 Appendix: rows are sourced from `invoice_items` (the
 * supplier side of the КП). The `items` prop is typed to the supplier-side
 * row shape so callers cannot accidentally pass customer-side quote_items.
 *
 * Fields read from the row map 1:1 onto `invoice_items` columns:
 *   brand, supplier_sku, product_name, quantity, purchase_price_original,
 *   purchase_currency, production_time_days, weight_in_kg,
 *   dimension_*_mm, minimum_order_quantity
 */
function itemToRow(item: ProcurementEditorItem): RowData {
  return {
    id: item.id,
    brand: item.brand ?? "",
    supplier_sku: item.supplier_sku ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    minimum_order_quantity: item.minimum_order_quantity ?? null,
    purchase_price_original: item.purchase_price_original ?? null,
    purchase_currency: item.purchase_currency ?? "",
    production_time_days: item.production_time_days ?? null,
    weight_in_kg: item.weight_in_kg ?? null,
    dimensions: formatDimensions(
      item.dimension_height_mm,
      item.dimension_width_mm,
      item.dimension_length_mm
    ),
  };
}

interface ProcurementHandsontableProps {
  items: ProcurementEditorItem[];
  invoiceId: string;
  procurementCompleted: boolean;
}

export function ProcurementHandsontable({
  items,
  procurementCompleted,
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

  const unassignRenderer = useCallback(
    (
      _instance: Handsontable,
      td: HTMLTableCellElement,
      row: number,
    ) => {
      td.innerHTML = "";
      td.style.textAlign = "center";
      td.style.verticalAlign = "middle";
      td.style.cursor = "pointer";
      td.style.padding = "0";

      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "✕";
      btn.title = "Убрать из КП";
      btn.style.cssText =
        "border:none;background:none;color:#a1a1aa;cursor:pointer;font-size:14px;padding:2px 6px;border-radius:4px;";
      btn.onmouseenter = () => { btn.style.color = "#dc2626"; btn.style.backgroundColor = "#fee2e2"; };
      btn.onmouseleave = () => { btn.style.color = "#a1a1aa"; btn.style.backgroundColor = "transparent"; };
      btn.onclick = (e) => {
        e.stopPropagation();
        const rowId = rowIdsRef.current[row];
        if (!rowId || pendingOps.current.has(`unassign-${rowId}`)) return;
        pendingOps.current.add(`unassign-${rowId}`);
        unassignInvoiceItem(rowId)
          .then(() => { toast.success("Позиция убрана из КП"); router.refresh(); })
          .catch(() => toast.error("Не удалось убрать позицию"))
          .finally(() => pendingOps.current.delete(`unassign-${rowId}`));
      };
      td.appendChild(btn);
    },
    [router]
  );

  const moqWarningRenderer = useCallback(
    (
      instance: Handsontable,
      td: HTMLTableCellElement,
      row: number,
      col: number,
      prop: string | number,
      value: unknown,
      cellProperties: Handsontable.CellProperties
    ) => {
      // Delegate formatting to the default numeric renderer first
      Handsontable.renderers.NumericRenderer(
        instance,
        td,
        row,
        col,
        prop,
        value,
        cellProperties
      );

      const quantity = instance.getDataAtRowProp(row, "quantity") as
        | number
        | null
        | undefined;
      const violated = isMoqViolation({
        quantity: quantity ?? null,
        min_order_quantity:
          typeof value === "number"
            ? value
            : value == null || value === ""
              ? null
              : Number(value),
      });

      if (violated) {
        td.classList.add("moq-warning");
        td.title = "Количество ниже минимального заказа поставщика";
      } else {
        td.classList.remove("moq-warning");
        td.removeAttribute("title");
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
            field === "production_time_days" ||
            field === "minimum_order_quantity"
          ) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (field === "purchase_currency") {
            updates[field] = val || null;
          } else {
            // Text fields: supplier_sku, product_name
            updates[field] = val || null;
          }
        }

        if (Object.keys(updates).length === 0) continue;

        const lockKey = `update-${rowId}`;
        if (pendingOps.current.has(lockKey)) continue;
        pendingOps.current.add(lockKey);

        updateInvoiceItem(rowId, updates)
          .then(() => router.refresh())
          .catch(() => toast.error("Не удалось сохранить"))
          .finally(() => pendingOps.current.delete(lockKey));
      }
    },
    [router]
  );

  const lockedColIndices = useMemo(() => {
    if (!procurementCompleted) return [];
    return [
      COLUMN_KEYS.indexOf("supplier_sku"),
      COLUMN_KEYS.indexOf("purchase_price_original"),
      COLUMN_KEYS.indexOf("production_time_days"),
    ];
  }, [procurementCompleted]);

  const cellsCallback = useCallback(
    (_row: number, col: number) => {
      if (lockedColIndices.includes(col)) {
        return { className: "locked-cell" };
      }
      return {};
    },
    [lockedColIndices]
  );

  if (items.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">
        Нет позиций в этом КП
      </div>
    );
  }

  return (
    <div className="ht-theme-main">
      <style>{`
        .locked-cell { background-color: var(--muted, #f4f4f5) !important; }
        .moq-warning { background-color: #fef3c7 !important; position: relative; }
        .moq-warning::after {
          content: "⚠";
          position: absolute;
          top: 2px;
          right: 4px;
          color: #b45309;
          font-size: 11px;
          line-height: 1;
          pointer-events: none;
        }
      `}</style>
      <HotTable
        ref={hotRef}
        data={initialData}
        licenseKey="non-commercial-and-evaluation"
        colHeaders={[
          "Бренд",
          "Арт.произ.",
          "Наименование",
          "Кол",
          "Мин. заказ",
          "Цена",
          "Срок, к.дн",
          "Вес, кг",
          "В×Ш×Д, мм",
          "",
        ]}
        columns={[
          { data: "brand", type: "text", width: 55, readOnly: true },
          {
            data: "supplier_sku",
            type: "text",
            width: 70,
            readOnly: procurementCompleted,
          },
          { data: "product_name", type: "text", width: 140, readOnly: true },
          { data: "quantity", type: "numeric", width: 35, readOnly: true },
          {
            data: "minimum_order_quantity",
            type: "numeric",
            width: 45,
            renderer: moqWarningRenderer,
          },
          { data: "purchase_price_original", type: "numeric", width: 55, readOnly: procurementCompleted },
          { data: "production_time_days", type: "numeric", width: 45, readOnly: procurementCompleted },
          { data: "weight_in_kg", type: "numeric", width: 45 },
          { data: "dimensions", type: "text", width: 60 },
          { data: "id", readOnly: true, width: 28, renderer: unassignRenderer },
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
        cells={procurementCompleted ? cellsCallback : undefined}
        className="htLeft"
      />
    </div>
  );
}
