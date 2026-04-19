import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 14 (Agent C) — procurement-step "can complete" guard tests.
 *
 * The old guard read `i.purchase_price_original` off quote_items (dropped in
 * migration 284). The new guard consumes a `priceReadyByQuoteItemId` map
 * derived from coverage → invoice_items with non-null
 * `purchase_price_original` in the selected invoice.
 */

import {
  validateCompleteProcurementGuard,
  type CompleteGuardItem,
  type PriceReadyMap,
} from "../procurement-step";

function item(overrides: Partial<CompleteGuardItem> = {}): CompleteGuardItem {
  return {
    id: "qi-1",
    invoice_id: "inv-A",
    is_unavailable: false,
    ...overrides,
  };
}

describe("validateCompleteProcurementGuard — uses coverage-derived priceReady map", () => {
  it("returns ok when every non-N/A item is priced via coverage and assigned", () => {
    const items = [
      item({ id: "qi-1", invoice_id: "inv-A" }),
      item({ id: "qi-2", invoice_id: "inv-A" }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true, "qi-2": true };
    const result = validateCompleteProcurementGuard(items, priceReady);
    expect(result.ok).toBe(true);
  });

  it("blocks when one item lacks a priceReady entry (uncovered or null price)", () => {
    const items = [
      item({ id: "qi-1", invoice_id: "inv-A" }),
      item({ id: "qi-2", invoice_id: "inv-A" }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true };
    const result = validateCompleteProcurementGuard(items, priceReady);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe("no-price");
      expect(result.count).toBe(1);
    }
  });

  it("blocks when any item is unassigned to an invoice", () => {
    const items = [
      item({ id: "qi-1", invoice_id: "inv-A" }),
      item({ id: "qi-2", invoice_id: null }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true, "qi-2": true };
    const result = validateCompleteProcurementGuard(items, priceReady);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe("unassigned");
      expect(result.count).toBe(1);
    }
  });

  it("excludes is_unavailable items from both the price and assignment checks", () => {
    const items = [
      item({ id: "qi-1", invoice_id: "inv-A" }),
      item({ id: "qi-2", invoice_id: null, is_unavailable: true }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true };
    const result = validateCompleteProcurementGuard(items, priceReady);
    expect(result.ok).toBe(true);
  });

  it("does not read `purchase_price_original` off the item (legacy column gone)", () => {
    // A formerly-priced item with no coverage entry should register as
    // not-ready — no legacy fallback.
    const items = [
      item({ id: "qi-1", invoice_id: "inv-A" }) as unknown as CompleteGuardItem & {
        purchase_price_original: number;
      },
    ];
    (items[0] as unknown as { purchase_price_original: number })
      .purchase_price_original = 10;
    const result = validateCompleteProcurementGuard(items, {});
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.reason).toBe("no-price");
    }
  });
});
