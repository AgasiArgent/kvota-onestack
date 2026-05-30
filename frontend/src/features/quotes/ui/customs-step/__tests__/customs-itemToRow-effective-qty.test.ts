import { describe, it, expect } from "vitest";
import { itemToRow, type SupplierByQuoteItem } from "../customs-handsontable";
import type { QuoteItemRow } from "@/entities/quote/queries";

function item(over: Record<string, unknown> = {}): QuoteItemRow {
  return {
    id: "qi-1",
    position: 1,
    brand: "B",
    product_code: "PC",
    product_name: "P",
    quantity: 32,
    ...over,
  } as unknown as QuoteItemRow;
}

function supplierMap(
  entry: Partial<SupplierByQuoteItem> = {}
): Map<string, SupplierByQuoteItem> {
  return new Map([
    [
      "qi-1",
      {
        supplier_country: "CN",
        invoice_id: "inv-1",
        minimum_order_quantity: null,
        ...entry,
      },
    ],
  ]);
}

describe("itemToRow — effective quantity (supplier override)", () => {
  it("shows effective qty (override UP)", () => {
    const row = itemToRow(
      item({ quantity: 32 }),
      new Map(),
      supplierMap({ minimum_order_quantity: 738 })
    );
    expect(row.quantity).toBe(738);
  });

  it("shows effective qty (override DOWN)", () => {
    const row = itemToRow(
      item({ quantity: 20 }),
      new Map(),
      supplierMap({ minimum_order_quantity: 10 })
    );
    expect(row.quantity).toBe(10);
  });

  it("falls back to ordered when supplier qty unset", () => {
    const row = itemToRow(
      item({ quantity: 7 }),
      new Map(),
      supplierMap({ minimum_order_quantity: null })
    );
    expect(row.quantity).toBe(7);
  });

  it("falls back to ordered when no supplier map entry", () => {
    const row = itemToRow(item({ quantity: 5 }), new Map(), new Map());
    expect(row.quantity).toBe(5);
  });
});
