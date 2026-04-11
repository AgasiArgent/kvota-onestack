import { describe, it, expect } from "vitest";
import { isMoqViolation } from "../moq-warning";

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
