// @vitest-environment jsdom
/**
 * Tests for the `uploadInvoiceXls` mutation (Testing 2 row 70).
 *
 * Mirrors download-validation-excel.dom.test.ts in shape — mocks
 * ``globalThis.fetch`` and asserts the request payload + error parsing.
 */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

// ---------------------------------------------------------------------------
// Supabase mock (must be hoisted: the module under test calls createClient()
// during getAuthHeaders, which would otherwise hit the real Supabase env).
// ---------------------------------------------------------------------------
const { getSessionMock } = vi.hoisted(() => ({
  getSessionMock: vi.fn(),
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { getSession: getSessionMock },
  }),
}));

import { uploadInvoiceXls } from "../mutations";

const originalFetch = globalThis.fetch;

beforeEach(() => {
  getSessionMock.mockReset();
  getSessionMock.mockResolvedValue({
    data: { session: { access_token: "test-jwt" } },
  });
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function buildResponse(opts: {
  ok: boolean;
  status?: number;
  json?: unknown;
}): Response {
  return {
    ok: opts.ok,
    status: opts.status ?? (opts.ok ? 200 : 400),
    statusText: "",
    headers: new Headers(),
    json: async () => opts.json,
  } as unknown as Response;
}

describe("uploadInvoiceXls — happy path", () => {
  it("POSTs the file as multipart with the JWT and returns the summary", async () => {
    const fetchMock: ReturnType<typeof vi.fn> = vi.fn(async () =>
      buildResponse({
        ok: true,
        status: 200,
        json: {
          success: true,
          data: { updated: 3, skipped: ["UNKNOWN-1"], total_in_file: 4 },
        },
      }),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const file = new File(["x"], "test.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    const result = await uploadInvoiceXls("inv-001", file);

    // Endpoint URL + method
    const calls = fetchMock.mock.calls as unknown as Array<
      [string, RequestInit]
    >;
    expect(calls.length).toBe(1);
    const [url, init] = calls[0];
    expect(url).toBe("/api/invoices/inv-001/import-xls");
    expect(init.method).toBe("POST");
    // Body is FormData with the file under key "file"
    const body = init.body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBeInstanceOf(File);
    // JWT header forwarded — Content-Type must NOT be set (browser sets the
    // multipart boundary automatically; setting it manually breaks parsing).
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer test-jwt");
    expect(headers["Content-Type"]).toBeUndefined();

    // Result is the typed summary
    expect(result).toEqual({
      updated: 3,
      skipped: ["UNKNOWN-1"],
      total_in_file: 4,
    });
  });
});

describe("uploadInvoiceXls — duplicates (400)", () => {
  it("throws with the duplicates list in the error message", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 400,
        json: {
          success: false,
          error: {
            code: "DUPLICATES",
            message: "Дубликаты артикулов: SKU-A, SKU-B",
            duplicates: ["SKU-A", "SKU-B"],
          },
        },
      }),
    ) as unknown as typeof fetch;

    const file = new File(["x"], "test.xlsx");

    await expect(uploadInvoiceXls("inv-001", file)).rejects.toThrow(
      /Дубликаты артикулов: SKU-A, SKU-B/,
    );
  });
});

describe("uploadInvoiceXls — generic failure", () => {
  it("throws with the server message when the envelope has one", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 500,
        json: {
          success: false,
          error: { code: "INTERNAL_ERROR", message: "Что-то пошло не так" },
        },
      }),
    ) as unknown as typeof fetch;

    const file = new File(["x"], "test.xlsx");

    await expect(uploadInvoiceXls("inv-001", file)).rejects.toThrow(
      /Что-то пошло не так/,
    );
  });

  it("falls back to a default message when the body is unreadable", async () => {
    globalThis.fetch = vi.fn(async () =>
      ({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: async () => {
          throw new Error("no body");
        },
      }) as unknown as Response,
    ) as unknown as typeof fetch;

    const file = new File(["x"], "test.xlsx");

    await expect(uploadInvoiceXls("inv-001", file)).rejects.toThrow(
      /HTTP 500/,
    );
  });
});
