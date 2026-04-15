import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

/**
 * Unit tests for restoreQuote mutation (entities/quote/mutations.ts).
 *
 * The function POSTs to /api/quotes/{id}/restore with a bearer token from the
 * Supabase session, then normalizes the API envelope to either a plain
 * data object or a thrown Error.
 */

const getSessionMock = vi.fn();

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: getSessionMock,
    },
  }),
}));

import { restoreQuote } from "../mutations";

const originalFetch = global.fetch;

function mockFetchResponse(init: {
  status?: number;
  jsonPayload?: unknown;
  jsonThrows?: boolean;
}) {
  const status = init.status ?? 200;
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: init.jsonThrows
      ? vi.fn().mockRejectedValue(new SyntaxError("Unexpected token"))
      : vi.fn().mockResolvedValue(init.jsonPayload ?? {}),
  });
}

describe("restoreQuote", () => {
  beforeEach(() => {
    getSessionMock.mockReset();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("POSTs to /api/quotes/{id}/restore with Bearer token from session", async () => {
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "token-abc" } },
    });
    const fetchMock = mockFetchResponse({
      jsonPayload: {
        success: true,
        data: { quote_affected: 1, spec_affected: 1, deal_affected: 0 },
      },
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await restoreQuote("quote-123");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/quotes/quote-123/restore");
    expect(opts.method).toBe("POST");
    expect((opts.headers as Record<string, string>).Authorization).toBe(
      "Bearer token-abc"
    );
    expect(result).toEqual({
      quote_affected: 1,
      spec_affected: 1,
      deal_affected: 0,
    });
  });

  it("omits Authorization header when no session is present", async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } });
    const fetchMock = mockFetchResponse({
      jsonPayload: {
        success: true,
        data: { quote_affected: 1, spec_affected: 0, deal_affected: 0 },
      },
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await restoreQuote("quote-456");

    const [, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(opts.headers).not.toHaveProperty("Authorization");
  });

  it("surfaces server error.message on 403", async () => {
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "token-abc" } },
    });
    global.fetch = mockFetchResponse({
      status: 403,
      jsonPayload: {
        success: false,
        error: { message: "Только администратор может восстанавливать КП" },
      },
    }) as unknown as typeof fetch;

    await expect(restoreQuote("quote-789")).rejects.toThrow(
      "Только администратор может восстанавливать КП"
    );
  });

  it("surfaces server error.message on 500", async () => {
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "token-abc" } },
    });
    global.fetch = mockFetchResponse({
      status: 500,
      jsonPayload: {
        success: false,
        error: { message: "Database is unreachable" },
      },
    }) as unknown as typeof fetch;

    await expect(restoreQuote("quote-err")).rejects.toThrow(
      "Database is unreachable"
    );
  });

  it("throws generic 'Restore failed' when response JSON is malformed", async () => {
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "token-abc" } },
    });
    global.fetch = mockFetchResponse({
      status: 500,
      jsonThrows: true,
    }) as unknown as typeof fetch;

    await expect(restoreQuote("quote-bad")).rejects.toThrow("Restore failed");
  });

  it("falls back to generic 'Restore failed' when error.message is missing", async () => {
    getSessionMock.mockResolvedValue({
      data: { session: { access_token: "token-abc" } },
    });
    global.fetch = mockFetchResponse({
      status: 500,
      jsonPayload: { success: false, error: {} },
    }) as unknown as typeof fetch;

    await expect(restoreQuote("quote-nomsg")).rejects.toThrow("Restore failed");
  });
});
