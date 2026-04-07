import { describe, it, expect } from "vitest";
import {
  isSalesOnly,
  isAssignedItemsOnly,
  isProcurementOnly,
} from "../roles";

describe("isSalesOnly", () => {
  it("returns true for sales-only user", () => {
    expect(isSalesOnly(["sales"])).toBe(true);
  });

  it("returns true for head_of_sales", () => {
    expect(isSalesOnly(["head_of_sales"])).toBe(true);
  });

  it("returns true for sales + head_of_sales combo", () => {
    expect(isSalesOnly(["sales", "head_of_sales"])).toBe(true);
  });

  it("returns false for admin", () => {
    expect(isSalesOnly(["admin"])).toBe(false);
  });

  it("returns false for sales + admin combo", () => {
    expect(isSalesOnly(["sales", "admin"])).toBe(false);
  });

  it("returns false for procurement", () => {
    expect(isSalesOnly(["procurement"])).toBe(false);
  });

  it("returns false for empty roles", () => {
    expect(isSalesOnly([])).toBe(false);
  });
});

describe("isAssignedItemsOnly", () => {
  // --- Should return TRUE (restricted visibility) ---

  it("returns true for procurement-only user", () => {
    expect(isAssignedItemsOnly(["procurement"])).toBe(true);
  });

  it("returns true for logistics-only user", () => {
    expect(isAssignedItemsOnly(["logistics"])).toBe(true);
  });

  it("returns true for customs-only user", () => {
    expect(isAssignedItemsOnly(["customs"])).toBe(true);
  });

  it("returns true for procurement + logistics combo", () => {
    expect(isAssignedItemsOnly(["procurement", "logistics"])).toBe(true);
  });

  it("returns true for all three operational roles", () => {
    expect(isAssignedItemsOnly(["procurement", "logistics", "customs"])).toBe(
      true
    );
  });

  // --- Should return FALSE (broader access via other role) ---

  it("returns false for admin", () => {
    expect(isAssignedItemsOnly(["admin"])).toBe(false);
  });

  it("returns false for procurement + admin combo", () => {
    expect(isAssignedItemsOnly(["procurement", "admin"])).toBe(false);
  });

  it("returns false for head_of_procurement (sees all quotes)", () => {
    expect(isAssignedItemsOnly(["head_of_procurement"])).toBe(false);
  });

  it("returns false for procurement_senior (broader procurement access)", () => {
    expect(isAssignedItemsOnly(["procurement_senior"])).toBe(false);
  });

  it("returns false for procurement + sales combo (sales grants broader access)", () => {
    expect(isAssignedItemsOnly(["procurement", "sales"])).toBe(false);
  });

  it("returns false for logistics + quote_controller combo", () => {
    expect(isAssignedItemsOnly(["logistics", "quote_controller"])).toBe(false);
  });

  it("returns false for customs + finance combo", () => {
    expect(isAssignedItemsOnly(["customs", "finance"])).toBe(false);
  });

  it("returns false for top_manager", () => {
    expect(isAssignedItemsOnly(["top_manager"])).toBe(false);
  });

  it("returns false for empty roles", () => {
    expect(isAssignedItemsOnly([])).toBe(false);
  });

  it("returns false for sales-only user (handled by isSalesOnly)", () => {
    expect(isAssignedItemsOnly(["sales"])).toBe(false);
  });

  it("returns false for head_of_sales", () => {
    expect(isAssignedItemsOnly(["head_of_sales"])).toBe(false);
  });
});

describe("isProcurementOnly", () => {
  it("returns true for procurement-only user", () => {
    expect(isProcurementOnly(["procurement"])).toBe(true);
  });

  it("returns false for procurement + admin", () => {
    expect(isProcurementOnly(["procurement", "admin"])).toBe(false);
  });

  it("returns false for sales", () => {
    expect(isProcurementOnly(["sales"])).toBe(false);
  });
});

describe("role tier mutual exclusivity", () => {
  it("isSalesOnly and isAssignedItemsOnly never both return true", () => {
    const allRoles = [
      "admin",
      "top_manager",
      "sales",
      "head_of_sales",
      "procurement",
      "head_of_procurement",
      "procurement_senior",
      "logistics",
      "customs",
      "quote_controller",
      "spec_controller",
      "finance",
      "head_of_logistics",
    ];

    // Test all single roles
    for (const role of allRoles) {
      const roles = [role];
      const sales = isSalesOnly(roles);
      const assigned = isAssignedItemsOnly(roles);
      expect(
        sales && assigned,
        `Role [${role}] matched both isSalesOnly and isAssignedItemsOnly`
      ).toBe(false);
    }

    // Test common multi-role combos
    const combos = [
      ["sales", "procurement"],
      ["sales", "logistics"],
      ["head_of_sales", "customs"],
      ["procurement", "logistics"],
      ["procurement", "customs"],
    ];
    for (const roles of combos) {
      const sales = isSalesOnly(roles);
      const assigned = isAssignedItemsOnly(roles);
      expect(
        sales && assigned,
        `Roles [${roles.join(",")}] matched both`
      ).toBe(false);
    }
  });
});
