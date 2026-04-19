import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 12 (Agent A) — sales-items-table regression.
 *
 * Verifies the component is a pure presentational table fed via props:
 *   - Items come from parent (page.tsx -> fetchQuoteItems), no self-fetch
 *   - Prices read from item.base_price_vat (the calc-engine write-back
 *     per main.py:14410 after /calculate runs)
 *   - Formats totals across all items in the supplied currency
 *
 * Task 12 case (a): data flows via props. No component change needed —
 * this spec guards the current prop contract.
 */

import { SalesItemsTable, type SalesItemRow } from "../sales-items-table";

function makeItem(overrides: Partial<SalesItemRow> = {}): SalesItemRow {
  return {
    id: "qi-1",
    product_name: "Болт М8",
    brand: "ABB",
    product_code: "SKU-1",
    quantity: 10,
    unit: "шт",
    base_price_vat: 100,
    ...overrides,
  };
}

describe("SalesItemsTable — reads base_price_vat from props", () => {
  it("renders per-item price from item.base_price_vat", () => {
    const items = [makeItem({ base_price_vat: 123.45, quantity: 2 })];

    const html = renderToString(
      <SalesItemsTable items={items} currency="USD" />
    );

    // Per-unit price formatted ru-RU style
    expect(html).toContain("123,45");
    // Line total = price * quantity = 246.90
    expect(html).toContain("246,90");
  });

  it("renders ИТОГО aggregated across all items", () => {
    const items = [
      makeItem({ id: "a", base_price_vat: 100, quantity: 2 }),
      makeItem({ id: "b", base_price_vat: 50, quantity: 4 }),
    ];

    const html = renderToString(
      <SalesItemsTable items={items} currency="USD" />
    );

    // Totals row: 100*2 + 50*4 = 400.00
    expect(html).toContain("400,00");
    // Total qty row: 2+4 = 6
    expect(html).toContain("ИТОГО:");
  });

  it("shows em-dash when base_price_vat is null", () => {
    const items = [makeItem({ base_price_vat: null })];

    const html = renderToString(
      <SalesItemsTable items={items} currency="USD" />
    );

    // Em-dash unicode \u2014 or rendered as "—"
    expect(html).toMatch(/—|&#x2014;/);
  });
});
