/**
 * Unit tests for the Срочность bucketing helper. Pins:
 *  - `overdue` matches anything strictly before `now`
 *  - `le_*` upcoming windows are inclusive of the threshold, exclusive of
 *    past deadlines (don't double-count overdue cards)
 *  - Missing / unparsable deadlines never match a positive bucket pick
 */

import { describe, expect, it } from "vitest";

import { isInUrgencyBucket, URGENCY_OPTIONS } from "../urgency";

const NOW = new Date("2026-05-24T12:00:00Z");

function plus(ms: number): string {
  return new Date(NOW.getTime() + ms).toISOString();
}

const HOUR = 60 * 60 * 1000;
const DAY = 24 * HOUR;

describe("isInUrgencyBucket — overdue", () => {
  it("matches deadlines in the past", () => {
    expect(isInUrgencyBucket(plus(-HOUR), "overdue", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(-30 * DAY), "overdue", NOW)).toBe(true);
  });

  it("excludes future deadlines", () => {
    expect(isInUrgencyBucket(plus(HOUR), "overdue", NOW)).toBe(false);
    expect(isInUrgencyBucket(plus(DAY), "overdue", NOW)).toBe(false);
  });
});

describe("isInUrgencyBucket — upcoming windows", () => {
  it("le_1d: includes deadlines within 24h, excludes past + 25h+", () => {
    expect(isInUrgencyBucket(plus(HOUR), "le_1d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(DAY), "le_1d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(25 * HOUR), "le_1d", NOW)).toBe(false);
    expect(isInUrgencyBucket(plus(-HOUR), "le_1d", NOW)).toBe(false);
  });

  it("le_3d: includes anything 0..3d ahead", () => {
    expect(isInUrgencyBucket(plus(2 * DAY), "le_3d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(3 * DAY), "le_3d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(3 * DAY + HOUR), "le_3d", NOW)).toBe(false);
  });

  it("le_7d: includes anything 0..7d ahead", () => {
    expect(isInUrgencyBucket(plus(5 * DAY), "le_7d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(7 * DAY), "le_7d", NOW)).toBe(true);
    expect(isInUrgencyBucket(plus(8 * DAY), "le_7d", NOW)).toBe(false);
  });
});

describe("isInUrgencyBucket — edge cases", () => {
  it("returns false when the deadline is missing", () => {
    expect(isInUrgencyBucket(null, "overdue", NOW)).toBe(false);
    expect(isInUrgencyBucket(undefined, "le_1d", NOW)).toBe(false);
  });

  it("returns false for unparsable input", () => {
    expect(isInUrgencyBucket("not-a-date", "overdue", NOW)).toBe(false);
  });
});

describe("URGENCY_OPTIONS", () => {
  it("exposes exactly the four buckets", () => {
    expect(URGENCY_OPTIONS.map((o) => o.value)).toEqual([
      "overdue",
      "le_1d",
      "le_3d",
      "le_7d",
    ]);
  });
});
