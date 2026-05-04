import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

/**
 * Tests for the per-invoice procurement completion mutations.
 *
 * As of fix/per-invoice-procurement-stage-transition, `completeInvoiceProcurement`
 * is a thin wrapper over the Python API endpoint
 * `POST /api/invoices/{id}/complete-procurement`. The endpoint orchestrates
 * the full transition (invoice flags + logistics/customs assigners + atomic
 * workflow advance) — the frontend just needs to authenticate and forward.
 *
 * `reopenInvoiceProcurement` remains a direct Supabase UPDATE used only by
 * role-gated unlock flows.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface FakeSupabase {
  authToken: string | null;
  authError: Error | null;
  updatedRow: Record<string, unknown> | null;
  updatedId: string | null;
  updateError: Error | null;
  auth: {
    getSession(): Promise<
      | { data: { session: { access_token: string } | null }; error: null }
      | { data: { session: null }; error: Error }
    >;
  };
  from(table: string): unknown;
}

let fakeSupabase: FakeSupabase;
const originalFetch = globalThis.fetch;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    authToken: "tok-1",
    authError: null,
    updatedRow: null,
    updatedId: null,
    updateError: null,
    auth: {
      getSession: async () => {
        if (state.authError) {
          return { data: { session: null }, error: state.authError };
        }
        return state.authToken
          ? {
              data: { session: { access_token: state.authToken } },
              error: null,
            }
          : { data: { session: null }, error: null };
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

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("POSTs to /api/invoices/{id}/complete-procurement with auth header", async () => {
    let calledUrl = "";
    let calledHeaders: Record<string, string> = {};
    let calledMethod = "";
    globalThis.fetch = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        calledUrl = String(url);
        calledHeaders = (init?.headers ?? {}) as Record<string, string>;
        calledMethod = init?.method ?? "";
        return new Response(
          JSON.stringify({ success: true, data: { workflow_advanced: true } }),
          { status: 200 }
        );
      }
    ) as unknown as typeof fetch;

    const { completeInvoiceProcurement } = await import("../mutations");
    await completeInvoiceProcurement("inv-1");

    expect(calledUrl).toBe("/api/invoices/inv-1/complete-procurement");
    expect(calledMethod).toBe("POST");
    expect(calledHeaders.Authorization).toBe("Bearer tok-1");
    expect(calledHeaders["Content-Type"]).toBe("application/json");
  });

  it("omits Authorization header when no session", async () => {
    fakeSupabase.authToken = null;
    let calledHeaders: Record<string, string> = {};
    globalThis.fetch = vi.fn(
      async (_url: string | URL | Request, init?: RequestInit) => {
        calledHeaders = (init?.headers ?? {}) as Record<string, string>;
        return new Response(
          JSON.stringify({ success: true, data: {} }),
          { status: 200 }
        );
      }
    ) as unknown as typeof fetch;

    const { completeInvoiceProcurement } = await import("../mutations");
    await completeInvoiceProcurement("inv-2");

    expect(calledHeaders.Authorization).toBeUndefined();
  });

  it("throws on non-2xx response with backend error message", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response(
        JSON.stringify({
          success: false,
          error: { code: "ALREADY_COMPLETED", message: "Already completed" },
        }),
        { status: 409 }
      )
    ) as unknown as typeof fetch;

    const { completeInvoiceProcurement } = await import("../mutations");
    await expect(completeInvoiceProcurement("inv-1")).rejects.toThrow(
      "Already completed"
    );
  });

  it("throws fallback message when error body is not JSON", async () => {
    globalThis.fetch = vi.fn(async () =>
      new Response("oops", { status: 500 })
    ) as unknown as typeof fetch;

    const { completeInvoiceProcurement } = await import("../mutations");
    await expect(completeInvoiceProcurement("inv-1")).rejects.toThrow(
      /HTTP 500/
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
