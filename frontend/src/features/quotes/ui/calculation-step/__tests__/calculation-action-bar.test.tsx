// @vitest-environment jsdom
/**
 * Validation Excel button wiring (Phase 6C-2B follow-up, 2026-05-20).
 *
 * Pre-fix: clicking "Validation Excel" opened
 *   ${legacyAppUrl}/quotes/{id}/export/validation
 * which pointed at the archived FastHTML route. Result: silent failure
 * on prod (page navigation went to a dead 404 page).
 *
 * Post-fix: the button opens the Next.js proxy
 *   /export/validation/{quoteId}
 * which forwards to the new `/api/quotes/{id}/export/validation`
 * endpoint. Gating moves from `!isApproved` (controller-only) to
 * `!hasCalculation` (anyone can download once a calc exists).
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}));

import { CalculationActionBar } from "../calculation-action-bar";

afterEach(cleanup);

describe("CalculationActionBar — Validation Excel button", () => {
  it("opens /export/validation/{quoteId} (not legacyAppUrl) when clicked", () => {
    const openSpy = vi
      .spyOn(window, "open")
      .mockImplementation(() => null as unknown as Window);

    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={true}
        workflowStatus="calculated"
        isApproved={false}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    button.click();

    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy).toHaveBeenCalledWith("/export/validation/q-1", "_blank");
    // Must NOT point at the dead FastHTML route
    expect(openSpy.mock.calls[0][0]).not.toMatch(/legacy|kvotaflow\.ru/);

    openSpy.mockRestore();
  });

  it("is enabled when hasCalculation is true (regardless of approval)", () => {
    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={true}
        workflowStatus="calculated"
        isApproved={false}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("is disabled when hasCalculation is false", () => {
    // Note: when hasCalculation is false the entire export section is hidden
    // (lines 120-143 of calculation-action-bar.tsx wrap the buttons in
    // `{hasCalculation && (...)}`). So a "disabled when no calc" assertion
    // collapses into "not rendered". This locks that contract.
    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={false}
        workflowStatus="draft"
        isApproved={false}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /Validation Excel/ }),
    ).toBeNull();
  });

  it("does NOT gate on isApproved (post-fix change)", () => {
    // Pre-fix the button was disabled until controller approval. That
    // gate is wrong — controllers themselves need to download the file
    // BEFORE approving. The new contract: any caller with hasCalculation
    // can click.
    render(
      <CalculationActionBar
        quoteId="q-1"
        formValues={{}}
        hasCalculation={true}
        workflowStatus="pending_quote_control"
        isApproved={false}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });
});
