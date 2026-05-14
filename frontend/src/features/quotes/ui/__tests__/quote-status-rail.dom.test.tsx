// @vitest-environment jsdom
/**
 * Testing 2 row 11 (part 1) — per-stage completion within the combined
 * `pending_logistics_and_customs` workflow stage.
 *
 * Tester report: while the quote is in the combined Logistics + Customs
 * stage, both rail steps render as "current" (filled accent circle). The
 * customs side should flip to a green check ✓ as soon as it's marked
 * done, even if logistics is still pending (and vice-versa) — otherwise
 * users see no progress until BOTH sub-stages complete.
 *
 * The fix wires `logistics_completed_at` / `customs_completed_at` from
 * the quote into the rail. When `workflowStatus ===
 * "pending_logistics_and_customs"` AND the per-step timestamp is set,
 * that step renders with the green Check icon (isCompleted = true) and
 * the other side stays "current".
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mocks (must come before component import — vitest hoists vi.mock)
// ---------------------------------------------------------------------------

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: () => {},
    push: () => {},
    replace: () => {},
    back: () => {},
    forward: () => {},
    prefetch: () => {},
  }),
}));

// StageTimerBadge + DeadlineOverride aren't relevant for icon assertions
// and pull in extra deps; stub them to keep the test focused.
vi.mock("../stage-timer-badge", () => ({
  StageTimerBadge: () => null,
}));
vi.mock("../deadline-override", () => ({
  DeadlineOverride: () => null,
}));

import { QuoteStatusRail } from "../quote-status-rail";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const baseProps = {
  activeStep: "logistics" as const,
  currentWorkflowStep: "logistics" as const,
  allowedSteps: ["sales", "procurement", "logistics", "customs", "calculation"] as const,
  isAdmin: true,
  quoteId: "q-1",
  stageDeadline: {
    stageEnteredAt: null,
    deadlineHours: null,
    overrideHours: null,
  },
};

/**
 * Lucide renders each icon as an `<svg class="lucide lucide-{name} ...">`.
 * To assert which icon a rail step is showing, we grab the button by its
 * accessible label (the step's Russian title) and inspect the first SVG
 * inside it.
 */
function getStepIconClass(label: RegExp): string {
  const button = screen.getByRole("button", { name: label });
  const svg = button.querySelector("svg");
  if (!svg) throw new Error(`No icon found inside step button matching ${label}`);
  return svg.getAttribute("class") ?? "";
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("QuoteStatusRail — partial completion within pending_logistics_and_customs", () => {
  afterEach(() => {
    cleanup();
  });

  it("marks Customs as ✓ green when customs_completed_at is set but logistics is not", () => {
    render(
      <QuoteStatusRail
        {...baseProps}
        // typed as readonly tuple — cast to mutable for prop
        allowedSteps={[...baseProps.allowedSteps]}
        workflowStatus="pending_logistics_and_customs"
        customsCompletedAt="2026-05-14T12:00:00Z"
        logisticsCompletedAt={null}
      />,
    );

    // Customs → completed (Check icon, green)
    const customsClass = getStepIconClass(/Таможня/);
    expect(customsClass).toMatch(/lucide-check/);
    expect(customsClass).toMatch(/text-green-600/);

    // Logistics → still current (Circle filled with accent)
    const logisticsClass = getStepIconClass(/Логистика/);
    expect(logisticsClass).toMatch(/lucide-circle/);
    expect(logisticsClass).toMatch(/fill-accent/);
  });

  it("marks Logistics as ✓ green when logistics_completed_at is set but customs is not", () => {
    render(
      <QuoteStatusRail
        {...baseProps}
        allowedSteps={[...baseProps.allowedSteps]}
        workflowStatus="pending_logistics_and_customs"
        customsCompletedAt={null}
        logisticsCompletedAt="2026-05-14T12:00:00Z"
      />,
    );

    const logisticsClass = getStepIconClass(/Логистика/);
    expect(logisticsClass).toMatch(/lucide-check/);
    expect(logisticsClass).toMatch(/text-green-600/);

    const customsClass = getStepIconClass(/Таможня/);
    expect(customsClass).toMatch(/lucide-circle/);
    expect(customsClass).toMatch(/fill-accent/);
  });

  it("marks BOTH Logistics and Customs as ✓ green when both timestamps are set", () => {
    render(
      <QuoteStatusRail
        {...baseProps}
        allowedSteps={[...baseProps.allowedSteps]}
        workflowStatus="pending_logistics_and_customs"
        customsCompletedAt="2026-05-14T12:00:00Z"
        logisticsCompletedAt="2026-05-14T11:00:00Z"
      />,
    );

    expect(getStepIconClass(/Логистика/)).toMatch(/lucide-check/);
    expect(getStepIconClass(/Таможня/)).toMatch(/lucide-check/);
  });

  it("keeps both as 'current' (filled accent circle) when neither timestamp is set", () => {
    render(
      <QuoteStatusRail
        {...baseProps}
        allowedSteps={[...baseProps.allowedSteps]}
        workflowStatus="pending_logistics_and_customs"
        customsCompletedAt={null}
        logisticsCompletedAt={null}
      />,
    );

    const logisticsClass = getStepIconClass(/Логистика/);
    expect(logisticsClass).toMatch(/lucide-circle/);
    expect(logisticsClass).toMatch(/fill-accent/);

    const customsClass = getStepIconClass(/Таможня/);
    expect(customsClass).toMatch(/lucide-circle/);
    expect(customsClass).toMatch(/fill-accent/);
  });

  it("does NOT apply partial completion logic outside pending_logistics_and_customs", () => {
    // Even if timestamps are set, a different workflow status should not
    // be affected by the new partial-completion branch. With status
    // `pending_logistics`, customs is NOT yet current at all, so the
    // customs_completed_at timestamp must not flip it green prematurely.
    render(
      <QuoteStatusRail
        {...baseProps}
        allowedSteps={[...baseProps.allowedSteps]}
        workflowStatus="pending_logistics"
        customsCompletedAt="2026-05-14T12:00:00Z"
        logisticsCompletedAt={null}
      />,
    );

    // Customs should remain pending (empty border circle), not green check.
    const customsClass = getStepIconClass(/Таможня/);
    expect(customsClass).toMatch(/lucide-circle/);
    expect(customsClass).not.toMatch(/text-green-600/);
  });
});
