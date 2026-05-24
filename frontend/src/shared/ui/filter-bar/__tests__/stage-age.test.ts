/**
 * Unit tests for the «На этапе > N дней» bucketing helper. Pins:
 *  - Strict > comparison (gt_7 excludes day 7, includes day 8)
 *  - NaN / Infinity input never matches a positive bucket
 */

import { describe, expect, it } from "vitest";

import { isInStageAgeBucket, STAGE_AGE_OPTIONS } from "../stage-age";

describe("isInStageAgeBucket", () => {
  it("gt_7: 8+ days passes, 7 does not", () => {
    expect(isInStageAgeBucket(8, "gt_7")).toBe(true);
    expect(isInStageAgeBucket(7, "gt_7")).toBe(false);
    expect(isInStageAgeBucket(0, "gt_7")).toBe(false);
  });

  it("gt_14: 15+ days passes, 14 does not", () => {
    expect(isInStageAgeBucket(15, "gt_14")).toBe(true);
    expect(isInStageAgeBucket(14, "gt_14")).toBe(false);
  });

  it("gt_30: 31+ days passes, 30 does not", () => {
    expect(isInStageAgeBucket(31, "gt_30")).toBe(true);
    expect(isInStageAgeBucket(30, "gt_30")).toBe(false);
  });

  it("returns false for non-finite input", () => {
    expect(isInStageAgeBucket(Number.NaN, "gt_7")).toBe(false);
    expect(isInStageAgeBucket(Number.POSITIVE_INFINITY, "gt_7")).toBe(false);
  });
});

describe("STAGE_AGE_OPTIONS", () => {
  it("exposes the three buckets in ascending order", () => {
    expect(STAGE_AGE_OPTIONS.map((o) => o.value)).toEqual([
      "gt_7",
      "gt_14",
      "gt_30",
    ]);
  });
});
