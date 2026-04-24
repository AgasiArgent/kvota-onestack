/**
 * Tests for the signed-URL helper (Task 24 — Req 9.7).
 *
 * Req 9.7: the `journey-verification-attachments` bucket is private; read
 * access is granted only via signed URLs (1-hour default TTL).
 *
 * The helper is a stateless call wrapper:
 *   - success → signed URL string
 *   - error   → null (callers render a broken-image icon per Req 14.6)
 */

import { describe, it, expect, vi } from "vitest";

import { getSignedUrl } from "../signed-url";

function mkSupabase(impl: {
  createSignedUrl: (
    path: string,
    ttl: number,
  ) => Promise<{
    data: { signedUrl: string } | null;
    error: unknown | null;
  }>;
}) {
  return {
    storage: {
      from: (_bucket: string) => ({
        createSignedUrl: impl.createSignedUrl,
      }),
    },
  };
}

describe("getSignedUrl", () => {
  it("returns the signed URL on success", async () => {
    const sb = mkSupabase({
      createSignedUrl: vi.fn(async () => ({
        data: { signedUrl: "https://example.com/signed?tok=abc" },
        error: null,
      })),
    });
    const out = await getSignedUrl(
      sb,
      "journey-verification-attachments",
      "app_quotes/pin-1/uuid-x.png",
    );
    expect(out).toBe("https://example.com/signed?tok=abc");
  });

  it("returns null on error", async () => {
    const sb = mkSupabase({
      createSignedUrl: vi.fn(async () => ({
        data: null,
        error: { message: "not found" },
      })),
    });
    const out = await getSignedUrl(
      sb,
      "journey-verification-attachments",
      "app_quotes/pin-1/missing.png",
    );
    expect(out).toBeNull();
  });

  it("defaults to 1-hour TTL (Req 9.7)", async () => {
    const createSignedUrl = vi.fn(async () => ({
      data: { signedUrl: "x" },
      error: null,
    }));
    const sb = mkSupabase({ createSignedUrl });
    await getSignedUrl(
      sb,
      "journey-verification-attachments",
      "path",
    );
    expect(createSignedUrl).toHaveBeenCalledWith("path", 3600);
  });

  it("accepts a custom TTL", async () => {
    const createSignedUrl = vi.fn(async () => ({
      data: { signedUrl: "x" },
      error: null,
    }));
    const sb = mkSupabase({ createSignedUrl });
    await getSignedUrl(
      sb,
      "journey-verification-attachments",
      "path",
      600,
    );
    expect(createSignedUrl).toHaveBeenCalledWith("path", 600);
  });

  it("returns null when supabase throws", async () => {
    const sb = mkSupabase({
      createSignedUrl: vi.fn(async () => {
        throw new Error("network");
      }),
    });
    const out = await getSignedUrl(
      sb,
      "journey-verification-attachments",
      "path",
    );
    expect(out).toBeNull();
  });
});
