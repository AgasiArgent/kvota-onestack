import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 14 (Agent C) — procurement-action-bar null-check tests.
 *
 * Verifies the "pricing readiness" logic uses a composed `priceReadyByQuoteItemId`
 * map instead of reading `purchase_price_original` directly off quote_items.
 *
 * Post-migration 284 `quote_items.purchase_price_original` is dropped, so the
 * legacy check would always return false. The new contract: the caller
 * supplies a `priceReadyByQuoteItemId` map derived from coverage →
 * invoice_items with non-null price in the selected invoice.
 */

import {
  getSubStage,
  countPriceReady,
  type ProcurementReadinessItem,
  type PriceReadyMap,
} from "../procurement-action-bar";

function item(
  overrides: Partial<ProcurementReadinessItem> = {}
): ProcurementReadinessItem {
  return {
    id: "qi-1",
    assigned_procurement_user: null,
    is_unavailable: false,
    ...overrides,
  };
}

describe("getSubStage — readiness derived from priceReadyByQuoteItemId map", () => {
  it("returns 'assignment' when no items", () => {
    expect(getSubStage([], {})).toBe("assignment");
  });

  it("returns 'assignment' when some items lack assigned_procurement_user", () => {
    const items = [
      item({ id: "qi-1", assigned_procurement_user: "u-1" }),
      item({ id: "qi-2", assigned_procurement_user: null }),
    ];
    expect(getSubStage(items, {})).toBe("assignment");
  });

  it("returns 'pricing' when all assigned but not all priced via coverage", () => {
    const items = [
      item({ id: "qi-1", assigned_procurement_user: "u-1" }),
      item({ id: "qi-2", assigned_procurement_user: "u-1" }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true };
    expect(getSubStage(items, priceReady)).toBe("pricing");
  });

  it("returns 'ready' when every item is priced via coverage map", () => {
    const items = [
      item({ id: "qi-1", assigned_procurement_user: "u-1" }),
      item({ id: "qi-2", assigned_procurement_user: "u-1" }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true, "qi-2": true };
    expect(getSubStage(items, priceReady)).toBe("ready");
  });

  it("counts is_unavailable items as priced without requiring coverage", () => {
    // Customer-marked N/A items are excluded from the readiness check.
    const items = [
      item({ id: "qi-1", assigned_procurement_user: "u-1" }),
      item({
        id: "qi-2",
        assigned_procurement_user: null,
        is_unavailable: true,
      }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true };
    expect(getSubStage(items, priceReady)).toBe("ready");
  });
});

describe("countPriceReady — how many items are priced via coverage", () => {
  it("counts only items whose id appears in priceReady map OR is_unavailable", () => {
    const items = [
      item({ id: "qi-1" }),
      item({ id: "qi-2" }),
      item({ id: "qi-3", is_unavailable: true }),
    ];
    const priceReady: PriceReadyMap = { "qi-1": true };
    expect(countPriceReady(items, priceReady)).toBe(2);
  });

  it("does not count false entries in priceReady map", () => {
    const items = [item({ id: "qi-1" })];
    const priceReady: PriceReadyMap = { "qi-1": false };
    expect(countPriceReady(items, priceReady)).toBe(0);
  });

  it("does not read `purchase_price_original` off the item (legacy column gone)", () => {
    // Regression: without a coverage map, a formerly-priced item should
    // register as not-ready — legacy fallback removed.
    const items = [
      item({ id: "qi-1" }) as unknown as ProcurementReadinessItem & {
        purchase_price_original: number;
      },
    ];
    (items[0] as unknown as { purchase_price_original: number })
      .purchase_price_original = 10;
    expect(countPriceReady(items, {})).toBe(0);
  });
});
