import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 14 (Agent C) — products-subtable weight tests.
 *
 * The subtable lists supplier-side positions and renders `weight_in_kg`
 * per row. Post-migration 284 the source is `invoice_items.weight_in_kg`.
 */

import { ProductsSubtable } from "../products-subtable";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";

function makeInvoice(): QuoteInvoiceRow {
  return {
    id: "inv-A",
    invoice_number: "INV-01",
    package_count: 2,
  } as unknown as QuoteInvoiceRow;
}

describe("ProductsSubtable — weight_in_kg sourced from invoice_items", () => {
  it("renders invoice_items.weight_in_kg per row", () => {
    const items = [
      {
        id: "ii-1",
        product_name: "Болт",
        product_code: "SKU-1",
        quantity: 100,
        weight_in_kg: 2.5,
      },
    ];

    const html = renderToString(
      <ProductsSubtable items={items} invoice={makeInvoice()} />
    );
    expect(html).toContain("2,50");
  });

  it("renders em-dash when invoice_items.weight_in_kg is null", () => {
    const items = [
      {
        id: "ii-1",
        product_name: "Болт",
        product_code: null,
        quantity: 100,
        weight_in_kg: null,
      },
    ];

    const html = renderToString(
      <ProductsSubtable items={items} invoice={makeInvoice()} />
    );
    // \u2014 = em-dash rendered as the "no weight" sentinel
    expect(html).toContain("\u2014");
  });

  it("accepts invoice_items rows with dimension_*_mm from invoice_items", () => {
    const items = [
      {
        id: "ii-1",
        product_name: "Болт",
        product_code: "SKU-1",
        quantity: 100,
        weight_in_kg: 1,
        dimension_height_mm: 10,
        dimension_width_mm: 20,
        dimension_length_mm: 30,
      },
    ];

    const html = renderToString(
      <ProductsSubtable items={items} invoice={makeInvoice()} />
    );
    // Format is "HxWxL" via × (multiplication sign, U+00D7)
    expect(html).toContain("10");
    expect(html).toContain("20");
    expect(html).toContain("30");
  });
});
