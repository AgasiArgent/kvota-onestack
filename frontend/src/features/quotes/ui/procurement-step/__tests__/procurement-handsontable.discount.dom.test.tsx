/**
 * Testing 2 row 91 — per-line КПП discount column wiring.
 *
 * Verifies the rendered <HotTable> props for the «Скидка, %» editable column
 * and the read-only «Сумма со скидкой» computed column:
 *
 *   1. `discount_pct` is a save key (PROCUREMENT_COLUMN_KEYS) and renders as a
 *      numeric column; `discounted_total` renders read-only (computed, never
 *      persisted).
 *   2. The «Скидка, %» / «Сумма со скидкой» headers are present.
 *   3. The discounted line total fed through the `data` prop equals
 *      qty × unit × (1 - discount_pct/100) — the same factor the calc input
 *      adaptation applies. Null/0 discount leaves the gross total unchanged.
 *   4. On a completed КПП, `discount_pct` is locked (mirrors `purchase_price`),
 *      while `discounted_total` is always read-only.
 *
 * Test pattern mirrors `procurement-handsontable.columns.dom.test.tsx`:
 * capture <HotTable> props at render time, assert on columns/colHeaders/data.
 */

import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { createElement } from "react";

const hotTableCalls: Array<Record<string, unknown>> = [];

vi.mock("@handsontable/react", () => ({
  HotTable: (props: Record<string, unknown>) => {
    hotTableCalls.push(props);
    return null;
  },
}));

vi.mock("handsontable", () => ({
  default: {
    renderers: { NumericRenderer: () => {}, TextRenderer: () => {} },
  },
  renderers: { NumericRenderer: () => {}, TextRenderer: () => {} },
}));

vi.mock("handsontable/registry", () => ({ registerAllModules: () => {} }));
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
  toast: { success: () => {}, error: () => {}, info: () => {} },
}));

import { ProcurementHandsontable } from "../procurement-handsontable";
import { PROCUREMENT_COLUMN_KEYS } from "../procurement-handsontable";

const baseItem = {
  id: "ii-1",
  invoice_id: "inv-1",
  position: 1,
  product_name: "Test product",
  supplier_sku: "SKU-1",
  brand: "TestBrand",
  quantity: 10,
  purchase_price_original: 100,
  discount_pct: null as number | null,
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
  numericFormat?: { pattern: string };
}

function renderWith(item: typeof baseItem, procurementCompleted = false) {
  hotTableCalls.length = 0;
  renderToString(
    createElement(ProcurementHandsontable, {
      items: [item],
      invoiceId: "inv-1",
      procurementCompleted,
    })
  );
  return hotTableCalls[hotTableCalls.length - 1];
}

function columns(props: Record<string, unknown>): ColumnDef[] {
  const cols = props.columns;
  expect(Array.isArray(cols)).toBe(true);
  return cols as ColumnDef[];
}

function findColumn(props: Record<string, unknown>, key: string) {
  return columns(props).find((c) => c.data === key);
}

describe("procurement-handsontable — per-line discount column (Testing 2 row 91)", () => {
  it("exposes `discount_pct` as a save key but NOT `discounted_total`", () => {
    expect(PROCUREMENT_COLUMN_KEYS).toContain("discount_pct");
    // The discounted total is computed/read-only; it must not be a save target.
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("discounted_total");
  });

  it("renders the «Скидка, %» and «Сумма со скидкой» headers", () => {
    const props = renderWith(baseItem);
    const headers = (props.colHeaders as string[]).join(" ");
    expect(headers).toContain("Скидка, %");
    expect(headers).toContain("Сумма со скидкой");
  });

  it("renders `discount_pct` as an editable numeric column when КПП is open", () => {
    const props = renderWith(baseItem, false);
    const col = findColumn(props, "discount_pct");
    expect(col).toBeDefined();
    expect(col?.type).toBe("numeric");
    expect(col?.readOnly).not.toBe(true);
  });

  it("renders `discounted_total` as a read-only numeric column", () => {
    const props = renderWith(baseItem, false);
    const col = findColumn(props, "discounted_total");
    expect(col).toBeDefined();
    expect(col?.type).toBe("numeric");
    expect(col?.readOnly).toBe(true);
  });

  it("computes the discounted line total = qty × unit × (1 - pct/100)", () => {
    const props = renderWith({ ...baseItem, discount_pct: 10 });
    const rows = props.data as Array<{ discounted_total: number | null }>;
    // 10 × 100 × (1 - 0.10) = 900
    expect(rows[0].discounted_total).toBe(900);
  });

  it("leaves the gross total unchanged when there is no discount", () => {
    const props = renderWith({ ...baseItem, discount_pct: null });
    const rows = props.data as Array<{ discounted_total: number | null }>;
    // 10 × 100 × 1 = 1000
    expect(rows[0].discounted_total).toBe(1000);
  });

  it("treats a zero discount as no discount (gross total)", () => {
    const props = renderWith({ ...baseItem, discount_pct: 0 });
    const rows = props.data as Array<{ discounted_total: number | null }>;
    expect(rows[0].discounted_total).toBe(1000);
  });

  it("locks `discount_pct` on a completed КПП (mirrors price)", () => {
    const props = renderWith(baseItem, true);
    const col = findColumn(props, "discount_pct");
    expect(col?.readOnly).toBe(true);
    // The computed total stays read-only in both states.
    expect(findColumn(props, "discounted_total")?.readOnly).toBe(true);
  });
});
