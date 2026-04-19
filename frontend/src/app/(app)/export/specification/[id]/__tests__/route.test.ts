import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Task 11 — spec export route reads items via invoice_items
 * instead of quote_items (Pattern B).
 *
 * Legacy behavior: .from("quote_items").select("brand, product_code,
 * product_name, unit, quantity, base_price_vat").eq("quote_id", X)
 *
 * Migration 284 drops `base_price_vat` and `product_code` from
 * quote_items; the composed sale prices now live on invoice_items. The
 * route now walks composition: for each quote_item of the spec's quote,
 * find its composition_selected_invoice_id, then pull the covering
 * invoice_items for that invoice.
 *
 * We use a single JOIN through invoice_item_coverage → invoice_items so
 * split/merge cases are handled implicitly.
 *
 * The renderer's props shape (SpecDocument.items) is unchanged — the
 * route's job is to assemble that shape from the new schema.
 */

// react-pdf/renderer's renderToBuffer pulls in stream/Buffer machinery we
// don't want to exercise in unit tests. Stub it to inspect the JSX element
// passed in: its props are what the handler constructed from Supabase
// data. This is enough to assert the items payload shape. The other
// named exports (Font, Document, Page, etc.) are referenced by
// SpecDocument at module-load time — stub them so the import succeeds.
vi.mock("@react-pdf/renderer", () => {
  const noop = () => null;
  return {
    renderToBuffer: vi.fn(
      async (element: { props?: Record<string, unknown> }) => {
        capturedSpecDocumentProps = element?.props ?? undefined;
        return new Uint8Array([0x25, 0x50, 0x44, 0x46]);
      }
    ),
    Font: {
      register: vi.fn(),
      registerHyphenationCallback: vi.fn(),
    },
    StyleSheet: { create: (x: unknown) => x },
    Document: noop,
    Page: noop,
    View: noop,
    Text: noop,
    Image: noop,
  };
});

interface FromCall {
  table: string;
  selectCols?: string;
}

interface FakeSupabase {
  fromCalls: FromCall[];
  specRow: Record<string, unknown> | null;
  quoteRow: Record<string, unknown> | null;
  customerRow: Record<string, unknown> | null;
  contractRow: Record<string, unknown> | null;
  /** New Pattern B source: invoice_items via composition. */
  composedItemsRow: Record<string, unknown> | null;
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;
let capturedSpecDocumentProps: Record<string, unknown> | undefined;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fakeSupabase,
}));

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    fromCalls: [],
    specRow: null,
    quoteRow: null,
    customerRow: null,
    contractRow: null,
    composedItemsRow: null,
    from(table: string) {
      return {
        select: (cols: string) => {
          state.fromCalls.push({ table, selectCols: cols });
          const chain: Record<string, unknown> = {};
          chain.eq = () => chain;
          chain.is = () => chain;
          chain.order = () => chain;
          chain.single = async () => {
            if (table === "specifications") {
              return { data: state.specRow, error: state.specRow ? null : { code: "PGRST116" } };
            }
            if (table === "quotes") {
              // Two flows hit "quotes":
              //   (a) basic quote lookup (id, idn_quote, customer_id, currency)
              //   (b) composition join for items (select contains quote_items!inner(...))
              if (/quote_items!inner/.test(cols)) {
                return { data: state.composedItemsRow, error: null };
              }
              return { data: state.quoteRow, error: null };
            }
            if (table === "customer_contracts") {
              return { data: state.contractRow, error: null };
            }
            if (table === "customers") {
              return { data: state.customerRow, error: null };
            }
            if (table === "invoice_items" || table === "invoice_item_coverage") {
              // Pattern B fallback: route may also fetch invoice_items
              // directly with .eq("invoice_id", X). Either shape is
              // acceptable; the assertion below covers it.
              return { data: state.composedItemsRow, error: null };
            }
            return { data: null, error: null };
          };
          // For invoice_items direct fetches the route calls .order() then
          // awaits the promise. Make the chain thenable.
          (chain as { then: unknown }).then = (
            resolve: (v: unknown) => unknown
          ) => {
            if (table === "invoice_items" || table === "invoice_item_coverage") {
              return Promise.resolve({
                data: state.composedItemsRow,
                error: null,
              }).then(resolve);
            }
            // Fallback: resolves to empty.
            return Promise.resolve({ data: [], error: null }).then(resolve);
          };
          return chain;
        },
      };
    },
  };
  return state;
}

async function callRoute() {
  const { GET } = await import("../route");
  const req = new Request("http://localhost/export/specification/spec-1");
  const params = Promise.resolve({ id: "spec-1" });
  return GET(req, { params });
}

describe("spec export route — Phase 5d Pattern B", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    capturedSpecDocumentProps = undefined;

    // Baseline fixtures: a complete spec, quote, customer, and one composed item.
    fakeSupabase.specRow = {
      id: "spec-1",
      quote_id: "q-1",
      contract_id: null,
      specification_number: "SP-001",
      sign_date: "2026-03-01",
      readiness_period: "30",
      status: "signed",
    };
    fakeSupabase.quoteRow = {
      id: "q-1",
      idn_quote: "Q-202603-0001",
      customer_id: "cust-1",
      currency: "RUB",
    };
    fakeSupabase.customerRow = {
      id: "cust-1",
      name: "OOO Ромашка",
      inn: "1234567890",
    };
    fakeSupabase.contractRow = null;
    // Composed items shape — route must assemble this from invoice_items
    // filtered by composition_selected_invoice_id.
    fakeSupabase.composedItemsRow = {
      id: "q-1",
      quote_items: [
        {
          id: "qi-1",
          position: 1,
          composition_selected_invoice_id: "inv-A",
          brand: "SKF",
          coverage: [
            {
              invoice_items: {
                invoice_id: "inv-A",
                supplier_sku: "SKF-205",
                product_name: "Подшипник SKF-205",
                brand: "SKF",
                base_price_vat: 1000,
                quantity: 5,
              },
            },
          ],
        },
      ],
    };
  });

  it("reads items from invoice_items via composition, not from quote_items legacy columns", async () => {
    await callRoute();

    const itemsCall = fakeSupabase.fromCalls.find((c) => {
      const cols = c.selectCols ?? "";
      // Pattern B — either direct invoice_items read or joined
      // quotes → quote_items → coverage → invoice_items.
      return (
        c.table === "invoice_items" ||
        c.table === "invoice_item_coverage" ||
        (c.table === "quotes" && /invoice_item_coverage|invoice_items/.test(cols))
      );
    });

    expect(itemsCall).toBeDefined();

    // It must not perform a direct quote_items select with the legacy
    // base_price_vat column.
    const legacyQuoteItemsCall = fakeSupabase.fromCalls.find(
      (c) =>
        c.table === "quote_items" &&
        /base_price_vat/.test(c.selectCols ?? "")
    );
    expect(legacyQuoteItemsCall).toBeUndefined();
  });

  it("passes the composed items to SpecDocument with the expected shape", async () => {
    await callRoute();

    expect(capturedSpecDocumentProps).toBeDefined();
    const items = capturedSpecDocumentProps!.items as Array<{
      brand: string | null;
      product_code: string | null;
      product_name: string;
      unit: string | null;
      quantity: number | null;
      base_price_vat: number | null;
    }>;

    expect(Array.isArray(items)).toBe(true);
    expect(items).toHaveLength(1);
    expect(items[0]).toMatchObject({
      product_name: "Подшипник SKF-205",
      brand: "SKF",
      product_code: "SKF-205",
      quantity: 5,
      base_price_vat: 1000,
    });
    // unit is not on invoice_items; the PDF renderer applies its own
    // fallback ("шт"). The route returns null here — migration 284
    // drops the legacy quote_items.unit column.
    expect(items[0].unit).toBeNull();
  });
});
