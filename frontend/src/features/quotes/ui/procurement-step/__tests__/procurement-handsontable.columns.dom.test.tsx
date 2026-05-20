/**
 * КПП Handsontable — column wiring tests for supplier-side payment fields and
 * editable brand (feat/kpp-supplier-fields).
 *
 * Verifies the rendered <HotTable> column props for three КПП fields:
 *
 *   - `brand`            — was `readOnly: true` before this change; МОЗ must
 *                          be able to change brand when supplier replies with
 *                          a substitute.
 *   - `supplier_payment_terms`        — new editable text column.
 *   - `advance_to_supplier_percent`   — new editable numeric column with 0-100
 *                                       validator. Required by «Завершить
 *                                       закупку» gate (P1 rule).
 *
 * The underlying schema is on `kvota.quote_items` (migration 016) but the
 * handsontable rows are bound to `invoice_items.id`. Per-row metadata
 * (quote_item_ids, supplier_payment_terms, advance_to_supplier_percent) flows
 * in via the new `quoteItemMetadataByItemId` prop — the invoice-card derives
 * it from the existing coverage join.
 *
 * Test pattern mirrors `procurement-handsontable-jump.dom.test.tsx`: capture
 * <HotTable> props at render time, assert on the columns/colHeaders arrays.
 */

import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { createElement } from "react";

// Capture every props bag passed to <HotTable />.
const hotTableCalls: Array<Record<string, unknown>> = [];

vi.mock("@handsontable/react", () => ({
  HotTable: (props: Record<string, unknown>) => {
    hotTableCalls.push(props);
    return null;
  },
}));

vi.mock("handsontable", () => ({
  default: {
    renderers: {
      NumericRenderer: () => {},
      TextRenderer: () => {},
    },
  },
  renderers: {
    NumericRenderer: () => {},
    TextRenderer: () => {},
  },
}));

vi.mock("handsontable/registry", () => ({
  registerAllModules: () => {},
}));
vi.mock("handsontable/styles/handsontable.css", () => ({}));
vi.mock("handsontable/styles/ht-theme-main.css", () => ({}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ eq: async () => ({ data: [], error: null }) }),
      update: () => ({ eq: async () => ({ data: null, error: null }) }),
    }),
  }),
}));

vi.mock("@/entities/quote/mutations", () => ({
  updateInvoiceItem: async () => ({}),
  updateQuoteItem: async () => ({}),
  unassignInvoiceItem: async () => ({}),
}));

vi.mock("sonner", () => ({
  toast: {
    success: () => {},
    error: () => {},
    info: () => {},
  },
}));

import {
  ProcurementHandsontable,
  PROCUREMENT_COLUMN_KEYS,
} from "../procurement-handsontable";

const sampleItem = {
  id: "ii-1",
  invoice_id: "inv-1",
  position: 1,
  product_name: "Test product",
  supplier_sku: "SKU-1",
  brand: "TestBrand",
  quantity: 10,
  purchase_price_original: 100,
  purchase_currency: "USD",
  minimum_order_quantity: 1,
  production_time_days: 7,
  weight_in_kg: 2,
  dimension_height_mm: 100,
  dimension_width_mm: 50,
  dimension_length_mm: 25,
};

interface ColumnDef {
  data?: string;
  type?: string;
  readOnly?: boolean | ((..._args: unknown[]) => boolean);
  width?: number;
  validator?: (..._args: unknown[]) => unknown;
  numericFormat?: { pattern: string };
}

function getColumns(): ColumnDef[] {
  expect(hotTableCalls.length).toBeGreaterThan(0);
  const props = hotTableCalls[hotTableCalls.length - 1];
  const cols = props.columns;
  expect(Array.isArray(cols)).toBe(true);
  return cols as ColumnDef[];
}

function findColumn(key: string): ColumnDef | undefined {
  return getColumns().find((c) => c.data === key);
}

describe("procurement-handsontable — brand editable (P2)", () => {
  it("renders `brand` column without readOnly", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const brandCol = findColumn("brand");
    expect(brandCol).toBeDefined();
    // brand must NOT be hard-locked. (procurementCompleted=true still locks
    // the whole table via the cellsCallback; that's a separate concern.)
    expect(brandCol?.readOnly).not.toBe(true);
  });

  it("locks `brand` only when the КПП itself is completed", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: true,
      })
    );

    // When procurement is closed, EVERY editable column should be readOnly via
    // its column-level prop OR via the global cellsCallback returning
    // `locked-cell`. We assert the column-level prop here: brand follows the
    // same gating pattern as supplier_sku / purchase_price_original etc.
    const brandCol = findColumn("brand");
    expect(brandCol).toBeDefined();
    // procurementCompleted=true → readOnly true (mirrors supplier_sku pattern).
    expect(brandCol?.readOnly).toBe(true);
  });
});

describe("procurement-handsontable — payment-terms columns (P1)", () => {
  it("exports the new column keys", () => {
    expect(PROCUREMENT_COLUMN_KEYS).toContain("supplier_payment_terms");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("advance_to_supplier_percent");
  });

  it("renders a text column for supplier_payment_terms", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const col = findColumn("supplier_payment_terms");
    expect(col).toBeDefined();
    expect(col?.type).toBe("text");
  });

  it("renders a numeric column with 0-100 validator for advance_to_supplier_percent", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const col = findColumn("advance_to_supplier_percent");
    expect(col).toBeDefined();
    expect(col?.type).toBe("numeric");
    expect(typeof col?.validator).toBe("function");

    // Exercise the validator over the range.
    const calls: boolean[] = [];
    const cb = (ok: boolean) => calls.push(ok);

    // valid
    col!.validator!(0, cb);
    col!.validator!(50, cb);
    col!.validator!(100, cb);
    // empty / null are allowed (let the gate enforce required, not the cell)
    col!.validator!("", cb);
    col!.validator!(null, cb);
    expect(calls.every((v) => v === true)).toBe(true);

    // invalid
    const bad: boolean[] = [];
    const badCb = (ok: boolean) => bad.push(ok);
    col!.validator!(-1, badCb);
    col!.validator!(101, badCb);
    col!.validator!(150, badCb);
    expect(bad.every((v) => v === false)).toBe(true);
  });

  it("includes Cyrillic headers for the new columns", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const props = hotTableCalls[hotTableCalls.length - 1];
    const headers = props.colHeaders as string[];
    expect(headers).toContain("% аванса");
    expect(headers).toContain("Условия оплаты");
  });
});
