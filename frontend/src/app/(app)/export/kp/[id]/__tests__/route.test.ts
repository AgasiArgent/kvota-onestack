import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Phase 5d Group 5 Appendix — KP export route reads items via
 * invoice_items instead of quote_items (Pattern B).
 *
 * Legacy behavior: .from("quote_items").select("*").eq("quote_id", X)
 *
 * Migration 284 drops `base_price_vat` and `product_code` from
 * quote_items; the composed sale prices now live on invoice_items. The
 * route now walks composition: for each quote_item of the quote, find
 * its composition_selected_invoice_id, then pull the covering
 * invoice_items for that invoice.
 *
 * We use a single JOIN through invoice_item_coverage → invoice_items so
 * split/merge cases are handled implicitly.
 *
 * The renderer's props shape (KPDocument.items of type KPComposedItem)
 * is unchanged — the route's job is to assemble that shape from the new
 * schema.
 */

// react-pdf/renderer's renderToBuffer pulls in stream/Buffer machinery we
// don't want to exercise in unit tests. Stub it to inspect the JSX element
// passed in: its props are what the handler constructed from Supabase
// data. The other named exports (Font, Document, Page, etc.) are
// referenced by KPDocument at module-load time — stub them so the import
// succeeds.
vi.mock("@react-pdf/renderer", () => {
  const noop = () => null;
  return {
    renderToBuffer: vi.fn(
      async (element: { props?: Record<string, unknown> }) => {
        capturedKPDocumentProps = element?.props ?? undefined;
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
  quoteRow: Record<string, unknown> | null;
  customerRow: Record<string, unknown> | null;
  contactRow: Record<string, unknown> | null;
  creatorRow: Record<string, unknown> | null;
  calcVarsRow: Record<string, unknown> | null;
  /** New Pattern B source: invoice_items via composition. */
  composedItemsRow: Record<string, unknown> | null;
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;
let capturedKPDocumentProps: Record<string, unknown> | undefined;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => fakeSupabase,
}));

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    fromCalls: [],
    quoteRow: null,
    customerRow: null,
    contactRow: null,
    creatorRow: null,
    calcVarsRow: null,
    composedItemsRow: null,
    from(table: string) {
      return {
        select: (cols: string) => {
          state.fromCalls.push({ table, selectCols: cols });
          const chain: Record<string, unknown> = {};
          chain.eq = () => chain;
          chain.is = () => chain;
          chain.order = () => chain;
          chain.limit = () => chain;
          chain.single = async () => {
            if (table === "quotes") {
              // Two flows hit "quotes":
              //   (a) basic quote lookup (select "*") — for the KP header
              //   (b) composition join for items (select contains quote_items!inner(...))
              if (/quote_items!inner/.test(cols)) {
                return { data: state.composedItemsRow, error: null };
              }
              return { data: state.quoteRow, error: null };
            }
            if (table === "customers") {
              return { data: state.customerRow, error: null };
            }
            if (table === "customer_contacts") {
              return { data: state.contactRow, error: null };
            }
            if (table === "user_profiles") {
              return { data: state.creatorRow, error: null };
            }
            if (table === "quote_calculation_variables") {
              return { data: state.calcVarsRow, error: null };
            }
            if (table === "invoice_items" || table === "invoice_item_coverage") {
              return { data: state.composedItemsRow, error: null };
            }
            return { data: null, error: null };
          };
          // For invoice_items direct fetches the route may call .order()
          // then await — make the chain thenable for those flows.
          (chain as { then: unknown }).then = (
            resolve: (v: unknown) => unknown
          ) => {
            if (table === "invoice_items" || table === "invoice_item_coverage") {
              return Promise.resolve({
                data: state.composedItemsRow,
                error: null,
              }).then(resolve);
            }
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
  const req = new Request("http://localhost/export/kp/q-1");
  const params = Promise.resolve({ id: "q-1" });
  return GET(req, { params });
}

describe("KP export route — Phase 5d Pattern B", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
    capturedKPDocumentProps = undefined;

    // Baseline fixtures: a complete quote with customer, contact, and one
    // composed invoice item.
    fakeSupabase.quoteRow = {
      id: "q-1",
      idn_quote: "Q-202604-0001",
      customer_id: "cust-1",
      contact_person_id: "contact-1",
      created_by: "user-1",
      currency: "RUB",
      quote_date: "2026-04-18",
      created_at: "2026-04-18T00:00:00Z",
      delivery_city: "Москва",
      delivery_country: "Россия",
      delivery_address: null,
      incoterms: "DDP",
      payment_terms: "Предоплата 100%",
      delivery_days: 30,
      valid_until: "2026-05-18",
      manager_email: "manager@example.com",
    };
    fakeSupabase.customerRow = {
      id: "cust-1",
      name: "OOO Ромашка",
      inn: "1234567890",
    };
    fakeSupabase.contactRow = {
      id: "contact-1",
      name: "Иванов И.И.",
      phone: "+7-999-000-00-00",
      email: "contact@example.com",
    };
    fakeSupabase.creatorRow = {
      user_id: "user-1",
      full_name: "Менеджер",
    };
    fakeSupabase.calcVarsRow = {
      variables: {
        offer_incoterms: "DDP",
        offer_sale_type: "внутренний",
      },
    };
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
                base_price_vat: 1200,
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

    // It must not perform a direct quote_items select (the legacy
    // `.from("quote_items").select("*")`).
    const legacyQuoteItemsCall = fakeSupabase.fromCalls.find(
      (c) => c.table === "quote_items"
    );
    expect(legacyQuoteItemsCall).toBeUndefined();
  });

  it("passes the composed items to KPDocument with KPComposedItem shape", async () => {
    await callRoute();

    expect(capturedKPDocumentProps).toBeDefined();
    const items = capturedKPDocumentProps!.items as Array<{
      id: string;
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
      base_price_vat: 1200,
    });
    // unit is not on invoice_items; the PDF renderer applies its own
    // fallback ("шт"). The route returns null here.
    expect(items[0].unit).toBeNull();
    // id is required by KPComposedItem (used as React key).
    expect(typeof items[0].id).toBe("string");
    expect(items[0].id.length).toBeGreaterThan(0);
  });

  it("handles split coverage (1 quote_item → N invoice_items) by emitting multiple rows", async () => {
    fakeSupabase.composedItemsRow = {
      id: "q-1",
      quote_items: [
        {
          id: "qi-split",
          position: 1,
          composition_selected_invoice_id: "inv-A",
          brand: "SKF",
          coverage: [
            {
              invoice_items: {
                invoice_id: "inv-A",
                supplier_sku: "BOLT-1",
                product_name: "Болт",
                brand: "SKF",
                base_price_vat: 100,
                quantity: 10,
              },
            },
            {
              invoice_items: {
                invoice_id: "inv-A",
                supplier_sku: "WASHER-1",
                product_name: "Шайба",
                brand: "SKF",
                base_price_vat: 50,
                quantity: 20,
              },
            },
          ],
        },
      ],
    };

    await callRoute();

    const items = capturedKPDocumentProps!.items as Array<{
      product_name: string;
      quantity: number | null;
    }>;

    expect(items).toHaveLength(2);
    expect(items.map((i) => i.product_name)).toEqual(["Болт", "Шайба"]);
  });

  it("ignores coverage rows from other invoices (not the selected invoice)", async () => {
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
                product_name: "Подшипник (A)",
                brand: "SKF",
                base_price_vat: 1000,
                quantity: 5,
              },
            },
            {
              invoice_items: {
                // Different invoice — must be skipped
                invoice_id: "inv-B",
                supplier_sku: "SKF-205",
                product_name: "Подшипник (B)",
                brand: "SKF",
                base_price_vat: 999,
                quantity: 5,
              },
            },
          ],
        },
      ],
    };

    await callRoute();

    const items = capturedKPDocumentProps!.items as Array<{
      product_name: string;
    }>;

    expect(items).toHaveLength(1);
    expect(items[0].product_name).toBe("Подшипник (A)");
  });
});
