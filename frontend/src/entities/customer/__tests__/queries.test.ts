import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Task 11 — fetchCustomerPositions now reads price data via
 * invoice_item_coverage → invoice_items filtered by quote_items
 * composition_selected_invoice_id (Pattern C).
 *
 * Legacy behavior: SELECT purchase_price_original, purchase_currency,
 * procurement_completed_at directly from quote_items.
 *
 * Migration 284 drops these columns from quote_items; the data now lives
 * on invoice_items (price + currency) and on invoices
 * (procurement_completed_at). Composition of "which invoice_item counts"
 * comes from quote_items.composition_selected_invoice_id, resolved via
 * invoice_item_coverage.
 */

interface FromCall {
  table: string;
  selectCols?: string;
}

interface FakeSupabase {
  /** Captured .from(…) + .select(…) combos in invocation order. */
  fromCalls: FromCall[];
  /** Rows returned for the quotes!inner composition join. */
  quotesRows: unknown[];
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
    quotesRows: [],
    from(table: string) {
      // The new query shape pulls from "quotes" with a chained join:
      //   .from("quotes")
      //   .select("id, idn_quote, customer_id,
      //           quote_items!inner(
      //             id, product_name, brand, supplier_sku, idn_sku,
      //             quantity, created_at, composition_selected_invoice_id,
      //             coverage:invoice_item_coverage!quote_item_id(
      //               invoice_items!inner(
      //                 invoice_id,
      //                 purchase_price_original,
      //                 purchase_currency,
      //                 invoices!inner(procurement_completed_at)
      //               )
      //             )
      //           )")
      //   .eq("customer_id", customerId)
      //   .order("quote_items.created_at", { ascending: false })
      //   .limit(100);
      //
      // We capture the first .from() + .select() so tests can assert the
      // new table is "quotes" and the select string references
      // invoice_item_coverage + invoice_items rather than legacy columns.
      return {
        select: (cols: string) => {
          state.fromCalls.push({ table, selectCols: cols });
          const chain = {
            eq: () => chain,
            order: () => chain,
            limit: async () => ({ data: state.quotesRows, error: null }),
            then: undefined,
          };
          return chain;
        },
      };
    },
  };
  return state;
}

describe("fetchCustomerPositions — Phase 5d Pattern C", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("queries invoice_item_coverage + invoice_items, not legacy columns on quote_items", async () => {
    fakeSupabase.quotesRows = [];
    const { fetchCustomerPositions } = await import("../queries");

    await fetchCustomerPositions("customer-1");

    expect(fakeSupabase.fromCalls.length).toBeGreaterThan(0);
    const primary = fakeSupabase.fromCalls[0];
    const cols = primary.selectCols ?? "";

    // RED assertion: the refactored query must reference the new shape
    expect(cols).toContain("invoice_item_coverage");
    expect(cols).toContain("invoice_items");

    // It must NOT read the legacy price columns as direct selections on
    // quote_items. Extract the quote_items!inner(...) payload and verify
    // its OWN column list (before the first nested JOIN) excludes the
    // legacy columns. Nested columns on invoice_items are fine.
    const qiMatch = /quote_items!inner\(([^()]*)/.exec(cols);
    expect(qiMatch).not.toBeNull();
    const qiDirectCols = qiMatch?.[1] ?? "";
    expect(qiDirectCols).not.toMatch(/purchase_price_original/);
    expect(qiDirectCols).not.toMatch(/purchase_currency/);
    expect(qiDirectCols).not.toMatch(/procurement_completed_at/);
  });

  it("flattens coverage → picks the invoice_item matching composition_selected_invoice_id", async () => {
    // One quote, one quote_item covered by two invoice_items in two different
    // invoices. The composition pointer selects invoice B; only that row
    // contributes to the returned shape.
    fakeSupabase.quotesRows = [
      {
        id: "q-1",
        idn_quote: "Q-202601-0001",
        customer_id: "customer-1",
        quote_items: [
          {
            id: "qi-1",
            product_name: "Болт М8",
            brand: "ABB",
            supplier_sku: "ABB-BOLT-M8",
            idn_sku: "SKU-1",
            quantity: 100,
            created_at: "2026-03-01T00:00:00Z",
            composition_selected_invoice_id: "inv-B",
            coverage: [
              {
                invoice_items: {
                  invoice_id: "inv-A",
                  purchase_price_original: 11.11,
                  purchase_currency: "EUR",
                  invoices: { procurement_completed_at: null },
                },
              },
              {
                invoice_items: {
                  invoice_id: "inv-B",
                  purchase_price_original: 9.99,
                  purchase_currency: "USD",
                  invoices: { procurement_completed_at: "2026-03-05T12:00:00Z" },
                },
              },
            ],
          },
        ],
      },
    ];

    const { fetchCustomerPositions } = await import("../queries");
    const rows = await fetchCustomerPositions("customer-1");

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      id: "qi-1",
      product_name: "Болт М8",
      brand: "ABB",
      sku: "ABB-BOLT-M8",
      idn_sku: "SKU-1",
      quantity: 100,
      purchase_price: 9.99,
      purchase_currency: "USD",
      procurement_date: "2026-03-05T12:00:00Z",
      quote_idn: "Q-202601-0001",
    });
  });

  it("omits purchase_price when no coverage matches composition_selected_invoice_id", async () => {
    // Uncovered quote_item: composition pointer is null or no coverage row
    // matches. Row still renders with null price so the UI can show the
    // line as 'no price yet'.
    fakeSupabase.quotesRows = [
      {
        id: "q-1",
        idn_quote: "Q-202601-0002",
        customer_id: "customer-1",
        quote_items: [
          {
            id: "qi-2",
            product_name: "Гайка",
            brand: null,
            supplier_sku: null,
            idn_sku: null,
            quantity: 50,
            created_at: "2026-03-02T00:00:00Z",
            composition_selected_invoice_id: null,
            coverage: [],
          },
        ],
      },
    ];

    const { fetchCustomerPositions } = await import("../queries");
    const rows = await fetchCustomerPositions("customer-1");

    expect(rows).toHaveLength(1);
    expect(rows[0].purchase_price).toBeNull();
    expect(rows[0].purchase_currency).toBeNull();
    expect(rows[0].procurement_date).toBeNull();
  });

  it("returns an empty array when supabase returns no rows", async () => {
    fakeSupabase.quotesRows = [];
    const { fetchCustomerPositions } = await import("../queries");
    const rows = await fetchCustomerPositions("customer-1");
    expect(rows).toEqual([]);
  });
});
