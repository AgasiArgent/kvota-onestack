import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Task 11 — fetchPositionsList detail-rows query now sources
 * price data via invoice_item_coverage → invoice_items (Pattern C).
 *
 * Legacy detail query: SELECT purchase_price_original, purchase_currency
 * from quote_items joined with quotes. Migration 284 drops these columns;
 * prices now live on invoice_items.
 *
 * The page-level master query continues to hit positions_registry_view,
 * which is unaffected. Only the per-row detail (SourcingEntry) fetch
 * changes: it walks quote_items → composition_selected_invoice_id →
 * invoice_item_coverage → invoice_items to read price + currency.
 */

interface FromCall {
  table: string;
  selectCols?: string;
}

interface FakeSupabase {
  fromCalls: FromCall[];
  viewRows: unknown[];
  detailRows: unknown[];
  brandsRows: unknown[];
  managersRows: unknown[];
  userProfilesRows: unknown[];
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

vi.mock("@/shared/lib/supabase/server", () => ({
  createAdminClient: () => fakeSupabase,
}));

/** Minimal chain that resolves all known suffixes with the configured rows. */
function makeChain(
  resolveData: () => { data: unknown; error: unknown; count?: number | null }
) {
  const chain: Record<string, unknown> = {};
  chain.eq = () => chain;
  chain.neq = () => chain;
  chain.ilike = () => chain;
  chain.not = () => chain;
  chain.or = () => chain;
  chain.order = () => chain;
  chain.range = () => chain;
  chain.limit = () => chain;
  chain.in = () => chain;
  chain.gte = () => chain;
  chain.lte = () => chain;
  chain.then = (resolve: (v: unknown) => unknown) => resolve(resolveData());
  return chain;
}

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    fromCalls: [],
    viewRows: [],
    detailRows: [],
    brandsRows: [],
    managersRows: [],
    userProfilesRows: [],
    from(table: string) {
      return {
        select: (cols: string, opts?: { count?: string }) => {
          state.fromCalls.push({ table, selectCols: cols });
          if (table === "positions_registry_view") {
            // Master query is sorted+filtered but always resolves to
            // viewRows with total count. Filter options queries (brands,
            // managers) also come from this table — distinguish by select
            // columns: brands uses "brand", managers uses "last_moz_id,
            // last_moz_name".
            if (cols === "brand") {
              return makeChain(() => ({
                data: state.brandsRows,
                error: null,
              }));
            }
            if (cols.includes("last_moz_id")) {
              return makeChain(() => ({
                data: state.managersRows,
                error: null,
              }));
            }
            return makeChain(() => ({
              data: state.viewRows,
              error: null,
              count: state.viewRows.length,
              ...(opts?.count ? { count: state.viewRows.length } : {}),
            }));
          }
          if (table === "user_profiles") {
            return makeChain(() => ({
              data: state.userProfilesRows,
              error: null,
            }));
          }
          // Detail rows for current-page products. Pre-Phase-5d this was
          // "quote_items" directly; post-Phase-5d it must read the
          // composed shape through invoice_item_coverage → invoice_items.
          // Accept either table so the test can run against both old and
          // new code paths without synthetic stubbing gaps.
          if (
            table === "quote_items" ||
            table === "invoice_item_coverage" ||
            table === "invoice_items" ||
            table === "quotes"
          ) {
            return makeChain(() => ({
              data: state.detailRows,
              error: null,
            }));
          }
          throw new Error(`Unexpected supabase table in test: ${table}`);
        },
      };
    },
  };
  return state;
}

describe("fetchPositionsList — Phase 5d Pattern C", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("detail query must not read purchase_price_original directly from quote_items", async () => {
    // A page-product ensures the detail query branch runs at all.
    fakeSupabase.viewRows = [
      {
        brand: "ABB",
        product_code: "ABB-1",
        product_name: "Относится к",
        latest_price: 1,
        latest_currency: "EUR",
        last_moz_name: null,
        last_moz_id: null,
        last_updated: "2026-03-01T00:00:00Z",
        entry_count: 1,
        availability_status: "available",
        organization_id: "org-1",
      },
    ];
    fakeSupabase.brandsRows = [{ brand: "ABB" }];
    fakeSupabase.managersRows = [];

    const { fetchPositionsList } = await import("../queries");
    await fetchPositionsList("org-1", {});

    // The refactored detail query must reference invoice_item_coverage
    // or invoice_items. It must not SELECT legacy columns straight out
    // of quote_items.
    const detailCalls = fakeSupabase.fromCalls.filter(
      (c) =>
        c.table === "quote_items" ||
        c.table === "invoice_item_coverage" ||
        c.table === "invoice_items" ||
        c.table === "quotes"
    );
    expect(detailCalls.length).toBeGreaterThan(0);

    const joinedCols = detailCalls.map((c) => c.selectCols ?? "").join(" | ");

    expect(joinedCols).toMatch(/invoice_item_coverage|invoice_items/);

    // Guard: the quote_items direct select (top-level, before any nested
    // JOIN parens) must not request purchase_price_original or
    // purchase_currency — those come from the nested invoice_items JOIN.
    const qiCall = detailCalls.find((c) => c.table === "quote_items");
    if (qiCall) {
      const cols = qiCall.selectCols ?? "";
      // Top-level selects are everything before the first '(' (JOINs open
      // parens). Accept newlines in the select.
      const topLevel = cols.split("(")[0];
      expect(topLevel).not.toMatch(/purchase_price_original/);
      expect(topLevel).not.toMatch(/purchase_currency/);
      expect(topLevel).not.toMatch(/product_code/);
    }
  });

  it("renders detail entries with price sourced from invoice_items", async () => {
    fakeSupabase.viewRows = [
      {
        brand: "SKF",
        product_code: "SKF-205",
        product_name: "Подшипник",
        latest_price: 42,
        latest_currency: "USD",
        last_moz_name: null,
        last_moz_id: null,
        last_updated: "2026-03-09T00:00:00Z",
        entry_count: 1,
        availability_status: "available",
        organization_id: "org-1",
      },
    ];
    fakeSupabase.brandsRows = [{ brand: "SKF" }];
    fakeSupabase.managersRows = [];

    // Detail rows shape (Pattern C) — one quote_item joined with
    // invoice_item_coverage → invoice_items, plus its parent quote.
    fakeSupabase.detailRows = [
      {
        id: "qi-1",
        quote_id: "q-1",
        brand: "SKF",
        supplier_sku: "SKF-205",
        updated_at: "2026-03-09T09:00:00Z",
        is_unavailable: false,
        composition_selected_invoice_id: "inv-A",
        assigned_procurement_user: null,
        proforma_number: null,
        quotes: { idn: "Q-202603-0003", organization_id: "org-1" },
        coverage: [
          {
            invoice_items: {
              invoice_id: "inv-A",
              purchase_price_original: 42,
              purchase_currency: "USD",
            },
          },
        ],
      },
    ];

    const { fetchPositionsList } = await import("../queries");
    const result = await fetchPositionsList("org-1", {});

    expect(result.products).toHaveLength(1);
    const key = "SKF::SKF-205";
    const entries = result.details[key] ?? [];
    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      id: "qi-1",
      quoteId: "q-1",
      quoteIdn: "Q-202603-0003",
      price: 42,
      currency: "USD",
      isUnavailable: false,
    });
  });

  it("omits price when the quote_item has no matching coverage in the selected invoice", async () => {
    fakeSupabase.viewRows = [
      {
        brand: "X",
        product_code: "X-1",
        product_name: "Без цены",
        latest_price: null,
        latest_currency: null,
        last_moz_name: null,
        last_moz_id: null,
        last_updated: "2026-03-10T00:00:00Z",
        entry_count: 1,
        availability_status: "unavailable",
        organization_id: "org-1",
      },
    ];
    fakeSupabase.brandsRows = [{ brand: "X" }];
    fakeSupabase.managersRows = [];

    fakeSupabase.detailRows = [
      {
        id: "qi-2",
        quote_id: "q-2",
        brand: "X",
        supplier_sku: "X-1",
        updated_at: "2026-03-10T00:00:00Z",
        is_unavailable: true,
        composition_selected_invoice_id: null,
        assigned_procurement_user: null,
        proforma_number: null,
        quotes: { idn: "Q-X", organization_id: "org-1" },
        coverage: [],
      },
    ];

    const { fetchPositionsList } = await import("../queries");
    const result = await fetchPositionsList("org-1", {});

    const entries = result.details["X::X-1"] ?? [];
    expect(entries).toHaveLength(1);
    expect(entries[0].price).toBeNull();
    expect(entries[0].currency).toBeNull();
  });
});
