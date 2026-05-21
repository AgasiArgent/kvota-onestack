// @vitest-environment jsdom
/**
 * Validation Excel button wiring (Phase 6C-2B follow-up, 2026-05-20).
 *
 * Pre-fix: clicking "Validation Excel" opened
 *   ${legacyAppUrl}/quotes/{id}/export/validation
 * which pointed at the archived FastHTML route. Result: silent failure
 * on prod (page navigation went to a dead 404 page).
 *
 * Intermediate fix: button called
 *   window.open('/export/validation/{quoteId}', '_blank')
 * which forwarded to the new Python endpoint — but on non-200 the new
 * tab rendered the raw JSON error envelope.
 *
 * Current contract (downloadValidationExcel helper): click triggers a
 * blob-or-toast flow via the helper, no new tab is opened. We mock the
 * helper module and assert it is called with the quote id.
 *
 * Gating: still moves from `!isApproved` (controller-only) to
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

const { downloadValidationExcelMock } = vi.hoisted(() => ({
  downloadValidationExcelMock: vi.fn(),
}));
vi.mock("@/features/quotes/lib/download-validation-excel", () => ({
  downloadValidationExcel: downloadValidationExcelMock,
}));

import { CalculationActionBar } from "../calculation-action-bar";

afterEach(() => {
  cleanup();
  downloadValidationExcelMock.mockReset();
});

describe("CalculationActionBar — Validation Excel button", () => {
  it("calls downloadValidationExcel(quoteId) when clicked (no window.open)", () => {
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

    expect(downloadValidationExcelMock).toHaveBeenCalledTimes(1);
    expect(downloadValidationExcelMock).toHaveBeenCalledWith("q-1");
    // Crucially: no new tab opens. The helper handles success/error inline.
    expect(openSpy).not.toHaveBeenCalled();

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
    // (the buttons are wrapped in `{hasCalculation && (...)}`). So a
    // "disabled when no calc" assertion collapses into "not rendered".
    // This locks that contract.
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
