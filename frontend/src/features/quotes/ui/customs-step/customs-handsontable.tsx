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

function ext<T>(row: unknown): T {
  return row as T;
}

type ItemExtras = {
  hs_code?: string | null;
  customs_duty?: number | null;
  license_ds_required?: boolean | null;
  license_ds_cost?: number | null;
  license_ss_required?: boolean | null;
  license_ss_cost?: number | null;
  license_sgr_required?: boolean | null;
  license_sgr_cost?: number | null;
};

const COLUMN_KEYS = [
  "position",
  "brand",
  "product_code",
  "product_name",
  "quantity",
  "supplier_country",
  "hs_code",
  "customs_duty",
  "license_ds_required",
  "license_ds_cost",
  "license_ss_required",
  "license_ss_cost",
  "license_sgr_required",
  "license_sgr_cost",
] as const;

interface RowData {
  id: string;
  position: number;
  brand: string;
  product_code: string;
  product_name: string;
  quantity: number | null;
  supplier_country: string;
  hs_code: string;
  customs_duty: number | null;
  license_ds_required: boolean;
  license_ds_cost: number | null;
  license_ss_required: boolean;
  license_ss_cost: number | null;
  license_sgr_required: boolean;
  license_sgr_cost: number | null;
}

function itemToRow(
  item: QuoteItemRow,
  invoiceCountryMap: Map<string, string>
): RowData {
  const extras = ext<ItemExtras>(item);
  const country =
    item.supplier_country ??
    (item.invoice_id ? invoiceCountryMap.get(item.invoice_id) ?? "" : "");

  return {
    id: item.id,
    position: item.position ?? 0,
    brand: item.brand ?? "",
    product_code: item.product_code ?? "",
    product_name: item.product_name ?? "",
    quantity: item.quantity,
    supplier_country: country,
    hs_code: extras.hs_code ?? "",
    customs_duty: extras.customs_duty ?? null,
    license_ds_required: extras.license_ds_required ?? false,
    license_ds_cost: extras.license_ds_cost ?? null,
    license_ss_required: extras.license_ss_required ?? false,
    license_ss_cost: extras.license_ss_cost ?? null,
    license_sgr_required: extras.license_sgr_required ?? false,
    license_sgr_cost: extras.license_sgr_cost ?? null,
  };
}

interface CustomsHandsontableProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
}

export function CustomsHandsontable({
  items,
  invoiceCountryMap,
}: CustomsHandsontableProps) {
  const router = useRouter();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const hotRef = useRef<any>(null);
  const pendingOps = useRef(new Set<string>());
  const rowIdsRef = useRef<string[]>(items.map((i) => i.id));

  const initialData = useMemo(
    () => items.map((item) => itemToRow(item, invoiceCountryMap)),
    [items, invoiceCountryMap]
  );

  if (rowIdsRef.current.length !== initialData.length) {
    rowIdsRef.current = initialData.map((r) => r.id);
  }

  const handleAfterChange = useCallback(
    (changes: Handsontable.CellChange[] | null, source: string) => {
      if (!changes || source === "loadData") return;

      const hot = hotRef.current?.hotInstance;
      if (!hot) return;

      const changedRows = new Map<number, Map<string, unknown>>();
      for (const [row, prop, , newVal] of changes) {
        const field =
          typeof prop === "number"
            ? COLUMN_KEYS[prop]
            : typeof prop === "string"
              ? prop
              : undefined;
        if (!field || field === "id" || field === "position") continue;

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
          if (field === "customs_duty") {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (
            field === "license_ds_cost" ||
            field === "license_ss_cost" ||
            field === "license_sgr_cost"
          ) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (
            field === "license_ds_required" ||
            field === "license_ss_required" ||
            field === "license_sgr_required"
          ) {
            updates[field] = Boolean(val);
          } else if (field === "hs_code") {
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
        Нет позиций для таможенного оформления
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
          "No",
          "Бренд",
          "Артикул",
          "Наименование",
          "Кол-во",
          "Страна",
          "Код ТН ВЭД",
          "Пошлина %",
          "ДС",
          "Ст-ть ДС",
          "СС",
          "Ст-ть СС",
          "СГР",
          "Ст-ть СГР",
        ]}
        columns={[
          { data: "position", type: "numeric", width: 30, readOnly: true },
          { data: "brand", type: "text", width: 55, readOnly: true },
          { data: "product_code", type: "text", width: 70, readOnly: true },
          { data: "product_name", type: "text", width: 130, readOnly: true },
          { data: "quantity", type: "numeric", width: 40, readOnly: true },
          { data: "supplier_country", type: "text", width: 65, readOnly: true },
          { data: "hs_code", type: "text", width: 85 },
          { data: "customs_duty", type: "numeric", width: 55, allowEmpty: true },
          { data: "license_ds_required", type: "checkbox", width: 30 },
          { data: "license_ds_cost", type: "numeric", width: 55, allowEmpty: true },
          { data: "license_ss_required", type: "checkbox", width: 30 },
          { data: "license_ss_cost", type: "numeric", width: 55, allowEmpty: true },
          { data: "license_sgr_required", type: "checkbox", width: 30 },
          { data: "license_sgr_cost", type: "numeric", width: 55, allowEmpty: true },
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
      <p className="text-xs text-muted-foreground mt-2 px-1">
        * Стоимость ДС, СС, СГР указана в рублях (RUB)
      </p>
    </div>
  );
}
