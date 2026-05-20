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
 * Post-fix: button is enabled (the component already early-returns if the
 * quote isn't in a control state, so when it renders it should be usable)
 * and opens `/export/validation/{quoteId}` (the Next.js proxy).
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

import { ControlActionBar } from "../control-action-bar";

afterEach(cleanup);

describe("ControlActionBar — Validation Excel button", () => {
  it("opens /export/validation/{quoteId} (not legacyAppUrl) when clicked", () => {
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

    expect(openSpy).toHaveBeenCalledTimes(1);
    expect(openSpy).toHaveBeenCalledWith("/export/validation/q-1", "_blank");
    expect(openSpy.mock.calls[0][0]).not.toMatch(/legacy|kvotaflow\.ru/);

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
