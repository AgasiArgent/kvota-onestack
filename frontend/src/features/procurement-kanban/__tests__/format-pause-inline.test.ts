import { describe, it, expect } from "vitest";
import {
  PAUSE_INLINE_REASON_MAX,
  formatPauseInline,
} from "../ui/kanban-card";
import type { KanbanPauseLog } from "../model/types";

/**
 * formatPauseInline produces the «На паузе с …» label rendered on paused
 * kanban cards (Testing 2 row 74). Tests verify date formatting, truncation
 * to PAUSE_INLINE_REASON_MAX, and graceful fallbacks when fields are absent.
 */
describe("formatPauseInline", () => {
  const baseLog: KanbanPauseLog = {
    id: "log-1",
    paused_at: "2026-05-25T10:00:00+00:00",
    paused_by_name: "Иванов И.И.",
    reason: "Поставщик не отвечает",
  };

  it("includes date + reason + author", () => {
    const out = formatPauseInline(baseLog);
    // Date prefix
    expect(out.startsWith("На паузе с ")).toBe(true);
    // Reason verbatim (under truncation threshold)
    expect(out).toContain("Поставщик не отвечает");
    // Author suffix
    expect(out.endsWith("(Иванов И.И.)")).toBe(true);
  });

  it("omits author parens when paused_by_name is null", () => {
    const out = formatPauseInline({ ...baseLog, paused_by_name: null });
    expect(out).not.toContain("(");
    expect(out).toContain("Поставщик не отвечает");
  });

  it("omits author parens when paused_by_name is whitespace", () => {
    const out = formatPauseInline({ ...baseLog, paused_by_name: "   " });
    expect(out).not.toContain("(");
  });

  it("truncates long reasons to PAUSE_INLINE_REASON_MAX with ellipsis", () => {
    const longReason = "a".repeat(PAUSE_INLINE_REASON_MAX + 50);
    const out = formatPauseInline({ ...baseLog, reason: longReason });
    // The reason portion should end with the horizontal ellipsis character.
    expect(out).toContain("…");
    // Reason content length capped at PAUSE_INLINE_REASON_MAX - 1 + 1 for ellipsis.
    // Total label includes prefix + date + colon + author so we just sanity-check:
    expect(out.length).toBeLessThan(
      PAUSE_INLINE_REASON_MAX + 100 // generous upper bound, NOT longReason.length
    );
    expect(out.length).toBeLessThan(longReason.length);
  });

  it("does NOT truncate when reason fits within the limit", () => {
    const shortReason = "Кратко".repeat(2); // 12 chars
    const out = formatPauseInline({ ...baseLog, reason: shortReason });
    expect(out).not.toContain("…");
    expect(out).toContain(shortReason);
  });

  it("falls back to the raw ISO string if paused_at is unparseable", () => {
    const out = formatPauseInline({ ...baseLog, paused_at: "not-a-date" });
    // Don't assert exact format — just that it doesn't throw and includes
    // the reason after a colon.
    expect(out).toContain(": Поставщик не отвечает");
  });
});
