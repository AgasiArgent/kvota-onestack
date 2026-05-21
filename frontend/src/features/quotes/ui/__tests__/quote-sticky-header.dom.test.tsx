// @vitest-environment jsdom
/**
 * FB-260513-155446-efa0 — back arrow regression (Testing 2, row 22).
 *
 * All 8 testers reported: «Кнопка назад ведёт не на предыдущую страницу, а
 * в раздел КП». The fix replaces the static `<Link href="/quotes">` with a
 * button that calls `router.back()` (and falls back to /quotes only when
 * the user opened the quote in a fresh tab without history).
 *
 * This test pins the new behavior so it does not silently regress to a
 * hard-coded `/quotes` push.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import type { QuoteDetailRow } from "@/entities/quote/queries";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

const back = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push,
    replace: () => {},
    back,
    forward: () => {},
    prefetch: () => {},
  }),
  useSearchParams: () => ({
    toString: () => "",
    get: () => null,
  }),
}));

vi.mock("../delete-menu/delete-menu", () => ({
  DeleteMenu: () => null,
}));

import { QuoteStickyHeader } from "../quote-sticky-header";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const quote = {
  id: "q-1",
  idn_quote: "Q-202605-0001",
  workflow_status: "draft",
  created_at: "2026-05-13T10:00:00Z",
  total_quote_currency: 1000,
  profit_quote_currency: 100,
  revenue_no_vat_quote_currency: 900,
  currency: "RUB",
  customer: { id: "c-1", name: "ACME" },
  cancellation_comment: null,
} as unknown as QuoteDetailRow;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("QuoteStickyHeader — back button", () => {
  afterEach(() => {
    cleanup();
    back.mockReset();
    push.mockReset();
  });

  it("renders a button (not a Link to /quotes) labelled «Назад»", () => {
    render(
      <QuoteStickyHeader
        quote={quote}
        userRoles={["sales"]}
        isContextOpen={false}
        onToggleContext={() => {}}
      />,
    );

    const backBtn = screen.getByRole("button", { name: /Назад/ });
    expect(backBtn.tagName).toBe("BUTTON");
    // Should NOT be a link that always points at /quotes.
    expect(backBtn.getAttribute("href")).toBeNull();
  });

  it("calls router.back() when browser history is available", () => {
    // jsdom defaults to history.length = 1, so push a fake entry first.
    window.history.pushState({}, "", "/quotes");
    window.history.pushState({}, "", "/quotes/q-1");
    expect(window.history.length).toBeGreaterThan(1);

    render(
      <QuoteStickyHeader
        quote={quote}
        userRoles={["sales"]}
        isContextOpen={false}
        onToggleContext={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Назад/ }));

    expect(back).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });
});
