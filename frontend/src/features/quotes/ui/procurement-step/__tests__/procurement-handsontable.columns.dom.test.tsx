/**
 * КПП Handsontable — column wiring tests.
 *
 * Verifies the rendered <HotTable> column props:
 *
 *   - `brand` — was `readOnly: true` before; МОЗ must be able to change
 *     brand when the supplier replies with a substitute. Locked again only
 *     when the КПП itself is completed (procurementCompleted=true).
 *   - Negative assertions on `% аванса` / `Условия оплаты` — those moved to
 *     the invoice-level header block in m328 (Testing 2 row 69). The
 *     handsontable must NOT carry per-position columns for them anymore.
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

describe("procurement-handsontable — payment-terms moved to invoice level (m328, Testing 2 row 69)", () => {
  it("does NOT expose `% аванса` / `Условия оплаты` as per-position column keys", () => {
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("supplier_payment_terms");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain(
      "advance_to_supplier_percent"
    );
  });

  it("does NOT render per-position columns for the moved fields", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    expect(findColumn("supplier_payment_terms")).toBeUndefined();
    expect(findColumn("advance_to_supplier_percent")).toBeUndefined();
  });

  it("does NOT include per-position headers `% аванса` / `Условия оплаты`", () => {
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
    expect(headers).not.toContain("% аванса");
    expect(headers).not.toContain("Условия оплаты");
  });
});

describe("procurement-handsontable — supplier-quantity override rename (Row 85)", () => {
  it("renames «Мин. заказ» → «Кол-во поставщика» with an explainer tooltip", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const props = hotTableCalls[hotTableCalls.length - 1];
    const headers = (props.colHeaders as string[]).join(" ");
    // New label present, old «Мин. заказ» retired.
    expect(headers).toContain("Кол-во поставщика");
    expect(headers).not.toContain("Мин. заказ");
    // Explainer carried via the native-title HTML colHeader (override semantics).
    expect(headers).toContain("переопределяет заказанное");
  });

  it("supplier-qty column drops the retired MOQ-violation renderer", () => {
    hotTableCalls.length = 0;

    renderToString(
      createElement(ProcurementHandsontable, {
        items: [sampleItem],
        invoiceId: "inv-1",
        procurementCompleted: false,
      })
    );

    const moqCol = findColumn("minimum_order_quantity");
    expect(moqCol).toBeDefined();
    // The violation highlight is retired — a smaller supplier qty is an
    // intentional override, not an error — so no custom renderer remains.
    expect(
      (moqCol as ColumnDef & { renderer?: unknown }).renderer
    ).toBeUndefined();
    // Still editable by procurement (no readOnly when КПП is open).
    expect(moqCol?.readOnly).not.toBe(true);
  });
});
