import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchCertificateHistory } from "../api/history";
import type { HistoryCertMatch } from "../model/types";

/**
 * Tests for `fetchCertificateHistory` — the typed wrapper over
 * `GET /api/customs/certificates/history` (Phase B Task 6 / REQ-5).
 *
 * Asserts the URL the wrapper builds — including conditional query-param
 * inclusion — and the response shape passthrough. Empty/undefined optional
 * args are dropped from the URL (server tolerates either, but skipping
 * them keeps the path clean).
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

const FAKE_MATCH: HistoryCertMatch = {
  cert_id: "cert-uuid-1",
  type: "ДС ТР ТС",
  number: "DC-123",
  issuer: "ВНИИС",
  legal_doc: "ТР ТС 010/2011",
  issued_at: "2026-01-01",
  valid_until: "2027-01-01",
  cost_rub: 12500,
  created_at: "2026-04-23T12:00:00Z",
  source_quote_id: "src-quote",
  source_item_id: "src-item",
  is_actual: true,
};

interface CapturedRequest {
  url: string;
  method: string;
}

let captured: CapturedRequest | null = null;

function mockFetchEnvelope<T>(envelope: { success: boolean; data?: T }) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    captured = {
      url,
      method: (init?.method ?? "GET").toUpperCase(),
    };
    return new Response(JSON.stringify(envelope), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

describe("fetchCertificateHistory — URL composition", () => {
  beforeEach(() => {
    captured = null;
    global.fetch = mockFetchEnvelope({
      success: true,
      data: { match: FAKE_MATCH },
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs the history endpoint with current_quote_id always present", async () => {
    await fetchCertificateHistory({ currentQuoteId: "quote-1" });
    expect(captured!.method).toBe("GET");
    expect(captured!.url).toContain("/api/customs/certificates/history");
    expect(captured!.url).toContain("current_quote_id=quote-1");
  });

  it("includes hs_code, brand and supplier_id when provided", async () => {
    await fetchCertificateHistory({
      currentQuoteId: "quote-1",
      hsCode: "8517.12.000",
      brand: "Acme",
      supplierId: "sup-uuid-1",
    });
    expect(captured!.url).toContain("hs_code=8517.12.000");
    expect(captured!.url).toContain("brand=Acme");
    expect(captured!.url).toContain("supplier_id=sup-uuid-1");
  });

  it("omits optional params when undefined", async () => {
    await fetchCertificateHistory({ currentQuoteId: "quote-1" });
    expect(captured!.url).not.toContain("hs_code=");
    expect(captured!.url).not.toContain("brand=");
    expect(captured!.url).not.toContain("supplier_id=");
  });

  it("omits optional params when explicitly empty string", async () => {
    // Empty strings are treated like undefined — the predicate
    // `if (args.hsCode)` is falsy for "".
    await fetchCertificateHistory({
      currentQuoteId: "quote-1",
      hsCode: "",
      brand: "",
      supplierId: "",
    });
    expect(captured!.url).not.toContain("hs_code=");
    expect(captured!.url).not.toContain("brand=");
    expect(captured!.url).not.toContain("supplier_id=");
  });

  it("URL-encodes special characters in brand", async () => {
    await fetchCertificateHistory({
      currentQuoteId: "quote-1",
      brand: "АО \"Свет\"",
    });
    // URLSearchParams encodes spaces as '+', quotes as %22, Cyrillic as %xx.
    expect(captured!.url).toContain("brand=");
    expect(captured!.url).toMatch(/brand=[^&]+/);
    expect(captured!.url).not.toContain('"Свет"'); // raw should not appear
  });
});

describe("fetchCertificateHistory — response passthrough", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the match envelope on a hit", async () => {
    global.fetch = mockFetchEnvelope({
      success: true,
      data: { match: FAKE_MATCH },
    }) as unknown as typeof fetch;
    const res = await fetchCertificateHistory({ currentQuoteId: "q" });
    expect(res.success).toBe(true);
    expect(res.data?.match).toEqual(FAKE_MATCH);
  });

  it("returns a null match envelope on a miss", async () => {
    global.fetch = mockFetchEnvelope({
      success: true,
      data: { match: null },
    }) as unknown as typeof fetch;
    const res = await fetchCertificateHistory({ currentQuoteId: "q" });
    expect(res.success).toBe(true);
    expect(res.data?.match).toBeNull();
  });

  it("preserves a failure envelope", async () => {
    global.fetch = mockFetchEnvelope({
      success: false,
    }) as unknown as typeof fetch;
    const res = await fetchCertificateHistory({ currentQuoteId: "q" });
    expect(res.success).toBe(false);
  });

  it("forwards is_actual=false (expired cert) verbatim", async () => {
    global.fetch = mockFetchEnvelope({
      success: true,
      data: {
        match: { ...FAKE_MATCH, is_actual: false, valid_until: "2025-01-01" },
      },
    }) as unknown as typeof fetch;
    const res = await fetchCertificateHistory({ currentQuoteId: "q" });
    expect(res.data?.match?.is_actual).toBe(false);
  });
});
