import { describe, it, expect } from "vitest";

import { intersectSupplierIdConstraints } from "../filter-supplier-ids";

/**
 * Testing 2 row 92 — /suppliers Бренд + МОЗ filters resolve to supplier-id
 * sets which must combine with AND semantics (and with the role-based
 * visibility scope). This pins the intersection contract that decides which
 * IDs survive to the `.in("id", …)` clause.
 */
describe("intersectSupplierIdConstraints", () => {
  it("returns null when no constraint is applied (no .in() filter)", () => {
    expect(intersectSupplierIdConstraints([null, null, null])).toBeNull();
  });

  it("returns the single constraint unchanged when only one applies", () => {
    const result = intersectSupplierIdConstraints([null, ["a", "b"], null]);
    expect(result).not.toBeNull();
    expect(new Set(result!)).toEqual(new Set(["a", "b"]));
  });

  it("intersects two constraints (AND) — only IDs in BOTH survive", () => {
    const result = intersectSupplierIdConstraints([
      ["a", "b", "c"],
      ["b", "c", "d"],
    ]);
    expect(new Set(result!)).toEqual(new Set(["b", "c"]));
  });

  it("intersects three constraints — role + brand + assignee", () => {
    const result = intersectSupplierIdConstraints([
      ["a", "b", "c"], // role visibility
      ["b", "c"], // brand
      ["c", "d"], // assignee
    ]);
    expect(result).toEqual(["c"]);
  });

  it("yields an empty array (zero rows) when the intersection is empty", () => {
    const result = intersectSupplierIdConstraints([["a"], ["b"]]);
    expect(result).toEqual([]);
  });

  it("an empty applied constraint forces zero rows (brand matched nothing)", () => {
    // A brand with no suppliers contributes [] — the result must be [], never
    // an unfiltered null, otherwise the filter would leak every supplier.
    const result = intersectSupplierIdConstraints([["a", "b"], []]);
    expect(result).toEqual([]);
  });

  it("skips null constraints but keeps an empty applied one", () => {
    expect(intersectSupplierIdConstraints([null, []])).toEqual([]);
  });
});
