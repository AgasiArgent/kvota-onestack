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
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(overrides: Partial<FakeSupabase> = {}): FakeSupabase {
  const state: FakeSupabase = {
    suppliersCountry: undefined,
    suppliersError: null,
    insertedRows: [],
    insertError: null,
    supplierQueryCount: 0,
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
            // .insert(...).select(...).single()
            return {
              single: async (): Promise<QueryResult<{ id: string; invoice_number: string }>> => {
                if (state.insertError) {
                  return { data: null, error: state.insertError };
                }
                return {
                  data: { id: "invoice-123", invoice_number: "INV-01-Q-202604-0001" },
                  error: null,
                };
              },
            };
          },
          insert: (row: Record<string, unknown>) => {
            state.insertedRows.push(row);
            return {
              select: () => ({
                single: async (): Promise<QueryResult<{ id: string; invoice_number: string }>> => {
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
    ...overrides,
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
});
