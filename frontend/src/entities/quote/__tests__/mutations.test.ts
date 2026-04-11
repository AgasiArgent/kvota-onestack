import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Regression tests for createInvoice pickup_country derivation.
 *
 * Bug: FB-260410-110450-4b85, FB-260410-123751-4b94
 * Root cause: createInvoice was inserting invoices with pickup_country = NULL,
 * which caused assign_logistics_to_invoices to silently skip them, so logistics
 * users never saw the invoices in their /quotes list.
 *
 * Fix: derive pickup_country from suppliers.country at invoice creation time.
 */

// The createClient module is mocked; the test installs its own fake client
// before each test so we can assert on the .insert() payload.
vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

type QueryResult<T> = { data: T; error: null } | { data: null; error: Error };

interface FakeSupabase {
  suppliersCountry: string | null | undefined;
  suppliersError: Error | null;
  insertedRows: Record<string, unknown>[];
  insertError: Error | null;
  supplierQueryCount: number;
  /** Phase 5b: when set, the sibling-invoice check returns this row. */
  existingSameSupplierInvoice: {
    id: string;
    pickup_country: string | null;
    pickup_city: string | null;
  } | null;
  /** Phase 5b: count of sibling-invoice queries (for assert). */
  siblingQueryCount: number;
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    suppliersCountry: undefined,
    suppliersError: null,
    insertedRows: [],
    insertError: null,
    supplierQueryCount: 0,
    existingSameSupplierInvoice: null,
    siblingQueryCount: 0,
    from(table: string) {
      if (table === "suppliers") {
        state.supplierQueryCount += 1;
        return {
          select: () => ({
            eq: () => ({
              maybeSingle: async (): Promise<QueryResult<{ country: string | null } | null>> => {
                if (state.suppliersError) {
                  return { data: null, error: state.suppliersError };
                }
                if (state.suppliersCountry === undefined) {
                  // Supplier not found
                  return { data: null, error: null };
                }
                return { data: { country: state.suppliersCountry }, error: null };
              },
            }),
          }),
        };
      }
      if (table === "invoices") {
        return {
          select: (_cols: string, opts?: { count?: string; head?: boolean }) => {
            if (opts?.head) {
              // Count query for invoice numbering
              return {
                eq: async () => ({ count: 0, error: null }),
              };
            }
            // Non-head select — used by two flows:
            //   A) Phase 5b sibling-invoice check:
            //      .select('id, pickup_country, pickup_city')
            //      .eq('quote_id', ...).eq('supplier_id', ...).limit(1).maybeSingle()
            //   B) Insert-then-select:
            //      .insert(...).select('id, invoice_number').single()
            // Differentiate by .eq() chain vs .single() chain.
            return {
              eq: () => ({
                eq: () => ({
                  limit: () => ({
                    maybeSingle: async (): Promise<
                      QueryResult<
                        | {
                            id: string;
                            pickup_country: string | null;
                            pickup_city: string | null;
                          }
                        | null
                      >
                    > => {
                      state.siblingQueryCount += 1;
                      return {
                        data: state.existingSameSupplierInvoice,
                        error: null,
                      };
                    },
                  }),
                }),
              }),
              single: async (): Promise<
                QueryResult<{ id: string; invoice_number: string }>
              > => {
                if (state.insertError) {
                  return { data: null, error: state.insertError };
                }
                return {
                  data: {
                    id: "invoice-123",
                    invoice_number: "INV-01-Q-202604-0001",
                  },
                  error: null,
                };
              },
            };
          },
          insert: (row: Record<string, unknown>) => {
            state.insertedRows.push(row);
            return {
              select: () => ({
                single: async (): Promise<
                  QueryResult<{ id: string; invoice_number: string }>
                > => {
                  if (state.insertError) {
                    return { data: null, error: state.insertError };
                  }
                  return {
                    data: {
                      id: "invoice-123",
                      invoice_number: "INV-01-Q-202604-0001",
                    },
                    error: null,
                  };
                },
              }),
            };
          },
        };
      }
      if (table === "invoice_cargo_places") {
        return {
          insert: async () => ({ error: null }),
        };
      }
      throw new Error(`Unexpected table: ${table}`);
    },
  };
  return state;
}

describe("createInvoice — pickup_country derivation", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("derives pickup_country from supplier.country when supplier_id is provided", async () => {
    fakeSupabase.suppliersCountry = "Китай";
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-1",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.supplierQueryCount).toBe(1);
    expect(fakeSupabase.insertedRows).toHaveLength(1);
    expect(fakeSupabase.insertedRows[0].pickup_country).toBe("Китай");
    expect(fakeSupabase.insertedRows[0].supplier_id).toBe("supplier-1");
  });

  it("sets pickup_country to null when supplier exists but has no country", async () => {
    fakeSupabase.suppliersCountry = null;
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-1",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.supplierQueryCount).toBe(1);
    expect(fakeSupabase.insertedRows).toHaveLength(1);
    expect(fakeSupabase.insertedRows[0].pickup_country).toBeNull();
  });

  it("sets pickup_country to null and skips supplier query when supplier_id is omitted", async () => {
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.supplierQueryCount).toBe(0);
    expect(fakeSupabase.insertedRows).toHaveLength(1);
    expect(fakeSupabase.insertedRows[0].pickup_country).toBeNull();
    expect(fakeSupabase.insertedRows[0].supplier_id).toBeNull();
  });

  it("propagates the error when the supplier lookup fails", async () => {
    fakeSupabase.suppliersError = new Error("db down");
    const { createInvoice } = await import("../mutations");

    await expect(
      createInvoice({
        quote_id: "quote-1",
        idn_quote: "Q-202604-0001",
        supplier_id: "supplier-1",
        buyer_company_id: "buyer-1",
        currency: "USD",
        boxes: [
          { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
        ],
      })
    ).rejects.toThrow("db down");

    expect(fakeSupabase.insertedRows).toHaveLength(0);
  });

  // -------------------------------------------------------------------------
  // Phase 3 Section 4: pickup_country_code and supplier_incoterms dual-write.
  // Schema migration 266 added pickup_country_code (CHAR(2)) and
  // supplier_incoterms (TEXT). The mutation now populates both alongside the
  // legacy pickup_country text field, and an explicit user pick from the
  // modal always wins over the supplier-derived default.
  // -------------------------------------------------------------------------

  it("prefers explicit pickup_country_override and pickup_country_code over supplier.country", async () => {
    // Supplier says Китай, but user explicitly picks Турция in the modal.
    fakeSupabase.suppliersCountry = "Китай";
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-1",
      buyer_company_id: "buyer-1",
      currency: "USD",
      pickup_country_override: "Турция",
      pickup_country_code: "TR",
      supplier_incoterms: "FOB",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.insertedRows).toHaveLength(1);
    const row = fakeSupabase.insertedRows[0];
    expect(row.pickup_country).toBe("Турция");
    expect(row.pickup_country_code).toBe("TR");
    expect(row.supplier_incoterms).toBe("FOB");
  });

  it("derives both pickup_country and pickup_country_code from supplier.country via findCountryByName", async () => {
    // No explicit override — supplier country must populate BOTH fields.
    // "Германия" is a Russian ICU name, so the code resolves to "DE".
    fakeSupabase.suppliersCountry = "Германия";
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-1",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.supplierQueryCount).toBe(1);
    expect(fakeSupabase.insertedRows).toHaveLength(1);
    const row = fakeSupabase.insertedRows[0];
    expect(row.pickup_country).toBe("Германия");
    expect(row.pickup_country_code).toBe("DE");
    expect(row.supplier_incoterms).toBeNull();
  });

  it("preserves supplier country text but leaves pickup_country_code null when ICU cannot resolve the name", async () => {
    // Legacy free-text country that ICU doesn't know. Graceful degradation:
    // text field keeps the original value, code field stays null.
    fakeSupabase.suppliersCountry = "Выдуманная страна";
    const { createInvoice } = await import("../mutations");

    await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-1",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(fakeSupabase.insertedRows).toHaveLength(1);
    const row = fakeSupabase.insertedRows[0];
    expect(row.pickup_country).toBe("Выдуманная страна");
    expect(row.pickup_country_code).toBeNull();
  });
});

describe("createInvoice — Phase 5b bypass logic", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("returns bypass_reason='new_supplier' and pre-fills pickup_country when supplier is new to this quote", async () => {
    fakeSupabase.suppliersCountry = "Italy";
    fakeSupabase.existingSameSupplierInvoice = null; // no sibling
    const { createInvoice } = await import("../mutations");

    const result = await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-italcarrelli",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(result.bypass_reason).toBe("new_supplier");
    expect(fakeSupabase.siblingQueryCount).toBe(1);
    expect(fakeSupabase.supplierQueryCount).toBe(1);
    expect(fakeSupabase.insertedRows[0].pickup_country).toBe("Italy");
  });

  it("returns bypass_reason='same_supplier' and inherits pickup_country from sibling without touching suppliers table", async () => {
    fakeSupabase.existingSameSupplierInvoice = {
      id: "first-invoice",
      pickup_country: "Turkey",
      pickup_city: "Istanbul",
    };
    const { createInvoice } = await import("../mutations");

    const result = await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-italcarrelli",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(result.bypass_reason).toBe("same_supplier");
    expect(fakeSupabase.siblingQueryCount).toBe(1);
    expect(
      fakeSupabase.supplierQueryCount,
      "suppliers table should NOT be queried on same_supplier bypass"
    ).toBe(0);
    expect(fakeSupabase.insertedRows[0].pickup_country).toBe("Turkey");
    expect(fakeSupabase.insertedRows[0].pickup_city).toBe("Istanbul");
  });

  it("respects caller-provided pickup_country_override even on same_supplier bypass (user override)", async () => {
    fakeSupabase.existingSameSupplierInvoice = {
      id: "first-invoice",
      pickup_country: "Turkey",
      pickup_city: "Istanbul",
    };
    const { createInvoice } = await import("../mutations");

    const result = await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      supplier_id: "supplier-italcarrelli",
      pickup_country_override: "Греция", // Phase 3 modal explicit override
      pickup_city: "Athens",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(result.bypass_reason).toBe("same_supplier");
    expect(fakeSupabase.insertedRows[0].pickup_country).toBe("Греция");
    expect(fakeSupabase.insertedRows[0].pickup_city).toBe("Athens");
  });

  it("returns bypass_reason=null and skips sibling check when supplier_id is omitted", async () => {
    const { createInvoice } = await import("../mutations");

    const result = await createInvoice({
      quote_id: "quote-1",
      idn_quote: "Q-202604-0001",
      buyer_company_id: "buyer-1",
      currency: "USD",
      boxes: [
        { weight_kg: 10, length_mm: 100, width_mm: 100, height_mm: 100 },
      ],
    });

    expect(result.bypass_reason).toBeNull();
    expect(fakeSupabase.siblingQueryCount).toBe(0);
    expect(fakeSupabase.supplierQueryCount).toBe(0);
  });
});
