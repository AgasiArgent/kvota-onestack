import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/**
 * Task 76 — fetchSupplierVatRate unit tests.
 *
 * fetchSupplierVatRate calls the Python API endpoint
 *   GET /api/geo/vat-rate?supplier_country_code=XX&buyer_company_id=UUID
 * and returns { rate, reason } on success or null on any failure
 * (network error, non-2xx, envelope.success=false, malformed payload).
 *
 * The function must never throw — callers decide UI behavior based on the
 * returned value. "unknown" is a legitimate successful reason, not an error.
 */

const getSessionMock = vi.fn();

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: getSessionMock },
  }),
}));

// Global fetch mock — reset between tests.
const originalFetch = globalThis.fetch;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  getSessionMock.mockReset();
  getSessionMock.mockResolvedValue({
    data: { session: { access_token: "test-jwt" } },
  });
  fetchMock = vi.fn();
  // Cast: happy-dom typings differ from the fetch type in some setups; the
  // runtime contract is the same.
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch;
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe("fetchSupplierVatRate — URL & auth", () => {
  it("hits /api/geo/vat-rate with both supplier_country_code and buyer_company_id", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 22, reason: "domestic" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "00000000-0000-0000-0000-000000000001",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("supplier_country_code=RU");
    expect(url).toContain(
      "buyer_company_id=00000000-0000-0000-0000-000000000001"
    );
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-jwt"
    );
  });

  it("URL-encodes both query parameters", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 0, reason: "unknown" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    await fetchSupplierVatRate({
      supplierCountryCode: "de",
      buyerCompanyId: "buyer with spaces",
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("supplier_country_code=de");
    expect(url).toContain("buyer_company_id=buyer%20with%20spaces");
  });

  it("omits Authorization header when no active session", async () => {
    getSessionMock.mockResolvedValueOnce({ data: { session: null } });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 0, reason: "unknown" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    await fetchSupplierVatRate({
      supplierCountryCode: "US",
      buyerCompanyId: "b-1",
    });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });
});

describe("fetchSupplierVatRate — successful responses", () => {
  it("returns { rate, reason } for domestic match", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 22, reason: "domestic" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toEqual({ rate: 22, reason: "domestic" });
  });

  it("returns { rate: 0, reason: 'export_zero_rated' } for cross-border trade", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 0, reason: "export_zero_rated" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "DE",
      buyerCompanyId: "b-1",
    });

    expect(result).toEqual({ rate: 0, reason: "export_zero_rated" });
  });

  it("returns { rate: 0, reason: 'unknown' } when backend cannot resolve", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 0, reason: "unknown" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "XX",
      buyerCompanyId: "b-1",
    });

    expect(result).toEqual({ rate: 0, reason: "unknown" });
  });
});

describe("fetchSupplierVatRate — failure modes return null", () => {
  it("returns null on 404 (buyer_company_id not found)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        success: false,
        error: { code: "NOT_FOUND", message: "buyer_company_id not found" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "missing",
    });

    expect(result).toBeNull();
  });

  it("returns null on 400 (malformed params)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({
        success: false,
        error: { code: "VALIDATION_ERROR", message: "bad input" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "X",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null on 500 (server error)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ success: false }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null when network rejects (offline / DNS)", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null when success=false even with 200", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: false, data: { rate: 22, reason: "domestic" } }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null when reason is an unknown string", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { rate: 22, reason: "made_up_value" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null when rate is missing / non-numeric", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { reason: "domestic" },
      }),
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });

  it("returns null when JSON parse fails", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => {
        throw new SyntaxError("unexpected token");
      },
    });

    const { fetchSupplierVatRate } = await import("../queries");
    const result = await fetchSupplierVatRate({
      supplierCountryCode: "RU",
      buyerCompanyId: "b-1",
    });

    expect(result).toBeNull();
  });
});
