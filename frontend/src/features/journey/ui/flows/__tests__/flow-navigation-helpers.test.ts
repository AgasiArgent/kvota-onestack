/**
 * Unit tests for the remaining-minutes helper used by `<FlowNavigation />`.
 */

import { describe, it, expect } from "vitest";
import { formatRemainingMinutes } from "../flow-navigation-helpers";

describe("formatRemainingMinutes", () => {
  it("returns the full estimate at step 0", () => {
    // 12 total minutes, 6 steps, index 0 → 6 steps remaining → 12 min
    expect(formatRemainingMinutes(12, 0, 6)).toBe(12);
  });

  it("halves at the mid-point", () => {
    expect(formatRemainingMinutes(12, 3, 6)).toBe(6);
  });

  it("never drops below per-step estimate on the last step", () => {
    // 12 min / 6 steps = 2 min/step. Last step (index 5) → 1 step remaining → 2 min.
    expect(formatRemainingMinutes(12, 5, 6)).toBe(2);
  });

  it("returns 0 for empty flows", () => {
    expect(formatRemainingMinutes(0, 0, 0)).toBe(0);
    expect(formatRemainingMinutes(10, 0, 0)).toBe(0);
  });

  it("returns 0 when est_minutes is zero", () => {
    expect(formatRemainingMinutes(0, 0, 5)).toBe(0);
  });

  it("clamps negative indices to full estimate", () => {
    // stepIndex -1 means the user is before the first step; treat as full.
    expect(formatRemainingMinutes(10, -1, 5)).toBe(10);
  });
});
