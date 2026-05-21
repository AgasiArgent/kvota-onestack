// @vitest-environment jsdom
/**
 * Tests for the `downloadValidationExcel` helper (Phase 6C-2B follow-up,
 * 2026-05-20).
 *
 * The helper replaces `window.open('/export/validation/{id}', '_blank')`,
 * which rendered raw error JSON in a new tab when the Python API returned
 * non-200. The new flow:
 *   - fetches as blob and triggers a hidden <a download> click on 200
 *   - parses JSON error envelope and shows a toast on non-200
 *   - never opens a new tab
 *
 * Mocks: global.fetch, sonner.toast, URL.createObjectURL /
 * URL.revokeObjectURL. We assert against the toast mock and against the
 * DOM (createElement / appendChild / removeChild / anchor.click).
 *
 * Filename is `.dom.test.ts` to opt into the jsdom vitest project (see
 * frontend/vitest.config.ts).
 */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";

const { toastErrorMock, toastSuccessMock } = vi.hoisted(() => ({
  toastErrorMock: vi.fn(),
  toastSuccessMock: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    error: toastErrorMock,
    success: toastSuccessMock,
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { downloadValidationExcel } from "../download-validation-excel";

const originalFetch = globalThis.fetch;
const originalCreateObjectURL = URL.createObjectURL;
const originalRevokeObjectURL = URL.revokeObjectURL;

let createObjectURLMock: ReturnType<typeof vi.fn>;
let revokeObjectURLMock: ReturnType<typeof vi.fn>;
let windowOpenSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.useFakeTimers();
  toastErrorMock.mockClear();
  toastSuccessMock.mockClear();

  createObjectURLMock = vi.fn(() => "blob:mock-url");
  revokeObjectURLMock = vi.fn();
  URL.createObjectURL = createObjectURLMock as unknown as typeof URL.createObjectURL;
  URL.revokeObjectURL = revokeObjectURLMock as unknown as typeof URL.revokeObjectURL;

  windowOpenSpy = vi
    .spyOn(window, "open")
    .mockImplementation(() => null as unknown as Window);
});

afterEach(() => {
  vi.useRealTimers();
  globalThis.fetch = originalFetch;
  URL.createObjectURL = originalCreateObjectURL;
  URL.revokeObjectURL = originalRevokeObjectURL;
  windowOpenSpy.mockRestore();
});

/**
 * Builds a Response-like object that the helper consumes. We avoid `new
 * Response(...)` because jsdom's Response.blob() implementation does not
 * round-trip text/binary cleanly across vitest's mock boundary.
 */
function buildResponse(opts: {
  ok: boolean;
  status?: number;
  statusText?: string;
  headers?: Record<string, string>;
  blob?: Blob;
  json?: unknown;
}): Response {
  const headers = new Headers(opts.headers ?? {});
  return {
    ok: opts.ok,
    status: opts.status ?? (opts.ok ? 200 : 500),
    statusText: opts.statusText ?? "",
    headers,
    blob: async () => opts.blob ?? new Blob(["x"]),
    json: async () => {
      if (opts.json === undefined) {
        throw new Error("no json body");
      }
      return opts.json;
    },
  } as unknown as Response;
}

describe("downloadValidationExcel — happy path (200)", () => {
  it("triggers a hidden <a download> click with the correct extension and revokes the object URL", async () => {
    const blob = new Blob(["binary-xlsm-bytes"]);
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: true,
        status: 200,
        headers: {
          "Content-Type":
            "application/vnd.ms-excel.sheet.macroEnabled.12",
        },
        blob,
      }),
    ) as unknown as typeof fetch;

    const appendSpy = vi.spyOn(document.body, "appendChild");
    const removeSpy = vi.spyOn(document.body, "removeChild");

    await downloadValidationExcel("quote-abc");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/export/validation/quote-abc",
    );

    // Anchor created, clicked, appended/removed.
    const anchorArg = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchorArg).toBeInstanceOf(HTMLAnchorElement);
    expect(anchorArg.download).toBe("validation_quote-abc.xlsm");
    expect(anchorArg.href).toContain("blob:mock-url");
    expect(removeSpy).toHaveBeenCalledWith(anchorArg);

    expect(createObjectURLMock).toHaveBeenCalledWith(blob);
    expect(toastSuccessMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock).not.toHaveBeenCalled();
    expect(windowOpenSpy).not.toHaveBeenCalled();

    // Revoke runs on a 1s timer.
    vi.advanceTimersByTime(1000);
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:mock-url");

    appendSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("uses the filename from Content-Disposition when present", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: true,
        headers: {
          "Content-Disposition": 'attachment; filename="my-quote.xlsm"',
        },
      }),
    ) as unknown as typeof fetch;

    const appendSpy = vi.spyOn(document.body, "appendChild");

    await downloadValidationExcel("quote-1");

    const anchorArg = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchorArg.download).toBe("my-quote.xlsm");

    appendSpy.mockRestore();
  });

  it("falls back to validation_{id}.xlsm when Content-Disposition is missing", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({ ok: true, headers: {} }),
    ) as unknown as typeof fetch;

    const appendSpy = vi.spyOn(document.body, "appendChild");

    await downloadValidationExcel("quote-fallback");

    const anchorArg = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchorArg.download).toBe("validation_quote-fallback.xlsm");

    appendSpy.mockRestore();
  });
});

describe("downloadValidationExcel — error responses", () => {
  it("shows error toast for 401 with {error: 'Unauthorized'} envelope", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        json: { error: "Unauthorized" },
      }),
    ) as unknown as typeof fetch;

    await downloadValidationExcel("quote-401");

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock.mock.calls[0]?.[0]).toContain("Unauthorized");
    expect(toastSuccessMock).not.toHaveBeenCalled();
    expect(windowOpenSpy).not.toHaveBeenCalled();
    expect(createObjectURLMock).not.toHaveBeenCalled();
  });

  it("shows error toast for 404", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: { error: { message: "Quote not found" } },
      }),
    ) as unknown as typeof fetch;

    await downloadValidationExcel("missing");

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock.mock.calls[0]?.[0]).toContain("Quote not found");
    expect(windowOpenSpy).not.toHaveBeenCalled();
  });

  it("shows error toast for 500", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: { error: { message: "Calc engine crashed" } },
      }),
    ) as unknown as typeof fetch;

    await downloadValidationExcel("boom");

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock.mock.calls[0]?.[0]).toContain("Calc engine crashed");
    expect(windowOpenSpy).not.toHaveBeenCalled();
  });

  it("falls back to statusText when error body is not JSON", async () => {
    globalThis.fetch = vi.fn(async () =>
      buildResponse({
        ok: false,
        status: 502,
        statusText: "Bad Gateway",
        // no `json` key → buildResponse's json() throws
      }),
    ) as unknown as typeof fetch;

    await downloadValidationExcel("gateway");

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock.mock.calls[0]?.[0]).toContain("Bad Gateway");
    expect(windowOpenSpy).not.toHaveBeenCalled();
  });

  it("shows fallback toast when fetch itself throws (network error)", async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    await downloadValidationExcel("offline");

    expect(toastErrorMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock.mock.calls[0]?.[0]).toContain("Не удалось скачать");
    expect(windowOpenSpy).not.toHaveBeenCalled();
    expect(createObjectURLMock).not.toHaveBeenCalled();
  });

  it("never opens a new tab on any error path", async () => {
    // Sanity sweep: covers the contract that distinguishes this helper from
    // the old window.open behaviour. window.open is spied in beforeEach.
    const errorCases = [
      { ok: false, status: 401, json: { error: "Unauthorized" } },
      { ok: false, status: 403, json: { error: { message: "Forbidden" } } },
      { ok: false, status: 404, json: { error: "Not found" } },
      { ok: false, status: 500, json: { error: { message: "boom" } } },
    ];

    for (const c of errorCases) {
      globalThis.fetch = vi.fn(async () =>
        buildResponse({
          ok: c.ok,
          status: c.status,
          statusText: `HTTP ${c.status}`,
          json: c.json,
        }),
      ) as unknown as typeof fetch;
      await downloadValidationExcel(`q-${c.status}`);
    }

    expect(windowOpenSpy).not.toHaveBeenCalled();
  });
});
