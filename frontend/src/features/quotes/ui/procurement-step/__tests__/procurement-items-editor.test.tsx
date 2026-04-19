import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5d Group 5 Appendix — procurement-items-editor caller chain.
 *
 * Task 14 (`8283a90`) rebound procurement-handsontable's COLUMN_KEYS to
 * the invoice_items schema (`minimum_order_quantity`, `purchase_price_original`,
 * etc). Upstream callers still passed `QuoteItemRow[]` — post-migration
 * 284 the handsontable rows would render `undefined` for those keys.
 *
 * Contract: procurement-items-editor must accept an `items` prop whose
 * rows carry invoice_items fields and forward them verbatim to
 * <ProcurementHandsontable items={...} />.
 *
 * We spy on the handsontable prop by mocking the dynamic import and
 * asserting the rendered items on the inner component.
 */

// next/dynamic resolves to a Promise-returning loader. Return the inner
// component synchronously so renderToString can capture its output + props.
vi.mock("next/dynamic", () => ({
  default: (
    loader: () => Promise<{ default: React.ComponentType<unknown> }>
  ) => {
    // Evaluate loader lazily; vitest runs loaders inline so we can await.
    let resolvedComponent: React.ComponentType<unknown> | null = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (loader as any)().then((mod: { default: React.ComponentType<unknown> }) => {
      resolvedComponent = mod.default;
    });
    // Return a wrapper that delegates to the resolved component.
    return function DynamicWrapper(props: Record<string, unknown>) {
      if (!resolvedComponent) return null;
      return React.createElement(resolvedComponent, props);
    };
  },
}));

// Capture the items prop that the editor passes to the handsontable.
let capturedHotProps: Record<string, unknown> | undefined;
vi.mock("../procurement-handsontable", () => ({
  ProcurementHandsontable: (props: Record<string, unknown>) => {
    capturedHotProps = props;
    return null;
  },
}));

import { ProcurementItemsEditor } from "../procurement-items-editor";

// Invoice items shape (supplier-side). Mirrors the kvota.invoice_items
// schema the handsontable COLUMN_KEYS now bind to.
type InvoiceItemShape = {
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
};

function makeInvoiceItem(
  overrides: Partial<InvoiceItemShape> = {}
): InvoiceItemShape {
  return {
    id: "ii-1",
    invoice_id: "inv-A",
    position: 1,
    product_name: "Подшипник",
    supplier_sku: "SKF-205",
    brand: "SKF",
    quantity: 5,
    purchase_price_original: 1200,
    purchase_currency: "USD",
    minimum_order_quantity: 10,
    production_time_days: 14,
    weight_in_kg: 0.5,
    dimension_height_mm: 20,
    dimension_width_mm: 25,
    dimension_length_mm: 52,
    ...overrides,
  };
}

describe("ProcurementItemsEditor — forwards invoice_items rows to handsontable", () => {
  it("passes the items prop through unchanged (preserving invoice_items shape)", () => {
    capturedHotProps = undefined;
    const invoiceItems = [makeInvoiceItem()];

    renderToString(
      <ProcurementItemsEditor
        items={invoiceItems}
        invoiceId="inv-A"
        procurementCompleted={false}
      />
    );

    expect(capturedHotProps).toBeDefined();
    const items = capturedHotProps!.items as InvoiceItemShape[];
    expect(items).toBe(invoiceItems);
  });

  it("preserves invoice_items field names that the handsontable COLUMN_KEYS bind to", () => {
    // Guard against silently accepting a QuoteItemRow[] (missing these keys).
    capturedHotProps = undefined;
    const invoiceItems = [
      makeInvoiceItem({
        minimum_order_quantity: 10,
        production_time_days: 14,
        weight_in_kg: 0.5,
        purchase_price_original: 999,
      }),
    ];

    renderToString(
      <ProcurementItemsEditor
        items={invoiceItems}
        invoiceId="inv-A"
        procurementCompleted={false}
      />
    );

    const items = capturedHotProps!.items as InvoiceItemShape[];
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      minimum_order_quantity: 10,
      production_time_days: 14,
      weight_in_kg: 0.5,
      purchase_price_original: 999,
    });
  });

  it("forwards invoiceId and procurementCompleted unchanged", () => {
    capturedHotProps = undefined;
    renderToString(
      <ProcurementItemsEditor
        items={[]}
        invoiceId="inv-B"
        procurementCompleted={true}
      />
    );

    expect(capturedHotProps).toMatchObject({
      invoiceId: "inv-B",
      procurementCompleted: true,
    });
  });
});
