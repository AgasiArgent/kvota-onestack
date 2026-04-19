import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Task 11 — fetchSupplierQuoteItems now reads price data via
 * invoice_item_coverage → invoice_items filtered by quote_items
 * composition_selected_invoice_id (Pattern C).
 *
 * Supplier-scoped positions are those where a supplier's invoice currently
 * provides pricing for a quote_item. Before Phase 5c this was denormalized
 * as quote_items.supplier_id + legacy price columns; after Phase 5c the
 * truth lives on invoice_items via invoice_item_coverage.
 *
 * The refactored query selects invoices owned by the supplier, walks their
 * invoice_items → coverage → quote_items, keeping only rows whose parent
 * quote_item points at this invoice via composition_selected_invoice_id.
 */

interface FromCall {
  table: string;
  selectCols?: string;
}

interface FakeSupabase {
  fromCalls: FromCall[];
  invoicesRows: unknown[];
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fakeSupabase,
  createAdminClient: () => fakeSupabase,
}));

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    fromCalls: [],
    invoicesRows: [],
    from(table: string) {
      return {
        select: (cols: string) => {
          state.fromCalls.push({ table, selectCols: cols });
          const chain = {
            eq: () => chain,
            order: () => chain,
            limit: async () => ({ data: state.invoicesRows, error: null }),
            then: undefined,
          };
          return chain;
        },
      };
    },
  };
  return state;
}

describe("fetchSupplierQuoteItems — Phase 5d Pattern C", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("queries invoice_item_coverage + invoice_items, not legacy columns on quote_items", async () => {
    fakeSupabase.invoicesRows = [];
    const { fetchSupplierQuoteItems } = await import("../queries");

    await fetchSupplierQuoteItems("supplier-1");

    expect(fakeSupabase.fromCalls.length).toBeGreaterThan(0);
    const primary = fakeSupabase.fromCalls[0];
    const cols = primary.selectCols ?? "";

    expect(cols).toContain("invoice_item_coverage");
    expect(cols).toContain("invoice_items");

    // It must not directly read the legacy price columns as siblings
    // of the quote_items select — they come from invoice_items now.
    const qiMatch = /quote_items!inner\(([^()]*)/.exec(cols);
    if (qiMatch) {
      const qiDirectCols = qiMatch[1] ?? "";
      expect(qiDirectCols).not.toMatch(/purchase_price_original/);
      expect(qiDirectCols).not.toMatch(/purchase_currency/);
      expect(qiDirectCols).not.toMatch(/procurement_completed_at/);
    }
  });

  it("returns supplier positions with price sourced from the composed invoice_item", async () => {
    // One invoice owned by supplier-1, containing one invoice_item which
    // covers quote_item qi-1. The quote_item's composition pointer matches
    // this invoice, so the row shows up with that invoice's price.
    fakeSupabase.invoicesRows = [
      {
        id: "inv-A",
        supplier_id: "supplier-1",
        procurement_completed_at: "2026-03-08T09:00:00Z",
        invoice_items: [
          {
            id: "ii-1",
            invoice_id: "inv-A",
            purchase_price_original: 42.5,
            purchase_currency: "USD",
            coverage: [
              {
                quote_items: {
                  id: "qi-1",
                  product_name: "Подшипник 6205",
                  brand: "SKF",
                  supplier_sku: "SKF-6205",
                  idn_sku: "SKU-A",
                  quantity: 10,
                  composition_selected_invoice_id: "inv-A",
                  created_at: "2026-03-07T00:00:00Z",
                  quotes: { idn_quote: "Q-202603-0001" },
                },
              },
            ],
          },
        ],
      },
    ];

    const { fetchSupplierQuoteItems } = await import("../queries");
    const rows = await fetchSupplierQuoteItems("supplier-1");

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "qi-1",
      product_name: "Подшипник 6205",
      brand: "SKF",
      sku: "SKF-6205",
      idn_sku: "SKU-A",
      quantity: 10,
      purchase_price: 42.5,
      purchase_currency: "USD",
      procurement_date: "2026-03-08T09:00:00Z",
      quote_idn: "Q-202603-0001",
    });
  });

  it("excludes coverage where the quote_item's composition pointer selects a different invoice", async () => {
    // supplier-1 owns invoice A, but the quote_item qi-2 points at invoice B.
    // The supplier's positions view must not show qi-2 — it's not in this
    // supplier's composition.
    fakeSupabase.invoicesRows = [
      {
        id: "inv-A",
        supplier_id: "supplier-1",
        procurement_completed_at: null,
        invoice_items: [
          {
            id: "ii-1",
            invoice_id: "inv-A",
            purchase_price_original: 7.77,
            purchase_currency: "EUR",
            coverage: [
              {
                quote_items: {
                  id: "qi-2",
                  product_name: "Reject",
                  brand: null,
                  supplier_sku: null,
                  idn_sku: null,
                  quantity: 1,
                  composition_selected_invoice_id: "inv-OTHER",
                  created_at: "2026-03-07T00:00:00Z",
                  quotes: { idn_quote: "Q-X" },
                },
              },
            ],
          },
        ],
      },
    ];

    const { fetchSupplierQuoteItems } = await import("../queries");
    const rows = await fetchSupplierQuoteItems("supplier-1");

    expect(rows).toEqual([]);
  });

  it("returns an empty array when supabase returns no rows", async () => {
    fakeSupabase.invoicesRows = [];
    const { fetchSupplierQuoteItems } = await import("../queries");
    const rows = await fetchSupplierQuoteItems("supplier-1");
    expect(rows).toEqual([]);
  });
});
