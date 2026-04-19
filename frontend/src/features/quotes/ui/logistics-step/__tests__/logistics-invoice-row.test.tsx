import { describe, it, expect } from "vitest";

/**
 * Phase 5d Task 14 (Agent C) — logistics-invoice-row weight tests.
 *
 * Per-invoice logistics data (weight, dimensions) belongs to invoice_items,
 * not quote_items. Migration 284 drops `quote_items.weight_in_kg`; the
 * logistics row sums weights from invoice_items tied to this invoice.
 */

import {
  computeTotalWeight,
  type LogisticsWeightItem,
  type CargoPlace,
} from "../logistics-invoice-row";

function ii(
  overrides: Partial<LogisticsWeightItem> = {}
): LogisticsWeightItem {
  return { quantity: 1, weight_in_kg: 0, ...overrides };
}

describe("computeTotalWeight — sources from invoice_items post-Phase-5d", () => {
  it("prefers cargo-places total when provided", () => {
    const cargo: CargoPlace[] = [
      { weight_kg: 5 },
      { weight_kg: 7 },
    ];
    const invoiceItems = [ii({ weight_in_kg: 100, quantity: 2 })];
    expect(computeTotalWeight(invoiceItems, cargo)).toBe(12);
  });

  it("falls back to sum of invoice_items.weight_in_kg × quantity when no cargo places", () => {
    const invoiceItems = [
      ii({ weight_in_kg: 2.5, quantity: 4 }),
      ii({ weight_in_kg: 1, quantity: 10 }),
    ];
    expect(computeTotalWeight(invoiceItems, [])).toBe(20);
  });

  it("treats null weight_in_kg as zero", () => {
    const invoiceItems = [
      ii({ weight_in_kg: null, quantity: 100 }),
      ii({ weight_in_kg: 3, quantity: 2 }),
    ];
    expect(computeTotalWeight(invoiceItems, [])).toBe(6);
  });

  it("returns 0 when invoice_items empty and no cargo places", () => {
    expect(computeTotalWeight([], [])).toBe(0);
  });
});
