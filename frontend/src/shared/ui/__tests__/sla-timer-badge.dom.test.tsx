// @vitest-environment jsdom
/**
 * SlaTimerBadge — REQ-4 timer fallback for unassigned kanban cards.
 *
 * An unassigned invoice has a NULL `{domain}_deadline_at` (the deadline is
 * stamped only on assignment). The badge must still render a *running* timer
 * counting from the stage-entry timestamp — `elapsed` state, no overdue
 * styling. Previously a missing deadline rendered an inert "—" placeholder.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SlaTimerBadge } from "../sla-timer-badge";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("SlaTimerBadge — null deadline (REQ-4 unassigned cards)", () => {
  it("renders a running elapsed timer when deadlineAt is null", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T12:00:00Z"));
    // Stage entry 3 hours ago.
    render(
      <SlaTimerBadge
        assignedAt="2026-05-15T09:00:00Z"
        deadlineAt={null}
      />,
    );
    expect(screen.getByText(/в работе/i)).toBeTruthy();
    expect(screen.getByText(/3 часа в работе/i)).toBeTruthy();
  });

  it("does not render the overdue placeholder when only the deadline is null", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T12:00:00Z"));
    render(
      <SlaTimerBadge
        assignedAt="2026-05-13T12:00:00Z"
        deadlineAt={null}
      />,
    );
    // 2 days since stage entry — elapsed, never "просрочено".
    expect(screen.getByText(/2 дня в работе/i)).toBeTruthy();
    expect(screen.queryByText(/просрочено/i)).toBeNull();
  });

  it("falls back to the inert placeholder only when BOTH timestamps are absent", () => {
    render(
      <SlaTimerBadge
        assignedAt={null as unknown as string}
        deadlineAt={null}
      />,
    );
    expect(screen.getByText("—")).toBeTruthy();
  });

  it("still renders a deadline countdown when deadlineAt is set", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-15T12:00:00Z"));
    // Deadline 5 hours out — assigned card keeps the normal SLA countdown.
    render(
      <SlaTimerBadge
        assignedAt="2026-05-15T09:00:00Z"
        deadlineAt="2026-05-15T17:00:00Z"
      />,
    );
    expect(screen.getByText(/осталось/i)).toBeTruthy();
  });

  it("shows «Завершено» when completedAt is set, regardless of deadline", () => {
    render(
      <SlaTimerBadge
        assignedAt="2026-05-15T09:00:00Z"
        deadlineAt={null}
        completedAt="2026-05-15T11:00:00Z"
      />,
    );
    expect(screen.getByText("Завершено")).toBeTruthy();
  });
});
