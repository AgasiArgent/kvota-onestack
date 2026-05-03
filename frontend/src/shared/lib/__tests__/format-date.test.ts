import { describe, it, expect } from "vitest";
import { formatChatListTimestamp } from "../format-date";

// Reference "now" pinned to 2026-05-03 14:00 Europe/Moscow (UTC+3 → 11:00 UTC)
const NOW = new Date("2026-05-03T11:00:00Z");

describe("formatChatListTimestamp", () => {
  it("returns empty string for null / undefined / empty input", () => {
    expect(formatChatListTimestamp(null, NOW)).toBe("");
    expect(formatChatListTimestamp(undefined, NOW)).toBe("");
    expect(formatChatListTimestamp("", NOW)).toBe("");
  });

  it("returns empty string for an invalid date string", () => {
    expect(formatChatListTimestamp("not-a-date", NOW)).toBe("");
  });

  it("renders today's messages as HH:mm in Europe/Moscow", () => {
    // 11:55 UTC = 14:55 Moscow on 2026-05-03 (same day as NOW)
    expect(formatChatListTimestamp("2026-05-03T11:55:00Z", NOW)).toBe("14:55");
  });

  it("renders yesterday's messages as 'вчера'", () => {
    expect(formatChatListTimestamp("2026-05-02T10:00:00Z", NOW)).toBe("вчера");
  });

  it("renders earlier-this-year messages as 'D MMM' (Russian)", () => {
    // 2026-04-29 → "29 апр." (toLocaleDateString returns short-month with dot)
    const out = formatChatListTimestamp("2026-04-29T11:55:00Z", NOW);
    expect(out).toMatch(/^29\s+апр/);
    expect(out).not.toContain("назад");
    expect(out).not.toContain("дн");
  });

  it("renders previous-year messages as DD.MM.YYYY", () => {
    expect(formatChatListTimestamp("2025-12-15T10:00:00Z", NOW)).toBe(
      "15.12.2025",
    );
  });

  it("never returns a relative phrase like 'только что' or '3 дн'", () => {
    // Several inputs that the legacy relative formatter would label "3 дн"
    const inputs = [
      "2026-04-30T08:00:00Z",
      "2026-04-29T08:00:00Z",
      "2026-05-03T10:59:30Z", // 30s ago — was "только что"
    ];
    for (const v of inputs) {
      const out = formatChatListTimestamp(v, NOW);
      expect(out).not.toContain("только что");
      expect(out).not.toContain("назад");
      expect(out).not.toMatch(/^\d+\s*(?:мин|ч|дн)$/);
    }
  });
});
