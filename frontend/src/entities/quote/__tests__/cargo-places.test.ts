import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tests for the cargo-place CRUD mutations added to support the
 * deferred-fill КП editor in InvoiceCard. The mutations live alongside
 * existing invoice/coverage mutations in entities/quote/mutations.ts and
 * are mocked here through a per-table fake that records inserts/updates/
 * deletes for assertion.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

type QueryResult<T> = { data: T; error: null } | { data: null; error: Error };

interface FakeSupabase {
  cargoMaxPosition: number | null;
  selectMaxError: Error | null;
  insertedRow: Record<string, unknown> | null;
  insertError: Error | null;
  insertReturn: { id: string; position: number } | null;
  updatedRow: Record<string, unknown> | null;
  updatedId: string | null;
  updateError: Error | null;
  deletedId: string | null;
  deleteError: Error | null;
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    cargoMaxPosition: null,
    selectMaxError: null,
    insertedRow: null,
    insertError: null,
    insertReturn: null,
    updatedRow: null,
    updatedId: null,
    updateError: null,
    deletedId: null,
    deleteError: null,
    from(table: string) {
      if (table !== "invoice_cargo_places") {
        throw new Error(`Unexpected table: ${table}`);
      }
      return {
        // .select("position").eq("invoice_id", ...).order(...).limit(1)
        select: (_cols: string) => ({
          eq: () => ({
            order: () => ({
              limit: async (): Promise<
                QueryResult<{ position: number }[]>
              > => {
                if (state.selectMaxError) {
                  return { data: null, error: state.selectMaxError };
                }
                return {
                  data:
                    state.cargoMaxPosition != null
                      ? [{ position: state.cargoMaxPosition }]
                      : [],
                  error: null,
                };
              },
            }),
          }),
        }),
        insert: (row: Record<string, unknown>) => {
          state.insertedRow = row;
          return {
            select: () => ({
              single: async (): Promise<
                QueryResult<{ id: string; position: number }>
              > => {
                if (state.insertError) {
                  return { data: null, error: state.insertError };
                }
                return {
                  data: state.insertReturn ?? {
                    id: "cp-1",
                    position: (row.position as number) ?? 1,
                  },
                  error: null,
                };
              },
            }),
          };
        },
        update: (updates: Record<string, unknown>) => {
          state.updatedRow = updates;
          return {
            eq: async (_col: string, value: string) => {
              state.updatedId = value;
              if (state.updateError) {
                return { data: null, error: state.updateError };
              }
              return { data: null, error: null };
            },
          };
        },
        delete: () => ({
          eq: async (_col: string, value: string) => {
            state.deletedId = value;
            if (state.deleteError) {
              return { data: null, error: state.deleteError };
            }
            return { data: null, error: null };
          },
        }),
      };
    },
  };
  return state;
}

describe("addCargoPlace", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("inserts at position 1 when the invoice has no cargo places yet", async () => {
    const { addCargoPlace } = await import("../mutations");
    const result = await addCargoPlace("inv-1", {
      weight_kg: 5,
      length_mm: 100,
      width_mm: 200,
      height_mm: 300,
    });
    expect(fakeSupabase.insertedRow).toMatchObject({
      invoice_id: "inv-1",
      position: 1,
      weight_kg: 5,
      length_mm: 100,
      width_mm: 200,
      height_mm: 300,
    });
    expect(result.position).toBe(1);
  });

  it("inserts at MAX(position) + 1 when prior places exist", async () => {
    fakeSupabase.cargoMaxPosition = 4;
    const { addCargoPlace } = await import("../mutations");
    await addCargoPlace("inv-1", {
      weight_kg: 1,
      length_mm: 1,
      width_mm: 1,
      height_mm: 1,
    });
    expect(fakeSupabase.insertedRow?.position).toBe(5);
  });

  it("propagates insert errors", async () => {
    fakeSupabase.insertError = new Error("RLS denied");
    const { addCargoPlace } = await import("../mutations");
    await expect(
      addCargoPlace("inv-1", {
        weight_kg: 1,
        length_mm: 1,
        width_mm: 1,
        height_mm: 1,
      })
    ).rejects.toThrow("RLS denied");
  });

  it("propagates max-position lookup errors", async () => {
    fakeSupabase.selectMaxError = new Error("query failed");
    const { addCargoPlace } = await import("../mutations");
    await expect(
      addCargoPlace("inv-1", {
        weight_kg: 1,
        length_mm: 1,
        width_mm: 1,
        height_mm: 1,
      })
    ).rejects.toThrow("query failed");
  });
});

describe("updateCargoPlace", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("updates only the supplied fields", async () => {
    const { updateCargoPlace } = await import("../mutations");
    await updateCargoPlace("cp-1", { weight_kg: 7.5 });
    expect(fakeSupabase.updatedRow).toEqual({ weight_kg: 7.5 });
    expect(fakeSupabase.updatedId).toBe("cp-1");
  });

  it("supports multi-field partial updates", async () => {
    const { updateCargoPlace } = await import("../mutations");
    await updateCargoPlace("cp-1", { length_mm: 100, width_mm: 50 });
    expect(fakeSupabase.updatedRow).toEqual({ length_mm: 100, width_mm: 50 });
  });

  it("propagates update errors", async () => {
    fakeSupabase.updateError = new Error("constraint violation");
    const { updateCargoPlace } = await import("../mutations");
    await expect(
      updateCargoPlace("cp-1", { weight_kg: 0 })
    ).rejects.toThrow("constraint violation");
  });
});

describe("deleteCargoPlace", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("deletes by id", async () => {
    const { deleteCargoPlace } = await import("../mutations");
    await deleteCargoPlace("cp-2");
    expect(fakeSupabase.deletedId).toBe("cp-2");
  });

  it("propagates delete errors", async () => {
    fakeSupabase.deleteError = new Error("foreign key");
    const { deleteCargoPlace } = await import("../mutations");
    await expect(deleteCargoPlace("cp-1")).rejects.toThrow("foreign key");
  });
});
