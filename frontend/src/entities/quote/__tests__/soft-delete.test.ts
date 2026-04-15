import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * Unit tests for softDeleteQuote mutation (Task 4).
 *
 * Covers:
 *   - happy path: POST to /api/quotes/{id}/soft-delete + returns data envelope
 *   - auth header forwarding (Supabase JWT)
 *   - 403 FORBIDDEN surfaces server error.message
 *   - 500 INTERNAL_ERROR surfaces server error.message
 *   - malformed JSON falls back to generic error
 *
 * These tests exercise the contract with the Python soft-delete endpoint
 * (owned by PR #5). They do NOT require the endpoint to be live — fetch
 * is mocked.
 */

const getSessionMock = vi.fn();

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: getSessionMock,
    },
  }),
}));

const originalFetch = globalThis.fetch;

describe("softDeleteQuote", () => {
  beforeEach(() => {
    getSessionMock.mockReset();
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "test-jwt" } },
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("POSTs to /api/quotes/{id}/soft-delete with Bearer token and returns data envelope", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        success: true,
        data: { quote_affected: 1, spec_affected: 1, deal_affected: 0 },
      }),
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");

    const result = await softDeleteQuote("quote-abc");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const url = call[0];
    const init = call[1];
    expect(url).toBe("/api/quotes/quote-abc/soft-delete");
    expect(init.method).toBe("POST");
    expect(
      (init.headers as Record<string, string>).Authorization
    ).toBe("Bearer test-jwt");

    expect(result).toEqual({
      quote_affected: 1,
      spec_affected: 1,
      deal_affected: 0,
    });
  });

  it("omits Authorization header when session has no access_token", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        success: true,
        data: { quote_affected: 1, spec_affected: 0, deal_affected: 0 },
      }),
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");
    await softDeleteQuote("quote-xyz");

    const call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const init = call[1];
    const headers = (init.headers ?? {}) as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("throws with server-provided message on 403 FORBIDDEN", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 403,
      json: async () => ({
        success: false,
        error: { code: "FORBIDDEN", message: "admin only" },
      }),
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");

    await expect(softDeleteQuote("quote-abc")).rejects.toThrow("admin only");
  });

  it("throws with server-provided message on 500 INTERNAL_ERROR", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => ({
        success: false,
        error: { code: "INTERNAL_ERROR", message: "db unreachable" },
      }),
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");

    await expect(softDeleteQuote("quote-abc")).rejects.toThrow(
      "db unreachable"
    );
  });

  it("falls back to generic message when response JSON is malformed", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("unexpected token");
      },
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");

    await expect(softDeleteQuote("quote-abc")).rejects.toThrow(
      "Soft-delete failed"
    );
  });

  it("falls back to generic message when envelope has no error.message", async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 500,
      json: async () => ({ success: false }),
    }));
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { softDeleteQuote } = await import("../mutations");

    await expect(softDeleteQuote("quote-abc")).rejects.toThrow(
      "Soft-delete failed"
    );
  });
});
