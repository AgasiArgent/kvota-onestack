/**
 * Runtime tests for the journey entity's API layer (envelope unwrap + URL
 * shape). We exercise the bare `journeyFetch` helper and `journeyNodePath`
 * directly so we do not need a TanStack Query test harness here — the hooks
 * are thin wrappers over the same helper.
 *
 * The test mocks `globalThis.fetch`, feeds it the `{success, data}` envelope
 * the Python API emits, and asserts:
 *   - success envelope → returns `data` payload unwrapped
 *   - error envelope → throws an Error with `.code` + `.status`
 *   - journeyNodePath builds the correct shape for app:/ and ghost:/ IDs
 *     and preserves slashes inside the tail (backend uses `{node_id:path}`)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { JourneyNodeAggregated } from "../types";
import { journeyFetch, journeyNodePath } from "../api";

type FetchLike = typeof globalThis.fetch;

function mockJsonResponse(body: unknown, init: { status?: number } = {}): Response {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "content-type": "application/json" },
  });
}

describe("journeyNodePath", () => {
  it("returns the path for an app:/ node with slashes intact", () => {
    // Backend route is `/api/journey/node/{node_id:path}` so slashes are
    // part of the path segment — do not percent-encode them.
    const p = journeyNodePath("app:/quotes/[id]");
    expect(p).toBe("app:/quotes/[id]");
  });

  it("returns the path for a ghost: node", () => {
    expect(journeyNodePath("ghost:new-feature")).toBe("ghost:new-feature");
  });

  it("rejects malformed node ids", () => {
    // @ts-expect-error — template-literal union disallows bare strings,
    // but we pass a cast to verify the runtime guard.
    expect(() => journeyNodePath("bogus" as const)).toThrow();
  });
});

describe("journeyFetch envelope unwrap", () => {
  let originalFetch: FetchLike;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("returns `data` on success envelope", async () => {
    const payload: JourneyNodeAggregated[] = [];
    globalThis.fetch = vi.fn(async () =>
      mockJsonResponse({ success: true, data: payload })
    ) as unknown as FetchLike;

    const result = await journeyFetch<JourneyNodeAggregated[]>("/api/journey/nodes");
    // JSON round-trips, so identity (`toBe`) won't hold — compare structure.
    expect(result).toEqual(payload);
  });

  it("throws with code + message on error envelope", async () => {
    globalThis.fetch = vi.fn(async () =>
      mockJsonResponse(
        { success: false, error: { code: "NOT_FOUND", message: "Node missing" } },
        { status: 404 }
      )
    ) as unknown as FetchLike;

    await expect(journeyFetch("/api/journey/node/app:/missing")).rejects.toMatchObject({
      message: expect.stringContaining("Node missing"),
      code: "NOT_FOUND",
      status: 404,
    });
  });

  it("attaches `data` payload on stale-version errors for rollback use", async () => {
    const currentState = { version: 7, impl_status: "done" };
    globalThis.fetch = vi.fn(async () =>
      mockJsonResponse(
        {
          success: false,
          error: { code: "STALE_VERSION", message: "Stale" },
          data: { current: currentState },
        },
        { status: 409 }
      )
    ) as unknown as FetchLike;

    await expect(journeyFetch("/api/journey/node/app:/x/state")).rejects.toMatchObject({
      code: "STALE_VERSION",
      status: 409,
      data: { current: currentState },
    });
  });

  it("sends credentials: 'include' so the Supabase session cookie is forwarded", async () => {
    const spy = vi.fn(async () => mockJsonResponse({ success: true, data: null }));
    globalThis.fetch = spy as unknown as FetchLike;

    await journeyFetch("/api/journey/nodes");

    expect(spy).toHaveBeenCalledTimes(1);
    const callArgs = spy.mock.calls[0] as unknown as [string, RequestInit];
    expect(callArgs[0]).toBe("/api/journey/nodes");
    expect(callArgs[1]).toMatchObject({ credentials: "include" });
  });
});
