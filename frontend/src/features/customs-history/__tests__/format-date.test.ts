import { describe, it, expect } from "vitest";

import { formatDateRussian } from "../lib/format-date";

/**
 * Pure-function tests for the customs-history date helper (Phase A Req 10).
 *
 * The helper is consumed by the HistoryBanner's headline copy and by the
 * inline `📅 DD.MM.YYYY` badges next to auto-applied fields in
 * customs-item-dialog. Output convention is the project-wide ru-RU
 * DD.MM.YYYY format.
 */

describe("formatDateRussian", () => {
  it("formats an ISO timestamp as DD.MM.YYYY", () => {
    expect(formatDateRussian("2026-04-23T15:30:00Z")).toMatch(
      /^\d{2}\.\d{2}\.2026$/,
    );
  });

  it("zero-pads single-digit day and month", () => {
    // Use a UTC timestamp at noon to avoid TZ shifting the day for
    // negative-offset CI runners.
    const out = formatDateRussian("2026-03-05T12:00:00Z");
    expect(out).toMatch(/^05\.03\.2026$/);
  });

  it("returns empty string for null input", () => {
    expect(formatDateRussian(null)).toBe("");
  });

  it("returns empty string for undefined input", () => {
    expect(formatDateRussian(undefined)).toBe("");
  });

  it("returns empty string for invalid ISO string", () => {
    expect(formatDateRussian("not-a-date")).toBe("");
  });

  it("returns empty string for empty string", () => {
    expect(formatDateRussian("")).toBe("");
  });

  it("uses dots as separators (not slashes or dashes)", () => {
    const out = formatDateRussian("2026-04-23T12:00:00Z");
    expect(out).toContain(".");
    expect(out).not.toContain("/");
    expect(out).not.toContain("-");
  });
});
