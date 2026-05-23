import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5c Task 10 — rewrite of assignItemsToInvoice for invoice_items +
 * invoice_item_coverage.
 *
 * Old behavior (Phase 5b):
 *   1. UPDATE quote_items SET invoice_id = X, composition_selected_invoice_id = X
 *   2. UPSERT invoice_item_prices (invoice_id, quote_item_id, price fields)
 *
 * New behavior (Phase 5c):
 *   1. SELECT quote_items rows for seeding defaults
 *   2. SELECT invoice for organization_id (RLS)
 *   3. SELECT MAX(position) within target invoice
 *   4. INSERT invoice_items rows (one per quote_item, with defaults)
 *   5. UPSERT invoice_item_coverage rows (ratio=1) — ON CONFLICT DO NOTHING
 *   6. UPDATE quote_items.composition_selected_invoice_id = invoiceId
 *
 * No write to quote_items.invoice_id (dropped in migration 284).
 * No write to invoice_item_prices (dropped in migration 284).
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface InsertedInvoiceItem {
  invoice_id: string;
  organization_id: string;
  position: number;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  purchase_currency: string;
  vat_rate: number | null;
  version: number;
}

interface InsertedCoverage {
  invoice_item_id: string;
  quote_item_id: string;
  ratio: number;
}

interface FakeSupabase {
  // Data fixtures
  quoteItems: Array<{
    id: string;
    quote_id: string;
    product_name: string | null;
    supplier_sku: string | null;
    brand: string | null;
    quantity: number;
    idn_sku: string | null;
    vat_rate: number | null;
    // `position` mirrors `kvota.quote_items.position` so the mock can return
    // rows in a controlled order via .order("position"). Defaults to fixture
    // index when omitted by older tests that don't care about ordering.
    position?: number;
  }>;
  invoice: { id: string; quote_id: string } | null;
  quote: { id: string; organization_id: string } | null;
  existingInvoiceItemsMaxPosition: number;
  createdInvoiceItemIdCounter: number;

  // Captured calls
  insertedInvoiceItems: InsertedInvoiceItem[];
  upsertedCoverage: InsertedCoverage[];
  upsertCoverageOpts: { onConflict?: string; ignoreDuplicates?: boolean } | null;
  updatedQuoteItems: Array<{ ids: string[]; updates: Record<string, unknown> }>;

  // Forbidden-write tracking (guards against legacy behaviour)
  wroteToInvoiceItemPrices: boolean;
  wroteLegacyInvoiceId: boolean;

  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    quoteItems: [],
    // `kvota.invoices` has no organization_id column (Phase 5d discovery);
    // the org boundary lives on `kvota.quotes` and is inherited through
    // quote_id. Mock reflects the real schema.
    invoice: { id: "inv-A", quote_id: "q-1" },
    quote: { id: "q-1", organization_id: "org-1" },
    existingInvoiceItemsMaxPosition: 0,
    createdInvoiceItemIdCounter: 0,
    insertedInvoiceItems: [],
    upsertedCoverage: [],
    upsertCoverageOpts: null,
    updatedQuoteItems: [],
    wroteToInvoiceItemPrices: false,
    wroteLegacyInvoiceId: false,
    from(table: string) {
      if (table === "invoice_item_prices") {
        // Any write here = legacy behavior bleeding through
        return {
          upsert: async () => {
            state.wroteToInvoiceItemPrices = true;
            return { error: null };
          },
          insert: async () => {
            state.wroteToInvoiceItemPrices = true;
            return { error: null };
          },
        };
      }
      if (table === "quote_items") {
        return {
          select: (_cols: string) => ({
            // Builder pattern: supports both `.in(...)` (legacy direct await)
            // and `.in(...).order("position", { ascending: true })` (current
            // assignItemsToInvoice — fixes Testing 2 row 68 where КПП rows
            // appeared shuffled because Supabase IN returns no guaranteed
            // order). The `then` keeps the builder thenable for tests that
            // don't chain `.order`.
            in: (_col: string, ids: string[]) => {
              const filtered = state.quoteItems.filter((qi) =>
                ids.includes(qi.id)
              );
              const positionOf = (qi: { id: string; position?: number }) => {
                if (typeof qi.position === "number") return qi.position;
                return state.quoteItems.findIndex((q) => q.id === qi.id);
              };
              return {
                order: async (
                  col: string,
                  opts?: { ascending?: boolean }
                ) => {
                  if (col !== "position") {
                    throw new Error(
                      `Unexpected order column on quote_items: ${col}`
                    );
                  }
                  const asc = opts?.ascending ?? true;
                  const sorted = [...filtered].sort((a, b) => {
                    const d = positionOf(a) - positionOf(b);
                    return asc ? d : -d;
                  });
                  return { data: sorted, error: null };
                },
                then(
                  resolve: (r: {
                    data: typeof filtered;
                    error: null;
                  }) => unknown
                ) {
                  return Promise.resolve({
                    data: filtered,
                    error: null,
                  }).then(resolve);
                },
              };
            },
          }),
          update: (updates: Record<string, unknown>) => {
            if ("invoice_id" in updates) {
              state.wroteLegacyInvoiceId = true;
            }
            return {
              in: async (_col: string, ids: string[]) => {
                state.updatedQuoteItems.push({ ids, updates });
                return { error: null };
              },
            };
          },
        };
      }
      if (table === "invoices") {
        return {
          select: () => ({
            eq: () => ({
              single: async () => ({
                data: state.invoice,
                error: null,
              }),
            }),
          }),
        };
      }
      if (table === "quotes") {
        // Used by getInvoiceOrganizationId: invoice → quote_id → quote.org_id.
        return {
          select: () => ({
            eq: () => ({
              single: async () => ({
                data: state.quote,
                error: null,
              }),
            }),
          }),
        };
      }
      if (table === "invoice_items") {
        return {
          select: () => ({
            eq: () => ({
              order: () => ({
                limit: async () => ({
                  data:
                    state.existingInvoiceItemsMaxPosition > 0
                      ? [{ position: state.existingInvoiceItemsMaxPosition }]
                      : [],
                  error: null,
                }),
              }),
            }),
          }),
          insert: (rows: InsertedInvoiceItem[]) => {
            state.insertedInvoiceItems.push(...rows);
            const created = rows.map(() => {
              state.createdInvoiceItemIdCounter += 1;
              return {
                id: `ii-${state.createdInvoiceItemIdCounter}`,
                invoice_id: rows[0].invoice_id,
              };
            });
            return {
              select: async (_cols: string) => ({
                data: created,
                error: null,
              }),
            };
          },
        };
      }
      if (table === "invoice_item_coverage") {
        return {
          // Phase 5c ghost-items pre-check: returns existing coverage rows for
          // the given quote_item ids. Default: no existing coverage.
          select: (_cols: string) => ({
            in: async (_col: string, _ids: string[]) => ({
              data: [] as Array<{
                quote_item_id: string;
                invoice_items: { invoice_id: string };
              }>,
              error: null,
            }),
          }),
          upsert: async (
            rows: InsertedCoverage[],
            opts?: { onConflict?: string; ignoreDuplicates?: boolean }
          ) => {
            state.upsertedCoverage.push(...rows);
            state.upsertCoverageOpts = opts ?? null;
            return { error: null };
          },
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("assignItemsToInvoice (Phase 5c) — new schema writes", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("inserts one invoice_items row per quote_item with defaults from quote_items", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "Болт М8",
        supplier_sku: "SKU-BOLT-8",
        brand: "ABB",
        quantity: 100,
        idn_sku: "IDN-1",
        vat_rate: 20,
      },
      {
        id: "qi-2",
        quote_id: "q-1",
        product_name: "Гайка М8",
        supplier_sku: null,
        brand: "ABB",
        quantity: 200,
        idn_sku: "IDN-2",
        vat_rate: 20,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1", "qi-2"], "inv-A");

    expect(fakeSupabase.insertedInvoiceItems).toHaveLength(2);
    const [row1, row2] = fakeSupabase.insertedInvoiceItems;
    expect(row1.invoice_id).toBe("inv-A");
    expect(row1.organization_id).toBe("org-1");
    expect(row1.product_name).toBe("Болт М8");
    expect(row1.supplier_sku).toBe("SKU-BOLT-8");
    expect(row1.brand).toBe("ABB");
    expect(row1.quantity).toBe(100);
    expect(row1.vat_rate).toBe(20);
    expect(row1.version).toBe(1);
    expect(row2.product_name).toBe("Гайка М8");
    expect(row2.quantity).toBe(200);
  });

  it("computes invoice_items.position as MAX(position) + 1 + i within target invoice", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
      {
        id: "qi-2",
        quote_id: "q-1",
        product_name: "B",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];
    fakeSupabase.existingInvoiceItemsMaxPosition = 5;

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1", "qi-2"], "inv-A");

    expect(fakeSupabase.insertedInvoiceItems[0].position).toBe(6);
    expect(fakeSupabase.insertedInvoiceItems[1].position).toBe(7);
  });

  it("starts position at 1 when target invoice has no existing invoice_items", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];
    fakeSupabase.existingInvoiceItemsMaxPosition = 0;

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1"], "inv-A");

    expect(fakeSupabase.insertedInvoiceItems[0].position).toBe(1);
  });

  it("upserts one invoice_item_coverage row per assignment with ratio=1 and onConflict ignoreDuplicates", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
      {
        id: "qi-2",
        quote_id: "q-1",
        product_name: "B",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1", "qi-2"], "inv-A");

    expect(fakeSupabase.upsertedCoverage).toHaveLength(2);
    for (const cov of fakeSupabase.upsertedCoverage) {
      expect(cov.ratio).toBe(1);
    }
    // Pair qi-1 → ii-1, qi-2 → ii-2
    expect(fakeSupabase.upsertedCoverage[0].quote_item_id).toBe("qi-1");
    expect(fakeSupabase.upsertedCoverage[0].invoice_item_id).toBe("ii-1");
    expect(fakeSupabase.upsertedCoverage[1].quote_item_id).toBe("qi-2");
    expect(fakeSupabase.upsertedCoverage[1].invoice_item_id).toBe("ii-2");
    // ON CONFLICT DO NOTHING via upsert ignoreDuplicates
    expect(fakeSupabase.upsertCoverageOpts).toMatchObject({
      onConflict: "invoice_item_id,quote_item_id",
      ignoreDuplicates: true,
    });
  });

  it("updates quote_items.composition_selected_invoice_id = invoiceId for all assigned items", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1"], "inv-A");

    expect(fakeSupabase.updatedQuoteItems).toHaveLength(1);
    const update = fakeSupabase.updatedQuoteItems[0];
    expect(update.ids).toEqual(["qi-1"]);
    expect(update.updates).toEqual({
      composition_selected_invoice_id: "inv-A",
    });
  });

  it("never writes to quote_items.invoice_id (column dropped in migration 284)", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1"], "inv-A");

    expect(fakeSupabase.wroteLegacyInvoiceId).toBe(false);
  });

  it("never writes to invoice_item_prices (table dropped in migration 284)", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice(["qi-1"], "inv-A");

    expect(fakeSupabase.wroteToInvoiceItemPrices).toBe(false);
  });

  it("inserts invoice_items in source quote_items.position order, regardless of Supabase fetch order (Testing 2 row 68)", async () => {
    // Regression for МОЗ "Позиции перемешиваются" — Testing 2 row 68.
    // Setup: fixtures intentionally out of position order. The fixture array
    // order mimics what Supabase IN returns when planner picks an index
    // scan — implementation-defined, NEVER the input list order.
    // After fix: assignItemsToInvoice must explicitly sort by source
    // quote_items.position so the КПП reflects the customer's original
    // numbering.
    fakeSupabase.quoteItems = [
      {
        id: "qi-third",
        quote_id: "q-1",
        product_name: "Третий",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
        position: 3,
      },
      {
        id: "qi-first",
        quote_id: "q-1",
        product_name: "Первый",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
        position: 1,
      },
      {
        id: "qi-second",
        quote_id: "q-1",
        product_name: "Второй",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
        position: 2,
      },
    ];

    const { assignItemsToInvoice } = await import("../mutations");
    // Caller passes IDs in arbitrary order — the contract is that source
    // position drives the КПП ordering, not selection order.
    await assignItemsToInvoice(
      ["qi-third", "qi-first", "qi-second"],
      "inv-A"
    );

    expect(fakeSupabase.insertedInvoiceItems).toHaveLength(3);
    const productNames = fakeSupabase.insertedInvoiceItems.map(
      (r) => r.product_name
    );
    expect(productNames).toEqual(["Первый", "Второй", "Третий"]);
    // Positions counted from MAX+1 (= 1, since fixture has no existing rows)
    const positions = fakeSupabase.insertedInvoiceItems.map((r) => r.position);
    expect(positions).toEqual([1, 2, 3]);

    // Coverage rows must pair invoice_items 1-2-3 with the source
    // quote_items in the SAME order — invoice_item ii-1 covers qi-first
    // (position 1), not qi-third (which was first in fixture).
    expect(fakeSupabase.upsertedCoverage[0].quote_item_id).toBe("qi-first");
    expect(fakeSupabase.upsertedCoverage[1].quote_item_id).toBe("qi-second");
    expect(fakeSupabase.upsertedCoverage[2].quote_item_id).toBe("qi-third");
  });

  it("is a no-op (returns early) when itemIds is empty", async () => {
    const { assignItemsToInvoice } = await import("../mutations");
    await assignItemsToInvoice([], "inv-A");

    expect(fakeSupabase.insertedInvoiceItems).toHaveLength(0);
    expect(fakeSupabase.upsertedCoverage).toHaveLength(0);
    expect(fakeSupabase.updatedQuoteItems).toHaveLength(0);
  });

  it("throws when the target invoice is not found (RLS/invalid ID)", async () => {
    fakeSupabase.quoteItems = [
      {
        id: "qi-1",
        quote_id: "q-1",
        product_name: "A",
        supplier_sku: null,
        brand: null,
        quantity: 1,
        idn_sku: null,
        vat_rate: null,
      },
    ];
    fakeSupabase.invoice = null;

    const { assignItemsToInvoice } = await import("../mutations");
    await expect(
      assignItemsToInvoice(["qi-1"], "inv-missing")
    ).rejects.toThrow(/invoice not found/i);
  });
});
