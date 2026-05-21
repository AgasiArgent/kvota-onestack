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

  it("is enabled when the bar renders in a control workflow state", () => {
    render(
      <ControlActionBar
        quoteId="q-1"
        userId="user-1"
        workflowStatus="pending_quote_control"
        needsApproval={false}
      />,
    );

    const button = screen.getByRole("button", { name: /Validation Excel/ });
    expect((button as HTMLButtonElement).disabled).toBe(false);
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
      />,
    );

    expect(
      screen.queryByRole("button", { name: /Validation Excel/ }),
    ).toBeNull();
  });
});
