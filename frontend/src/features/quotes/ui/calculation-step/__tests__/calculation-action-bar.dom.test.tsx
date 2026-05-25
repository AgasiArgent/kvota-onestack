// @vitest-environment jsdom
/**
 * Calc-step P0 fix (2026-05-25) — MISSING_PRICES banner.
 *
 * Pre-fix: clicking «Рассчитать» on a quote with an unpriced item produced a
 * 400 with body
 *   {"success": false,
 *    "error": {"code": "MISSING_PRICES", "message": "Not all items have prices"},
 *    "items_without_price": ["Brand — Item"]}
 * The frontend toast read only `error.message` — English, no item names,
 * dismissed after 4s. The tester had no actionable signal.
 *
 * Post-fix contract:
 *   - On MISSING_PRICES with non-empty items_without_price[], the toast is
 *     Russian, lists every blocked item, and is persistent (duration: Infinity).
 *   - On any OTHER error, the original behavior is preserved (toast.error
 *     with the extracted message).
 *   - On 200 success, toast.success("Расчёт выполнен") fires and the router
 *     is refreshed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const refreshMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: refreshMock }),
}));

const toastErrorMock = vi.fn();
const toastSuccessMock = vi.fn();
vi.mock("sonner", () => ({
  toast: {
    error: (...args: unknown[]) => toastErrorMock(...args),
    success: (...args: unknown[]) => toastSuccessMock(...args),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock("@/shared/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      getSession: async () => ({
        data: { session: { access_token: "fake-token" } },
      }),
    },
  }),
}));

vi.mock("@/features/quotes/lib/download-validation-excel", () => ({
  downloadValidationExcel: vi.fn(),
}));

import { CalculationActionBar } from "../calculation-action-bar";

const originalFetch = global.fetch;

beforeEach(() => {
  refreshMock.mockReset();
  toastErrorMock.mockReset();
  toastSuccessMock.mockReset();
});

afterEach(() => {
  cleanup();
  global.fetch = originalFetch;
});

function mockFetchResponse(status: number, body: unknown): void {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }) as unknown as typeof fetch;
}

describe("CalculationActionBar — MISSING_PRICES handling", () => {
  it("shows persistent Russian banner with item list on 400 + items_without_price", async () => {
    mockFetchResponse(400, {
      success: false,
      error: { code: "MISSING_PRICES", message: "Not all items have prices" },
      items_without_price: [
        "Китайский бренд — Миксер пневматический PM-3/TJ3",
        "Brand B — Item X",
      ],
    });

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() => expect(toastErrorMock).toHaveBeenCalledTimes(1));

    const [title, opts] = toastErrorMock.mock.calls[0] as [
      string,
      { description?: string; duration?: number },
    ];
    expect(title).toBe("Не у всех позиций есть цена");
    expect(opts.description).toContain(
      "Китайский бренд — Миксер пневматический PM-3/TJ3",
    );
    expect(opts.description).toContain("Brand B — Item X");
    expect(opts.duration).toBe(Infinity);

    // Success toast must not fire on error.
    expect(toastSuccessMock).not.toHaveBeenCalled();
    // Router must not refresh on error.
    expect(refreshMock).not.toHaveBeenCalled();
  });

  it("falls back to extracted error message when items_without_price is missing", async () => {
    mockFetchResponse(400, {
      success: false,
      error: { code: "MISSING_PRICES", message: "Not all items have prices" },
      // items_without_price intentionally absent
    });

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() => expect(toastErrorMock).toHaveBeenCalledTimes(1));

    const [msg] = toastErrorMock.mock.calls[0] as [string];
    // Single-arg shape — the original behaviour.
    expect(msg).toBe("Not all items have prices");
  });

  it("falls back to extracted error message when items_without_price is an empty array", async () => {
    mockFetchResponse(400, {
      success: false,
      error: { code: "MISSING_PRICES", message: "Not all items have prices" },
      items_without_price: [],
    });

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() => expect(toastErrorMock).toHaveBeenCalledTimes(1));

    const [msg] = toastErrorMock.mock.calls[0] as [string];
    expect(msg).toBe("Not all items have prices");
  });

  it("preserves original toast behavior for non-MISSING_PRICES errors", async () => {
    mockFetchResponse(500, {
      success: false,
      error: { code: "INTERNAL_ERROR", message: "Something broke" },
    });

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() => expect(toastErrorMock).toHaveBeenCalledTimes(1));

    const [msg] = toastErrorMock.mock.calls[0] as [string];
    // Single-arg form — generic path, NOT the structured persistent banner.
    expect(msg).toBe("Something broke");
  });

  it("fires success toast and refreshes router on 200", async () => {
    mockFetchResponse(200, { success: true });

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Рассчитать/ }));

    await waitFor(() => expect(toastSuccessMock).toHaveBeenCalledTimes(1));
    expect(toastSuccessMock).toHaveBeenCalledWith("Расчёт выполнен");
    expect(refreshMock).toHaveBeenCalledTimes(1);
    expect(toastErrorMock).not.toHaveBeenCalled();
  });
});
