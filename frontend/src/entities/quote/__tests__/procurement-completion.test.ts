import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tests for the per-invoice procurement completion mutations. Replaces the
 * legacy quote-level flag — each КП completes / re-opens independently.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface FakeSupabase {
  authUserId: string | null;
  updatedRow: Record<string, unknown> | null;
  updatedId: string | null;
  updateError: Error | null;
  authError: Error | null;
  auth: {
    getUser(): Promise<
      | { data: { user: { id: string } | null }; error: null }
      | { data: { user: null }; error: Error }
    >;
  };
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    authUserId: "user-1",
    updatedRow: null,
    updatedId: null,
    updateError: null,
    authError: null,
    auth: {
      getUser: async () => {
        if (state.authError) {
          return { data: { user: null }, error: state.authError };
        }
        return state.authUserId
          ? { data: { user: { id: state.authUserId } }, error: null }
          : { data: { user: null }, error: null };
      },
    },
    from(table: string) {
      if (table !== "invoices") {
        throw new Error(`Unexpected table: ${table}`);
      }
      return {
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
      };
    },
  };
  return state;
}

describe("completeInvoiceProcurement", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("stamps procurement_completed_at and procurement_completed_by", async () => {
    const { completeInvoiceProcurement } = await import("../mutations");
    await completeInvoiceProcurement("inv-1");
    expect(fakeSupabase.updatedId).toBe("inv-1");
    expect(fakeSupabase.updatedRow).toMatchObject({
      procurement_completed_by: "user-1",
    });
    expect(typeof fakeSupabase.updatedRow?.procurement_completed_at).toBe(
      "string"
    );
    // ISO 8601-ish — at minimum starts with 4 digits + dash
    expect(
      String(fakeSupabase.updatedRow?.procurement_completed_at)
    ).toMatch(/^\d{4}-/);
  });

  it("falls back to null user when auth.getUser returns no session", async () => {
    fakeSupabase.authUserId = null;
    const { completeInvoiceProcurement } = await import("../mutations");
    await completeInvoiceProcurement("inv-2");
    expect(fakeSupabase.updatedRow?.procurement_completed_by).toBeNull();
  });

  it("propagates update errors", async () => {
    fakeSupabase.updateError = new Error("RLS denied");
    const { completeInvoiceProcurement } = await import("../mutations");
    await expect(completeInvoiceProcurement("inv-1")).rejects.toThrow(
      "RLS denied"
    );
  });
});

describe("reopenInvoiceProcurement", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  it("clears both procurement_completed_* columns", async () => {
    const { reopenInvoiceProcurement } = await import("../mutations");
    await reopenInvoiceProcurement("inv-3");
    expect(fakeSupabase.updatedId).toBe("inv-3");
    expect(fakeSupabase.updatedRow).toEqual({
      procurement_completed_at: null,
      procurement_completed_by: null,
    });
  });

  it("propagates update errors", async () => {
    fakeSupabase.updateError = new Error("constraint");
    const { reopenInvoiceProcurement } = await import("../mutations");
    await expect(reopenInvoiceProcurement("inv-3")).rejects.toThrow(
      "constraint"
    );
  });
});
