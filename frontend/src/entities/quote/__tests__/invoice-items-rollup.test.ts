import { describe, it, expect } from "vitest";
import {
  rollupInvoiceItemsByInvoice,
  type InvoiceItemAggRow,
} from "../queries";

function row(over: Partial<InvoiceItemAggRow> = {}): InvoiceItemAggRow {
  return {
    invoice_id: "inv-1",
    quantity: 10,
    minimum_order_quantity: null,
    purchase_price_original: 100,
    purchase_currency: "USD",
    invoice_item_coverage: [{ quote_items: { unit: "шт" } }],
    ...over,
  };
}

describe("rollupInvoiceItemsByInvoice — effective quantity", () => {
  it("sums effective qty (override UP) and price × effective", () => {
    // ordered 5, supplier 10 → effective 10; amount 100 × 10 = 1000
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 5, minimum_order_quantity: 10 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(10);
    expect(agg.total_amount_original).toBe(1000);
  });

  it("sums effective qty (override DOWN)", () => {
    // ordered 20, supplier 5 → effective 5; amount 100 × 5 = 500
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 20, minimum_order_quantity: 5 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(5);
    expect(agg.total_amount_original).toBe(500);
  });

  it("uses ordered qty when supplier qty unset", () => {
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 7, minimum_order_quantity: null, purchase_price_original: 100 }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(7);
    expect(agg.total_amount_original).toBe(700);
  });

  it("aggregates units and keeps total null when no quantity contributes", () => {
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: null, purchase_price_original: null }),
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBeNull();
    expect(agg.units.has("шт")).toBe(true);
  });

  it("sums effective qty across multiple rows of the same invoice", () => {
    const agg = rollupInvoiceItemsByInvoice([
      row({ quantity: 5, minimum_order_quantity: 10 }), // eff 10
      row({ quantity: 20, minimum_order_quantity: 5 }), // eff 5
    ]).get("inv-1")!;
    expect(agg.total_quantity).toBe(15);
  });
});
