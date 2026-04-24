/**
 * Unit tests for the pure helpers backing `useFlowState`. The hook itself
 * is exercised via integration testing at the `<FlowView />` level — here
 * we only verify the deterministic primitives.
 */

import { describe, it, expect } from "vitest";
import { clampStepIndex, resolveKeyAction } from "../use-flow-state";

describe("clampStepIndex", () => {
  it("clamps above the upper bound", () => {
    expect(clampStepIndex(5, 3)).toBe(2);
  });

  it("clamps below zero", () => {
    expect(clampStepIndex(-1, 3)).toBe(0);
  });

  it("returns 0 when stepCount is zero", () => {
    expect(clampStepIndex(0, 0)).toBe(0);
    expect(clampStepIndex(7, 0)).toBe(0);
  });

  it("passes through valid indices", () => {
    expect(clampStepIndex(0, 5)).toBe(0);
    expect(clampStepIndex(2, 5)).toBe(2);
    expect(clampStepIndex(4, 5)).toBe(4);
  });
});

describe("resolveKeyAction", () => {
  it("maps ArrowRight to next", () => {
    expect(resolveKeyAction("ArrowRight")).toBe("next");
  });

  it("maps ArrowLeft to prev", () => {
    expect(resolveKeyAction("ArrowLeft")).toBe("prev");
  });

  it("maps Escape to exit", () => {
    expect(resolveKeyAction("Escape")).toBe("exit");
  });

  it("returns null for unbound keys", () => {
    expect(resolveKeyAction("Tab")).toBeNull();
    expect(resolveKeyAction("Enter")).toBeNull();
    expect(resolveKeyAction(" ")).toBeNull();
    expect(resolveKeyAction("a")).toBeNull();
  });
});
