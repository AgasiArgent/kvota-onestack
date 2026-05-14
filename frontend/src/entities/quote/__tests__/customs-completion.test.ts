import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

import { extractErrorMessage } from "@/shared/lib/errors";

/**
 * Testing 2 row 11 — «Таможня завершена» silent failure on HTTP 422.
 *
 * Pre-fix: production POST to `/api/quotes/{id}/workflow/transition`
 * returned `{success: false, error: "Customs already completed"}` with
 * status 422. The mutation correctly threw, but the customs-step handler
 * used `err instanceof Error ? err.message : "fallback"` which is fine
 * for the throw path — yet there was no visible toast under some race
 * conditions when the error envelope nested the message. This file locks
 * in the throw contract so the upstream toast layer always receives a
 * usable message via `extractErrorMessage`.
 *
 * Covers two angles:
 *   1. `completeCustoms` throws an `Error` whose `.message` carries the
 *      raw server-side reason ("Customs already completed", "Cannot
 *      complete customs: N items missing HS code", etc.).
 *   2. `extractErrorMessage` — used by the new
 *      customs-step.handleCompleteCustoms catch — returns the same
 *      string regardless of whether the caller passes the thrown Error
 *      or a raw api-first envelope.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => fakeSupabase,
}));

interface FakeSupabase {
  authToken: string | null;
  auth: {
    getSession(): Promise<{
      data: { session: { access_token: string } | null };
      error: null;
    }>;
  };
}

let fakeSupabase: FakeSupabase;
const originalFetch = globalThis.fetch;

function makeFakeSupabase(): FakeSupabase {
  const state: FakeSupabase = {
    authToken: "tok-1",
    auth: {
      getSession: async () => ({
        data: state.authToken
          ? { session: { access_token: state.authToken } }
          : { session: null },
        error: null,
      }),
    },
  };
  return state;
}

describe("completeCustoms — workflow transition contract", () => {
  beforeEach(() => {
    fakeSupabase = makeFakeSupabase();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("POSTs to /api/quotes/{id}/workflow/transition with complete_customs action", async () => {
    let calledUrl = "";
    let calledBody: unknown = null;
    globalThis.fetch = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        calledUrl = String(url);
        calledBody = init?.body ? JSON.parse(String(init.body)) : null;
        return new Response(
          JSON.stringify({
            success: true,
            from_status: "pending_customs",
            to_status: "calculated",
          }),
          { status: 200 },
        );
      },
    ) as unknown as typeof fetch;

    const { completeCustoms } = await import("../mutations");
    await completeCustoms("q-1");

    expect(calledUrl).toBe("/api/quotes/q-1/workflow/transition");
    expect(calledBody).toEqual({ action: "complete_customs" });
  });

  it("throws Error with server message on 422 «Customs already completed»", async () => {
    // Mirrors the real prod response observed on quote b4e56dac.
    globalThis.fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            success: false,
            error: "Customs already completed",
          }),
          { status: 422 },
        ),
    ) as unknown as typeof fetch;

    const { completeCustoms } = await import("../mutations");
    await expect(completeCustoms("q-1")).rejects.toThrow(
      "Customs already completed",
    );
  });

  it("throws Error with server message on 422 «N items missing HS code»", async () => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            success: false,
            error: "Cannot complete customs: 3 items missing HS code (ТН ВЭД)",
          }),
          { status: 422 },
        ),
    ) as unknown as typeof fetch;

    const { completeCustoms } = await import("../mutations");
    await expect(completeCustoms("q-1")).rejects.toThrow(
      "3 items missing HS code",
    );
  });
});

describe("customs-step error toast — extractErrorMessage integration", () => {
  // The handler is `extractErrorMessage(err) ?? "Не удалось завершить таможню"`.
  // These assertions document the shapes the catch must handle.

  it("returns the server message from a thrown Error", () => {
    const err = new Error("Customs already completed");
    expect(extractErrorMessage(err)).toBe("Customs already completed");
  });

  it("returns the server message from a raw api-first envelope", () => {
    // If the throw layer were ever bypassed and the raw fetch response body
    // hit the catch, the helper must still surface the message.
    const envelope = {
      success: false,
      error: { code: "ALREADY_COMPLETED", message: "Customs already completed" },
    };
    expect(extractErrorMessage(envelope)).toBe("Customs already completed");
  });

  it("falls back to null for unknown shapes (component supplies Russian fallback)", () => {
    expect(extractErrorMessage({ random: "noise" })).toBeNull();
    expect(extractErrorMessage(null)).toBeNull();
    expect(extractErrorMessage(undefined)).toBeNull();
  });
});
