import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  attachCertificateItem,
  createCertificate,
  deleteCertificate,
  detachCertificateItem,
  listCertificates,
} from "../api/certificates";
import type { Certificate } from "../model/types";

/**
 * Tests for the typed API wrappers (Phase B Task 6).
 *
 * The wrappers delegate to `apiClient` from `@/shared/lib/api`, which
 * itself calls `fetch` with the `/api{path}` prefix and a Supabase JWT
 * header (mocked here to a static token). We assert on:
 *   1. The URL the wrapper builds (path + query encoding).
 *   2. The HTTP method.
 *   3. The serialized body (for write endpoints).
 *
 * Mocking strategy: stub `@/shared/lib/supabase/client` so `apiClient`
 * can hand back a fake session, then stub global `fetch` to capture the
 * outgoing request and return a canned envelope.
 */

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: () =>
        Promise.resolve({
          data: { session: { access_token: "test-jwt" } },
        }),
    },
  }),
}));

const FAKE_CERT: Certificate = {
  id: "cert-uuid-1",
  quote_id: "quote-uuid-1",
  type: "ДС ТР ТС",
  number: "DC-001",
  issuer: null,
  legal_doc: null,
  issued_at: null,
  valid_until: null,
  cost_rub: 12500,
  notes: null,
  display_name: null,
  is_custom_expense: false,
  created_at: "2026-05-04T10:00:00Z",
  updated_at: "2026-05-04T10:00:00Z",
  created_by: "user-uuid-1",
  attached_items: [],
};

interface CapturedRequest {
  url: string;
  method: string;
  body: string | null;
  headers: Record<string, string>;
}

let captured: CapturedRequest | null = null;

function mockFetchResponse<T>(envelope: { success: boolean; data?: T }) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    captured = {
      url,
      method: (init?.method ?? "GET").toUpperCase(),
      body: typeof init?.body === "string" ? init.body : null,
      headers: (init?.headers as Record<string, string>) ?? {},
    };
    return new Response(JSON.stringify(envelope), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("createCertificate", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: true,
      data: FAKE_CERT,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs to /api/customs/certificates with the input as JSON body", async () => {
    const input = {
      quote_id: "quote-uuid-1",
      type: "ДС ТР ТС",
      cost_rub: 12500,
      item_ids: ["item-1", "item-2"],
    };
    const res = await createCertificate(input);
    expect(res.success).toBe(true);
    expect(res.data).toEqual(FAKE_CERT);
    expect(captured).not.toBeNull();
    expect(captured!.url).toContain("/api/customs/certificates");
    expect(captured!.method).toBe("POST");
    expect(captured!.body).toBe(JSON.stringify(input));
  });

  it("forwards the Authorization Bearer header from the Supabase session", async () => {
    await createCertificate({
      quote_id: "q",
      type: "СС",
      cost_rub: 0,
      item_ids: [],
    });
    expect(captured!.headers.Authorization).toBe("Bearer test-jwt");
  });

  it("sets Content-Type when sending a body", async () => {
    await createCertificate({
      quote_id: "q",
      type: "СС",
      cost_rub: 0,
      item_ids: [],
    });
    expect(captured!.headers["Content-Type"]).toBe("application/json");
  });
});

describe("listCertificates", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: true,
      data: { certificates: [FAKE_CERT] },
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs /api/customs/certificates with quote_id query param", async () => {
    const res = await listCertificates("quote-uuid-1");
    expect(res.success).toBe(true);
    expect(res.data?.certificates).toHaveLength(1);
    expect(captured!.url).toContain(
      "/api/customs/certificates?quote_id=quote-uuid-1",
    );
    expect(captured!.method).toBe("GET");
  });

  it("URL-encodes the quote_id parameter", async () => {
    await listCertificates("quote/with/slashes");
    expect(captured!.url).toContain("quote_id=quote%2Fwith%2Fslashes");
  });

  it("sends no body on GET", async () => {
    await listCertificates("any");
    expect(captured!.body).toBeNull();
  });
});

describe("attachCertificateItem", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: true,
      data: FAKE_CERT,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs to /api/customs/certificates/{cert_id}/items with item_id body", async () => {
    const res = await attachCertificateItem("cert-uuid-1", "item-uuid-9");
    expect(res.success).toBe(true);
    expect(captured!.url).toContain(
      "/api/customs/certificates/cert-uuid-1/items",
    );
    expect(captured!.method).toBe("POST");
    expect(captured!.body).toBe(JSON.stringify({ item_id: "item-uuid-9" }));
  });

  it("URL-encodes the cert_id segment", async () => {
    await attachCertificateItem("cert/with/slashes", "item-9");
    expect(captured!.url).toContain(
      "/api/customs/certificates/cert%2Fwith%2Fslashes/items",
    );
  });
});

describe("detachCertificateItem", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: true,
      data: FAKE_CERT,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("DELETEs /api/customs/certificates/{cert_id}/items/{item_id}", async () => {
    const res = await detachCertificateItem("cert-uuid-1", "item-uuid-9");
    expect(res.success).toBe(true);
    expect(captured!.url).toContain(
      "/api/customs/certificates/cert-uuid-1/items/item-uuid-9",
    );
    expect(captured!.method).toBe("DELETE");
    // DELETE requests carry no body.
    expect(captured!.body).toBeNull();
  });

  it("URL-encodes both path segments", async () => {
    await detachCertificateItem("c/x", "i/y");
    expect(captured!.url).toContain(
      "/api/customs/certificates/c%2Fx/items/i%2Fy",
    );
  });
});

describe("deleteCertificate", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: true,
      data: { deleted_id: "cert-uuid-1" },
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("DELETEs /api/customs/certificates/{cert_id}", async () => {
    const res = await deleteCertificate("cert-uuid-1");
    expect(res.success).toBe(true);
    expect(res.data?.deleted_id).toBe("cert-uuid-1");
    expect(captured!.url).toContain("/api/customs/certificates/cert-uuid-1");
    expect(captured!.method).toBe("DELETE");
    expect(captured!.body).toBeNull();
  });

  it("URL-encodes the cert_id segment", async () => {
    await deleteCertificate("with spaces");
    expect(captured!.url).toContain(
      "/api/customs/certificates/with%20spaces",
    );
  });
});

describe("error envelope passthrough", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchResponse({
      success: false,
      data: undefined,
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the failure envelope verbatim from createCertificate", async () => {
    const res = await createCertificate({
      quote_id: "q",
      type: "X",
      cost_rub: 0,
      item_ids: [],
    });
    expect(res.success).toBe(false);
  });
});
