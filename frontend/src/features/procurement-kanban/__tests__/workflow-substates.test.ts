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
  it("exposes exactly 4 substatuses matching the backend enum", () => {
    expect(PROCUREMENT_SUBSTATUSES).toEqual([
      "distributing",
      "searching_supplier",
      "waiting_prices",
      "prices_ready",
    ]);
  });

  it("has a Russian label for every substatus", () => {
    for (const sub of PROCUREMENT_SUBSTATUSES) {
      expect(SUBSTATUS_LABELS_RU[sub]).toBeTruthy();
    }
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

  it("rejects skipping steps (e.g. distributing → waiting_prices)", () => {
    expect(isValidTransition("distributing", "waiting_prices")).toBe(false);
    expect(isValidTransition("distributing", "prices_ready")).toBe(false);
    expect(isValidTransition("prices_ready", "distributing")).toBe(false);
  });

  it("isProcurementSubstatus narrows unknown strings", () => {
    expect(isProcurementSubstatus("distributing")).toBe(true);
    expect(isProcurementSubstatus("prices_ready")).toBe(true);
    expect(isProcurementSubstatus("shipped")).toBe(false);
    expect(isProcurementSubstatus("")).toBe(false);
  });
});
