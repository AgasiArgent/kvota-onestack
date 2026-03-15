"use client";

import { useCallback, useMemo } from "react";
import { HotTable, type HotTableClass } from "@handsontable/react";
import { registerAllModules } from "handsontable/registry";
import type Handsontable from "handsontable";
import "handsontable/dist/handsontable.full.min.css";
import type { PhmbQuoteItem, CalcResult } from "@/entities/phmb-quote/types";

registerAllModules();

interface ItemsTableProps {
  items: PhmbQuoteItem[];
  onUpdateItem: (id: string, field: string, value: number | string) => void;
  onDeleteItem: (id: string) => void;
  totals: CalcResult["totals"] | null;
}

export function ItemsTable({
  items,
  onUpdateItem,
  onDeleteItem,
  totals,
}: ItemsTableProps) {
  // Map items to table data rows
  const tableData = useMemo(() => {
    const rows = items.map((item, idx) => [
      idx + 1, // row number
      item.cat_number,
      item.product_name,
      item.brand,
      item.quantity,
      item.list_price_rmb,
      item.discount_pct,
      item.exw_price_usd,
      item.cogs_usd,
      item.total_price_usd,
      item.total_price_with_vat_usd,
      item.status === "priced" ? "\u2713" : "\u23F3", // checkmark or hourglass
    ]);

    // Add totals row
    if (items.length > 0) {
      rows.push([
        "",
        "",
        "ИТОГО",
        "",
        "",
        "",
        "",
        "",
        "",
        totals?.total_usd ?? null,
        totals?.total_with_vat_usd ?? null,
        "",
      ]);
    }

    return rows;
  }, [items, totals]);

  const columns: Handsontable.ColumnSettings[] = useMemo(
    () => [
      { data: 0, width: 40, readOnly: true, type: "text" },
      { data: 1, width: 120, readOnly: true, type: "text" },
      { data: 2, width: 220, readOnly: true, type: "text" },
      { data: 3, width: 100, readOnly: true, type: "text" },
      { data: 4, width: 70, readOnly: false, type: "numeric" },
      {
        data: 5,
        width: 100,
        readOnly: false,
        type: "numeric",
        numericFormat: { pattern: "0,0.00", culture: "ru-RU" },
      },
      {
        data: 6,
        width: 80,
        readOnly: true,
        type: "numeric",
        numericFormat: { pattern: "0.0", culture: "ru-RU" },
      },
      {
        data: 7,
        width: 100,
        readOnly: true,
        type: "numeric",
        numericFormat: { pattern: "0,0.00", culture: "ru-RU" },
      },
      {
        data: 8,
        width: 100,
        readOnly: true,
        type: "numeric",
        numericFormat: { pattern: "0,0.00", culture: "ru-RU" },
      },
      {
        data: 9,
        width: 110,
        readOnly: true,
        type: "numeric",
        numericFormat: { pattern: "0,0.00", culture: "ru-RU" },
      },
      {
        data: 10,
        width: 110,
        readOnly: true,
        type: "numeric",
        numericFormat: { pattern: "0,0.00", culture: "ru-RU" },
      },
      { data: 11, width: 40, readOnly: true, type: "text" },
    ],
    []
  );

  const colHeaders = [
    "#",
    "Артикул",
    "Наименование",
    "Бренд",
    "Кол-во",
    "Цена RMB",
    "Скидка %",
    "EXW USD",
    "COGS USD",
    "Цена продажи",
    "Итого с НДС",
    "",
  ];

  const handleAfterChange = useCallback(
    (
      changes: Handsontable.CellChange[] | null,
      _source: Handsontable.ChangeSource
    ) => {
      if (!changes) return;

      for (const [row, col, oldVal, newVal] of changes) {
        // Ignore totals row
        if (row >= items.length) continue;
        if (oldVal === newVal) continue;

        const item = items[row];
        if (!item) continue;

        if (col === 4) {
          // quantity
          onUpdateItem(item.id, "quantity", Number(newVal));
        } else if (col === 5) {
          // list_price_rmb
          onUpdateItem(item.id, "list_price_rmb", Number(newVal));
        }
      }
    },
    [items, onUpdateItem]
  );

  const cellCallback = useCallback(
    (
      row: number,
      col: number,
      prop: string | number
    ): Handsontable.CellMeta => {
      const meta: Handsontable.CellMeta = {};

      // Totals row styling
      if (row === items.length) {
        meta.readOnly = true;
        meta.className = "phmb-totals-row";
        return meta;
      }

      const item = items[row];
      if (!item) return meta;

      // Waiting items: orange background
      if (item.status === "waiting") {
        meta.className = "phmb-waiting-row";
      }

      return meta;
    },
    [items]
  );

  if (items.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-text-subtle text-sm border border-border-light rounded-lg bg-card">
        Добавьте позиции через поиск выше
      </div>
    );
  }

  return (
    <div className="phmb-table-wrapper border border-border-light rounded-lg overflow-hidden">
      <style>{`
        .phmb-table-wrapper .handsontable {
          font-family: 'Plus Jakarta Sans', sans-serif;
          font-size: 14px;
          color: var(--color-text, #1C1917);
        }
        .phmb-table-wrapper .handsontable th {
          background: var(--color-sidebar, #F0EDEA) !important;
          color: var(--color-text-muted, #78716C) !important;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          border-color: var(--color-border, #D6D3CE) !important;
        }
        .phmb-table-wrapper .handsontable td {
          background: var(--color-card, #FFFFFF);
          border-color: var(--color-border-light, #E7E5E0) !important;
        }
        .phmb-table-wrapper .handsontable td.phmb-waiting-row {
          background: #FEF3C7 !important;
          color: #92400E;
        }
        .phmb-table-wrapper .handsontable td.phmb-totals-row {
          background: var(--color-sidebar, #F0EDEA) !important;
          font-weight: 600;
          border-top: 2px solid var(--color-border, #D6D3CE) !important;
        }
        .phmb-table-wrapper .handsontable td.current,
        .phmb-table-wrapper .handsontable td.area {
          background: var(--color-accent-subtle, #FFF7ED) !important;
        }
        .phmb-table-wrapper .handsontable .htDimmed {
          color: var(--color-text-muted, #78716C);
        }
        .phmb-table-wrapper .ht_master .wtHolder {
          max-height: 60vh;
        }
      `}</style>
      <HotTable
        data={tableData}
        columns={columns}
        colHeaders={colHeaders}
        rowHeaders={false}
        stretchH="all"
        autoColumnSize={false}
        manualColumnResize
        contextMenu={["remove_row"]}
        afterChange={handleAfterChange}
        cells={cellCallback}
        beforeRemoveRow={(index: number) => {
          if (index < items.length) {
            const item = items[index];
            if (item) onDeleteItem(item.id);
          }
          return false; // Prevent default removal — we update state via callback
        }}
        licenseKey="non-commercial-and-evaluation"
        height="auto"
        className="phmb-hot"
      />
    </div>
  );
}
