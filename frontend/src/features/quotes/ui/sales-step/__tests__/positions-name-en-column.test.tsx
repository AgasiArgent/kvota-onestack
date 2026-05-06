import { describe, it, expect, vi } from "vitest";

/**
 * РОЗ test follow-up to PR #116 — adds an editable «Наименование (EN)»
 * column to the sales-side positions handsontable so МОЗ can populate
 * `quote_items.name_en`. Without data, the procurement КП export and
 * letter composer fall back to `product_name`, which is Russian.
 *
 * @handsontable/react + handsontable touch DOM at module load. We mock
 * them out and assert the exported column contract directly — same pattern
 * used in `procurement-handsontable.test.tsx` (Phase 5d Task 14).
 */

vi.mock("@handsontable/react", () => ({
  HotTable: () => null,
}));
vi.mock("handsontable", () => ({
  default: {},
  renderers: {
    TextRenderer: () => {},
    NumericRenderer: () => {},
  },
}));
vi.mock("handsontable/registry", () => ({
  registerAllModules: () => {},
}));
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

vi.mock("@/entities/quote/mutations", () => ({
  createQuoteItemsBatch: async () => [],
  updateQuoteItem: async () => ({}),
  deleteQuoteItem: async () => undefined,
}));

import { SALES_COLUMN_KEYS } from "../sales-items-handsontable";

describe("sales-items-handsontable — name_en column contract", () => {
  it("includes `name_en` in the column key list", () => {
    expect(SALES_COLUMN_KEYS).toContain("name_en");
  });

  it("places `name_en` directly after `product_name` so the EN field sits next to the RU one", () => {
    const productNameIdx = SALES_COLUMN_KEYS.indexOf("product_name");
    const nameEnIdx = SALES_COLUMN_KEYS.indexOf("name_en");
    expect(productNameIdx).toBeGreaterThanOrEqual(0);
    expect(nameEnIdx).toBe(productNameIdx + 1);
  });

  it("keeps the legacy sales column contract: brand → product_code → product_name → name_en → quantity → unit", () => {
    // Lock the order so future edits don't accidentally reshuffle the
    // sales-side row (which would silently break the Handsontable column
    // ↔ data-source binding).
    expect(SALES_COLUMN_KEYS).toEqual([
      "brand",
      "product_code",
      "product_name",
      "name_en",
      "quantity",
      "unit",
    ]);
  });
});
