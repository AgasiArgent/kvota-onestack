// @vitest-environment jsdom
/**
 * Validation Excel button wiring on the control page (Phase 6C-2B
 * follow-up, 2026-05-20).
 *
 * Pre-fix: button was hardcoded `disabled` and pointed at
 *   ${legacyAppUrl}/quotes/{id}/export/validation
 * Both wrong:
 *   1. Hardcoded `disabled` — controllers couldn't click the button at all.
 *   2. URL — the FastHTML route was archived 2026-04-20.
 *
 * Intermediate fix: button called
 *   window.open('/export/validation/{quoteId}', '_blank')
 * but a non-200 response from the Python endpoint rendered raw JSON in the
 * new tab.
 *
 * Current contract (downloadValidationExcel helper): click runs the
 * blob-or-toast flow via the helper, no new tab is opened. We mock the
 * helper module and assert it is called with the quote id.
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

vi.mock("@/entities/quote/mutations", () => ({
  approveQuote: vi.fn(),
  escalateQuote: vi.fn(),
}));

const { downloadValidationExcelMock } = vi.hoisted(() => ({
  downloadValidationExcelMock: vi.fn(),
}));
vi.mock("@/features/quotes/lib/download-validation-excel", () => ({
  downloadValidationExcel: downloadValidationExcelMock,
}));

import { ControlActionBar } from "../control-action-bar";

afterEach(() => {
  cleanup();
  downloadValidationExcelMock.mockReset();
});

describe("ControlActionBar — Validation Excel button", () => {
  it("calls downloadValidationExcel(quoteId) when clicked (no window.open)", () => {
    const openSpy = vi
      .spyOn(window, "open")
      .mockImplementation(() => null as unknown as Window);

    render(
      <ControlActionBar
        quoteId="q-1"
        userId="user-1"
        workflowStatus="pending_quote_control"
        needsApproval={false}
        hasCalculation={true}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    button.click();

    expect(downloadValidationExcelMock).toHaveBeenCalledTimes(1);
    expect(downloadValidationExcelMock).toHaveBeenCalledWith("q-1");
    // No new tab — the helper handles success/error inline.
    expect(openSpy).not.toHaveBeenCalled();

    openSpy.mockRestore();
  });

  it("is enabled when the bar renders in a control workflow state with hasCalculation=true", () => {
    render(
      <ControlActionBar
        quoteId="q-1"
        userId="user-1"
        workflowStatus="pending_quote_control"
        needsApproval={false}
        hasCalculation={true}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    expect((button as HTMLButtonElement).disabled).toBe(false);
  });

  it("is disabled when hasCalculation=false (lingering total_amount, stale calc)", () => {
    // Regression for the 2026-05-25 "validation file excel скачивается
    // пустой" bug: ControlActionBar must disable the button when the
    // parent has signalled that quote_calculation_results rows are
    // missing — even though the quote still has a non-null total_amount.
    // See /tmp/validation-xlsm-investigate-2026-05-25.md.
    render(
      <ControlActionBar
        quoteId="q-1"
        userId="user-1"
        workflowStatus="pending_quote_control"
        needsApproval={false}
        hasCalculation={false}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("does not render the bar at all outside of control states", () => {
    // Sanity: the component early-returns null when workflow_status is
    // neither `pending_quote_control` nor `pending_approval`. We rely on
    // that contract for the "enabled when rendered" guarantee above.
    render(
      <ControlActionBar
        quoteId="q-1"
        userId="user-1"
        workflowStatus="draft"
        needsApproval={false}
        hasCalculation={true}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /Validation Excel/ }),
    ).toBeNull();
  });
});
