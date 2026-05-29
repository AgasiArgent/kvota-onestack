import { describe, it, expect } from "vitest";
import { effectiveQuantity, isMoqViolation } from "../moq-warning";

describe("isMoqViolation", () => {
  it("returns false when min_order_quantity is null", () => {
    expect(
      isMoqViolation({ quantity: 10, min_order_quantity: null })
    ).toBe(false);
  });

  it("returns false when quantity is null", () => {
    expect(
      isMoqViolation({ quantity: null, min_order_quantity: 15 })
    ).toBe(false);
  });

  it("returns false when quantity equals min_order_quantity", () => {
    expect(
      isMoqViolation({ quantity: 10, min_order_quantity: 10 })
    ).toBe(false);
  });

  it("returns false when quantity is above min_order_quantity", () => {
    expect(
      isMoqViolation({ quantity: 20, min_order_quantity: 10 })
    ).toBe(false);
  });

  it("returns true when quantity is below min_order_quantity", () => {
    expect(
      isMoqViolation({ quantity: 5, min_order_quantity: 10 })
    ).toBe(true);
  });

  it("returns false when both values are null", () => {
    expect(
      isMoqViolation({ quantity: null, min_order_quantity: null })
    ).toBe(false);
  });
});

describe("effectiveQuantity", () => {
  it("rounds ordered up to the MOQ when MOQ is higher", () => {
    expect(effectiveQuantity(5, 10)).toBe(10);
  });

  it("returns ordered when MOQ is below ordered", () => {
    expect(effectiveQuantity(10, 5)).toBe(10);
  });

  it("returns ordered when MOQ equals ordered", () => {
    expect(effectiveQuantity(10, 10)).toBe(10);
  });

  it("returns ordered when MOQ is null", () => {
    expect(effectiveQuantity(5, null)).toBe(5);
  });

  it("returns ordered when MOQ is zero", () => {
    expect(effectiveQuantity(5, 0)).toBe(5);
  });

  it("returns ordered when MOQ is negative", () => {
    expect(effectiveQuantity(5, -3)).toBe(5);
  });

  it("treats null ordered as 0 and binds to a positive MOQ", () => {
    expect(effectiveQuantity(null, 10)).toBe(10);
  });

  it("returns 0 when both are null/absent", () => {
    expect(effectiveQuantity(null, null)).toBe(0);
  });
});
