import { describe, it, expect } from "vitest";
import { aggregateDistributionMetrics } from "../api/server-queries";
import type { QuoteWithBrandGroups } from "../model/types";

/**
 * РОЗ-57 — sidebar badge for «Распределение» previously surfaced the
 * brand-slice count (1 card = 1 brand-slice). The /quotes registry counts
 * whole quotes (1 row = 1 quote) in its «Требует действия» group, so when a
 * quote had ≥2 brands at the distribution stage the two surfaces showed
 * different numbers (e.g. 5 vs 4) for the same logical bucket. The fix:
 * `fetchUnassignedItemCount` now returns `quoteCount` to align with /quotes;
 * the page header still surfaces both numbers in its subtitle.
 *
 * These tests exercise the pure aggregation helper that powers both the
 * sidebar badge and the page header — sufficient to lock in the contract
 * without spinning up a Supabase mock chain.
 */

function makeQuote(
  id: string,
  brands: string[],
  itemsPerBrand: number
): QuoteWithBrandGroups {
  return {
    quote: {
      id,
      idn: `Q-${id}`,
      customer_name: null,
      sales_manager_name: null,
      created_at: "2026-05-05T00:00:00Z",
    },
    brandGroups: brands.map((brand, i) => ({
      brand,
      itemCount: itemsPerBrand,
      itemIds: Array.from({ length: itemsPerBrand }).map(
        (_, k) => `${id}-${i}-${k}`
      ),
    })),
  };
}

describe("aggregateDistributionMetrics — units", () => {
  it("counts unique quotes for quoteCount (one input row → one quote)", () => {
    const m = aggregateDistributionMetrics([
      makeQuote("a", ["Alfa"], 2),
      makeQuote("b", ["Beta"], 1),
      makeQuote("c", ["Gamma", "Delta"], 1),
    ]);
    expect(m.quoteCount).toBe(3);
  });

  it("counts (quote × brand) pairs for brandSliceCount", () => {
    const m = aggregateDistributionMetrics([
      makeQuote("a", ["Alfa"], 2),
      makeQuote("b", ["Beta"], 1),
      makeQuote("c", ["Gamma", "Delta"], 1), // 2 slices on this quote
    ]);
    expect(m.brandSliceCount).toBe(4);
  });

  it("counts every position for itemCount", () => {
    const m = aggregateDistributionMetrics([
      makeQuote("a", ["Alfa"], 2),
      makeQuote("b", ["Beta"], 1),
      makeQuote("c", ["Gamma", "Delta"], 3), // 6 items here
    ]);
    expect(m.itemCount).toBe(2 + 1 + 6);
  });

  it("returns zeros when no quotes are pending distribution", () => {
    expect(aggregateDistributionMetrics([])).toEqual({
      quoteCount: 0,
      brandSliceCount: 0,
      itemCount: 0,
    });
  });
});

describe("sidebar badge contract — РОЗ-57 regression", () => {
  it("the sidebar value (quoteCount) is NOT the same as the brand-slice count when a quote has multiple brands", () => {
    // 4 distinct quotes, but one of them has 2 brands → 5 brand-slices.
    // The sidebar badge must read 4 (= /quotes table grouping), the page
    // header subtitle still surfaces "5 карточек" via brandSliceCount.
    const m = aggregateDistributionMetrics([
      makeQuote("a", ["Alfa"], 1),
      makeQuote("b", ["Beta"], 1),
      makeQuote("c", ["Gamma"], 1),
      makeQuote("d", ["Delta", "Epsilon"], 1),
    ]);
    expect(m.quoteCount).toBe(4);
    expect(m.brandSliceCount).toBe(5);
    // Reading the sidebar number out of metrics directly — the badge query
    // does the same thing on top of fetched data.
    expect(m.quoteCount).not.toBe(m.brandSliceCount);
  });

  it("when every quote has exactly one brand, sidebar and page header agree", () => {
    const m = aggregateDistributionMetrics([
      makeQuote("a", ["Alfa"], 1),
      makeQuote("b", ["Beta"], 1),
      makeQuote("c", ["Gamma"], 1),
    ]);
    expect(m.quoteCount).toBe(m.brandSliceCount);
  });
});
