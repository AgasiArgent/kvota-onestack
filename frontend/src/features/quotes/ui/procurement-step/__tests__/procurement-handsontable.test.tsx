import { describe, it, expect, vi } from "vitest";

/**
 * Phase 5d Task 14 (Agent C) — procurement-handsontable tests.
 *
 * Verifies:
 *   - COLUMN_KEYS bind to invoice_items field names
 *   - `minimum_order_quantity` (invoice_items) replaces `min_order_quantity`
 *     (legacy quote_items name)
 *   - Supplier-side columns (purchase_price_original, production_time_days,
 *     weight_in_kg, dimensions) remain bound to invoice_items
 *
 * Next.js dynamic imports + Handsontable rendering are heavy for SSR, so we
 * import only the exported COLUMN_KEYS constant and assert directly.
 */

// The handsontable module imports @handsontable/react + handsontable. Both
// touch DOM APIs at module load — stub to avoid evaluation in the test env.
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

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ eq: async () => ({ data: [], error: null }) }),
      update: () => ({ eq: async () => ({ data: null, error: null }) }),
    }),
  }),
}));

vi.mock("@/entities/quote/mutations", () => ({
  updateInvoiceItem: async () => ({}),
  unassignInvoiceItem: async () => ({}),
}));

import { PROCUREMENT_COLUMN_KEYS } from "../procurement-handsontable";

describe("procurement-handsontable — COLUMN_KEYS bind to invoice_items schema", () => {
  it("exports PROCUREMENT_COLUMN_KEYS as an ordered array", () => {
    expect(Array.isArray(PROCUREMENT_COLUMN_KEYS)).toBe(true);
    expect(PROCUREMENT_COLUMN_KEYS.length).toBeGreaterThan(0);
  });

  it("uses invoice_items `minimum_order_quantity` (not legacy `min_order_quantity`)", () => {
    // quote_items.min_order_quantity (dropped in migration 284) vs
    // invoice_items.minimum_order_quantity (the new canonical name)
    expect(PROCUREMENT_COLUMN_KEYS).toContain("minimum_order_quantity");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("min_order_quantity");
  });

  it("keeps invoice_items supplier-side pricing/timing/weight keys", () => {
    // These columns live on invoice_items (verified against migration 281).
    expect(PROCUREMENT_COLUMN_KEYS).toContain("purchase_price_original");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("production_time_days");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("weight_in_kg");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("supplier_sku");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("quantity");
  });

  it("keeps identity keys shared with invoice_items", () => {
    // product_name + brand both exist on invoice_items (supplier-side copy).
    expect(PROCUREMENT_COLUMN_KEYS).toContain("product_name");
    expect(PROCUREMENT_COLUMN_KEYS).toContain("brand");
  });

  it("uses composed `dimensions` column (aggregating dimension_*_mm on invoice_items)", () => {
    // Sugar column — aggregates the three dimension_*_mm columns that exist
    // on invoice_items. Kept in COLUMN_KEYS for the editor to expose a
    // single "В×Ш×Д" cell.
    expect(PROCUREMENT_COLUMN_KEYS).toContain("dimensions");
  });

  it("drops quote_items-only columns that no longer source row data post-284", () => {
    // Migration 284 drops these from quote_items. They have no invoice_items
    // counterpart; the handsontable should not bind to them as row keys.
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("product_code");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("manufacturer_product_name");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("name_en");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("is_unavailable");
    expect(PROCUREMENT_COLUMN_KEYS).not.toContain("supplier_sku_note");
  });
});
