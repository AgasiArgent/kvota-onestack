import { describe, it, expect } from "vitest";
import { effectiveQuantity } from "../effective-quantity";

describe("effectiveQuantity", () => {
  it("overrides up when supplier qty is higher", () => {
    expect(effectiveQuantity(5, 10)).toBe(10);
  });
  it("overrides DOWN when supplier qty is lower", () => {
    expect(effectiveQuantity(10, 5)).toBe(5);
  });
  it("equal", () => {
    expect(effectiveQuantity(10, 10)).toBe(10);
  });
  it("unset → ordered", () => {
    expect(effectiveQuantity(5, null)).toBe(5);
  });
  it("zero → ordered", () => {
    expect(effectiveQuantity(5, 0)).toBe(5);
  });
  it("negative → ordered", () => {
    expect(effectiveQuantity(5, -3)).toBe(5);
  });
  it("null ordered + set supplier qty → supplier qty", () => {
    expect(effectiveQuantity(null, 10)).toBe(10);
  });
});
