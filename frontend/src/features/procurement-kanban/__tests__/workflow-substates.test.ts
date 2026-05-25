import { describe, it, expect } from "vitest";
import {
  PROCUREMENT_SUBSTATUSES,
  SUBSTATUS_LABELS_RU,
  FORWARD_TRANSITIONS,
  BACKWARD_TRANSITIONS,
  isBackwardTransition,
  isValidTransition,
  isProcurementSubstatus,
} from "@/shared/lib/workflow-substates";

describe("workflow-substates", () => {
  it("exposes exactly 5 substatuses matching the backend check constraint", () => {
    expect(PROCUREMENT_SUBSTATUSES).toEqual([
      "distributing",
      "searching_supplier",
      "waiting_prices",
      "prices_ready",
      "paused",
    ]);
  });

  it("places 'paused' at the end so the linear active flow is unchanged", () => {
    expect(PROCUREMENT_SUBSTATUSES.at(-1)).toBe("paused");
  });

  it("has a Russian label for every substatus", () => {
    for (const sub of PROCUREMENT_SUBSTATUSES) {
      expect(SUBSTATUS_LABELS_RU[sub]).toBeTruthy();
    }
  });

  it("labels 'paused' as «На паузе»", () => {
    expect(SUBSTATUS_LABELS_RU.paused).toBe("На паузе");
  });

  it("marks all forward moves as valid and non-backward", () => {
    for (const [from, to] of FORWARD_TRANSITIONS) {
      expect(isValidTransition(from, to)).toBe(true);
      expect(isBackwardTransition(from, to)).toBe(false);
    }
  });

  it("marks all backward moves as valid and backward", () => {
    for (const [from, to] of BACKWARD_TRANSITIONS) {
      expect(isValidTransition(from, to)).toBe(true);
      expect(isBackwardTransition(from, to)).toBe(true);
    }
  });

  it("rejects same-column moves", () => {
    for (const sub of PROCUREMENT_SUBSTATUSES) {
      expect(isValidTransition(sub, sub)).toBe(false);
    }
  });

  it("rejects skipping steps within the active flow", () => {
    // Pause-aside, you still can't skip from distributing straight to
    // waiting_prices or prices_ready in the linear active path.
    expect(isValidTransition("distributing", "waiting_prices")).toBe(false);
    expect(isValidTransition("distributing", "prices_ready")).toBe(false);
    expect(isValidTransition("prices_ready", "distributing")).toBe(false);
  });

  it("allows pausing from any active column (forward, no reason)", () => {
    const activeStatuses = [
      "distributing",
      "searching_supplier",
      "waiting_prices",
      "prices_ready",
    ] as const;
    for (const sub of activeStatuses) {
      expect(isValidTransition(sub, "paused")).toBe(true);
      expect(isBackwardTransition(sub, "paused")).toBe(false);
    }
  });

  it("allows resuming from paused to any active column (forward, no reason)", () => {
    const activeStatuses = [
      "distributing",
      "searching_supplier",
      "waiting_prices",
      "prices_ready",
    ] as const;
    for (const sub of activeStatuses) {
      expect(isValidTransition("paused", sub)).toBe(true);
      expect(isBackwardTransition("paused", sub)).toBe(false);
    }
  });

  it("isProcurementSubstatus narrows unknown strings", () => {
    expect(isProcurementSubstatus("distributing")).toBe(true);
    expect(isProcurementSubstatus("prices_ready")).toBe(true);
    expect(isProcurementSubstatus("paused")).toBe(true);
    expect(isProcurementSubstatus("shipped")).toBe(false);
    expect(isProcurementSubstatus("")).toBe(false);
  });
});
