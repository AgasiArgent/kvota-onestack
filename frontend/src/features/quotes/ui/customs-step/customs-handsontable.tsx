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
  customs_duty_per_kg?: number | null;
  customs_ds_sgr?: string | null;
  customs_util_fee?: number | null;
  customs_excise?: number | null;
  customs_psn_pts?: string | null;
  customs_notification?: string | null;
  customs_licenses?: string | null;
  customs_marking?: string | null;
  customs_eco_fee?: number | null;
  customs_honest_mark?: string | null;
  import_banned?: boolean | null;
  import_ban_reason?: string | null;
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
  "customs_duty_per_kg",
  "customs_ds_sgr",
  "customs_util_fee",
  "customs_excise",
  "customs_psn_pts",
  "customs_notification",
  "customs_licenses",
  "customs_marking",
  "customs_eco_fee",
  "customs_honest_mark",
  "import_banned",
  "import_ban_reason",
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
  customs_duty_per_kg: number | null;
  customs_ds_sgr: string;
  customs_util_fee: number | null;
  customs_excise: number | null;
  customs_psn_pts: string;
  customs_notification: string;
  customs_licenses: string;
  customs_marking: string;
  customs_eco_fee: number | null;
  customs_honest_mark: string;
  import_banned: boolean;
  import_ban_reason: string;
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
    customs_duty_per_kg: extras.customs_duty_per_kg ?? null,
    customs_ds_sgr: extras.customs_ds_sgr ?? "",
    customs_util_fee: extras.customs_util_fee ?? null,
    customs_excise: extras.customs_excise ?? null,
    customs_psn_pts: extras.customs_psn_pts ?? "",
    customs_notification: extras.customs_notification ?? "",
    customs_licenses: extras.customs_licenses ?? "",
    customs_marking: extras.customs_marking ?? "",
    customs_eco_fee: extras.customs_eco_fee ?? null,
    customs_honest_mark: extras.customs_honest_mark ?? "",
    import_banned: extras.import_banned ?? false,
    import_ban_reason: extras.import_ban_reason ?? "",
    license_ds_required: extras.license_ds_required ?? false,
    license_ds_cost: extras.license_ds_cost ?? null,
    license_ss_required: extras.license_ss_required ?? false,
    license_ss_cost: extras.license_ss_cost ?? null,
    license_sgr_required: extras.license_sgr_required ?? false,
    license_sgr_cost: extras.license_sgr_cost ?? null,
  };
}

const NUMERIC_FIELDS = new Set([
  "customs_duty",
  "customs_duty_per_kg",
  "customs_util_fee",
  "customs_excise",
  "customs_eco_fee",
  "license_ds_cost",
  "license_ss_cost",
  "license_sgr_cost",
]);

const BOOLEAN_FIELDS = new Set([
  "import_banned",
  "license_ds_required",
  "license_ss_required",
  "license_sgr_required",
]);

const TEXT_FIELDS = new Set([
  "hs_code",
  "customs_ds_sgr",
  "customs_psn_pts",
  "customs_notification",
  "customs_licenses",
  "customs_marking",
  "customs_honest_mark",
  "import_ban_reason",
]);

/** Column header with tooltip */
function headerWithTooltip(label: string, tooltip: string): string {
  return `<span title="${tooltip}">${label}</span>`;
}

interface CustomsHandsontableProps {
  items: QuoteItemRow[];
  invoiceCountryMap: Map<string, string>;
  userRoles: string[];
}

export function CustomsHandsontable({
  items,
  invoiceCountryMap,
  userRoles,
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
          if (NUMERIC_FIELDS.has(field)) {
            const parsed = parseFloat(String(val));
            updates[field] = isNaN(parsed) ? null : parsed;
          } else if (BOOLEAN_FIELDS.has(field)) {
            updates[field] = Boolean(val);
          } else if (TEXT_FIELDS.has(field)) {
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

  const canToggleBan = useMemo(
    () => userRoles.some((r) => ["customs", "admin"].includes(r)),
    [userRoles]
  );

  const numericTooltip = "Значение за единицу товара";

  const colHeaders = useMemo(
    () => [
      "No",
      "Бренд",
      "Артикул",
      "Наименование",
      "Кол-во",
      "Страна",
      "Код ТН ВЭД",
      headerWithTooltip("Пошлина %", numericTooltip),
      headerWithTooltip("Пошлина, $/кг", numericTooltip),
      "ДС/СС/СГР",
      headerWithTooltip("Утильсбор", numericTooltip),
      headerWithTooltip("Акциз", numericTooltip),
      "ПСН/ПТС",
      "Нотификация",
      "Лицензии",
      "Маркировка",
      headerWithTooltip("Экосбор", numericTooltip),
      "Честный знак",
      "Запрет ввоза",
      "Причина запрета",
      "ДС",
      headerWithTooltip("Ст-ть ДС", numericTooltip),
      "СС",
      headerWithTooltip("Ст-ть СС", numericTooltip),
      "СГР",
      headerWithTooltip("Ст-ть СГР", numericTooltip),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const columns: Handsontable.ColumnSettings[] = useMemo(
    () => [
      { data: "position", type: "numeric", width: 30, readOnly: true },
      { data: "brand", type: "text", width: 55, readOnly: true },
      { data: "product_code", type: "text", width: 70, readOnly: true },
      { data: "product_name", type: "text", width: 130, readOnly: true },
      { data: "quantity", type: "numeric", width: 40, readOnly: true },
      { data: "supplier_country", type: "text", width: 65, readOnly: true },
      { data: "hs_code", type: "text", width: 85 },
      { data: "customs_duty", type: "numeric", width: 55, allowEmpty: true },
      { data: "customs_duty_per_kg", type: "numeric", width: 80, allowEmpty: true },
      { data: "customs_ds_sgr", type: "text", width: 80 },
      { data: "customs_util_fee", type: "numeric", width: 70, allowEmpty: true },
      { data: "customs_excise", type: "numeric", width: 65, allowEmpty: true },
      { data: "customs_psn_pts", type: "text", width: 70 },
      { data: "customs_notification", type: "text", width: 90 },
      { data: "customs_licenses", type: "text", width: 80 },
      { data: "customs_marking", type: "text", width: 80 },
      { data: "customs_eco_fee", type: "numeric", width: 65, allowEmpty: true },
      { data: "customs_honest_mark", type: "text", width: 85 },
      { data: "import_banned", type: "checkbox", width: 50, readOnly: !canToggleBan },
      { data: "import_ban_reason", type: "text", width: 120 },
      { data: "license_ds_required", type: "checkbox", width: 30 },
      { data: "license_ds_cost", type: "numeric", width: 55, allowEmpty: true },
      { data: "license_ss_required", type: "checkbox", width: 30 },
      { data: "license_ss_cost", type: "numeric", width: 55, allowEmpty: true },
      { data: "license_sgr_required", type: "checkbox", width: 30 },
      { data: "license_sgr_cost", type: "numeric", width: 55, allowEmpty: true },
    ],
    [canToggleBan]
  );

  /** Per-cell config: banned row styling + import_ban_reason read-only when not banned */
  const cellsCallback = useCallback(
    function (
      this: Handsontable.CellProperties,
      row: number,
      col: number
    ): Handsontable.CellMeta {
      const meta: Handsontable.CellMeta = {};
      const data = initialData[row];
      if (!data) return meta;

      // Red-tinted background for banned rows
      if (data.import_banned) {
        meta.className = (meta.className ?? "") + " row-import-banned";
      }

      // import_ban_reason col — make read-only when import_banned is false
      const prop = COLUMN_KEYS[col];
      if (prop === "import_ban_reason" && !data.import_banned) {
        meta.readOnly = true;
      }

      return meta;
    },
    [initialData]
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
      <style>{`
        .row-import-banned td {
          background-color: rgba(239, 68, 68, 0.08) !important;
        }
      `}</style>
      <div style={{ overflowX: "auto" }}>
        <HotTable
          ref={hotRef}
          data={initialData}
          licenseKey="non-commercial-and-evaluation"
          colHeaders={colHeaders}
          columns={columns}
          cells={cellsCallback}
          rowHeaders={false}
          stretchH="none"
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
      <p className="text-xs text-muted-foreground mt-2 px-1">
        * Стоимость ДС, СС, СГР указана в рублях (RUB). Числовые столбцы — значение за единицу товара.
      </p>
    </div>
  );
}
