import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Validation Excel proxy route.
 *
 * Replaces the dead FastHTML route `${legacyAppUrl}/quotes/{id}/export/validation`
 * (archived 2026-04-20 in Phase 6C-2B-Mega-C). The Next.js side is a
 * thin proxy: forward Bearer JWT downstream to Python API at
 * `/api/quotes/{id}/export/validation` and stream back the xlsm bytes.
 *
 * Why a proxy (not direct SSR-Supabase like kp/spec): the validation
 * Excel is built by `services/export_validation_service.py` which
 * stitches Python-side calculation engine inputs with the openpyxl
 * template. The TS layer should not duplicate that logic — it owns auth
 * forwarding and response passthrough only.
 */

interface CapturedRequest {
  url: string;
  method: string;
  headers: Record<string, string>;
}

let captured: CapturedRequest | null = null;
let fakeSession: { access_token: string } | null = {
  access_token: "fake-jwt-token",
};
let fakeUpstreamResponse: Response;

vi.mock("@/shared/lib/supabase/server", () => ({
  createClient: async () => ({
    auth: {
      getSession: async () => ({ data: { session: fakeSession } }),
    },
  }),
}));

function setupFetchMock() {
  global.fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    captured = {
      url,
      method: (init?.method ?? "GET").toUpperCase(),
      headers: (init?.headers as Record<string, string>) ?? {},
    };
    return fakeUpstreamResponse;
  }) as typeof fetch;
}

async function callRoute(id = "q-1") {
  const { GET } = await import("../route");
  const req = new Request(`http://localhost/export/validation/${id}`);
  const params = Promise.resolve({ id });
  return GET(req, { params });
}

describe("Validation Excel proxy route — Phase 6C-2B follow-up", () => {
  beforeEach(() => {
    captured = null;
    fakeSession = { access_token: "fake-jwt-token" };
    fakeUpstreamResponse = new Response(
      new Uint8Array([0x50, 0x4b, 0x03, 0x04, 0xde, 0xad, 0xbe, 0xef]),
      {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.ms-excel.sheet.macroEnabled.12",
          "Content-Disposition": 'attachment; filename="validation_Q-202605-0018.xlsm"',
        },
      },
    );
    setupFetchMock();
  });

  it("returns 401 when there is no Supabase session", async () => {
    fakeSession = null;

    const resp = await callRoute();

    expect(resp.status).toBe(401);
    // Must NOT have called the Python API
    expect(captured).toBeNull();
  });

  it("forwards Bearer JWT downstream to Python API", async () => {
    await callRoute("q-1");

    expect(captured).not.toBeNull();
    expect(captured!.headers.Authorization).toBe("Bearer fake-jwt-token");
    expect(captured!.url).toMatch(/\/api\/quotes\/q-1\/export\/validation$/);
    expect(captured!.method).toBe("GET");
  });

  it("preserves Content-Type and Content-Disposition from Python response", async () => {
    const resp = await callRoute("q-1");

    expect(resp.status).toBe(200);
    expect(resp.headers.get("Content-Type")).toBe(
      "application/vnd.ms-excel.sheet.macroEnabled.12",
    );
    expect(resp.headers.get("Content-Disposition")).toBe(
      'attachment; filename="validation_Q-202605-0018.xlsm"',
    );
  });

  it("forwards body bytes correctly", async () => {
    const resp = await callRoute("q-1");

    const body = new Uint8Array(await resp.arrayBuffer());
    expect(Array.from(body)).toEqual([
      0x50, 0x4b, 0x03, 0x04, 0xde, 0xad, 0xbe, 0xef,
    ]);
  });

  it("propagates non-200 status from Python", async () => {
    fakeUpstreamResponse = new Response(
      JSON.stringify({ error: "Quote not found: q-missing" }),
      {
        status: 404,
        headers: { "Content-Type": "application/json" },
      },
    );

    const resp = await callRoute("q-missing");

    expect(resp.status).toBe(404);
  });
});
