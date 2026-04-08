import { describe, it, expect } from "vitest";
import {
  isSalesOnly,
  isAssignedItemsOnly,
  isProcurementOnly,
  isProcurementSeniorOnly,
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

describe("isProcurementSeniorOnly", () => {
  // --- Should return TRUE (procurement stage only) ---

  it("returns true for procurement_senior alone", () => {
    expect(isProcurementSeniorOnly(["procurement_senior"])).toBe(true);
  });

  it("returns true for procurement_senior + procurement combo (senior dominates)", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "procurement"])).toBe(true);
  });

  it("returns true for procurement_senior + logistics combo", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "logistics"])).toBe(true);
  });

  it("returns true for procurement_senior + customs combo", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "customs"])).toBe(true);
  });

  // --- Should return FALSE (broader role overrides) ---

  it("returns false for admin", () => {
    expect(isProcurementSeniorOnly(["admin"])).toBe(false);
  });

  it("returns false for procurement_senior + admin", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "admin"])).toBe(false);
  });

  it("returns false for procurement_senior + head_of_procurement", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "head_of_procurement"])).toBe(false);
  });

  it("returns false for procurement_senior + sales (mixed tier)", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "sales"])).toBe(false);
  });

  it("returns false for procurement_senior + top_manager", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "top_manager"])).toBe(false);
  });

  it("returns false for procurement_senior + finance", () => {
    expect(isProcurementSeniorOnly(["procurement_senior", "finance"])).toBe(false);
  });

  it("returns false for procurement without senior", () => {
    expect(isProcurementSeniorOnly(["procurement"])).toBe(false);
  });

  it("returns false for empty roles", () => {
    expect(isProcurementSeniorOnly([])).toBe(false);
  });
});

describe("role tier mutual exclusivity", () => {
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

  const multiRoleCombos = [
    ["sales", "procurement"],
    ["sales", "logistics"],
    ["head_of_sales", "customs"],
    ["procurement", "logistics"],
    ["procurement", "customs"],
    ["procurement_senior", "procurement"],
    ["procurement_senior", "sales"],
    ["procurement_senior", "admin"],
  ];

  it("isSalesOnly and isAssignedItemsOnly never both return true", () => {
    for (const role of allRoles) {
      const roles = [role];
      expect(
        isSalesOnly(roles) && isAssignedItemsOnly(roles),
        `Role [${role}] matched both isSalesOnly and isAssignedItemsOnly`
      ).toBe(false);
    }
    for (const roles of multiRoleCombos) {
      expect(
        isSalesOnly(roles) && isAssignedItemsOnly(roles),
        `Roles [${roles.join(",")}] matched both`
      ).toBe(false);
    }
  });

  it("isProcurementSeniorOnly and isSalesOnly never both return true", () => {
    for (const role of allRoles) {
      const roles = [role];
      expect(
        isProcurementSeniorOnly(roles) && isSalesOnly(roles),
        `Role [${role}] matched both isProcurementSeniorOnly and isSalesOnly`
      ).toBe(false);
    }
    for (const roles of multiRoleCombos) {
      expect(
        isProcurementSeniorOnly(roles) && isSalesOnly(roles),
        `Roles [${roles.join(",")}] matched both`
      ).toBe(false);
    }
  });

  it("isProcurementSeniorOnly and isAssignedItemsOnly never both return true", () => {
    for (const role of allRoles) {
      const roles = [role];
      expect(
        isProcurementSeniorOnly(roles) && isAssignedItemsOnly(roles),
        `Role [${role}] matched both isProcurementSeniorOnly and isAssignedItemsOnly`
      ).toBe(false);
    }
    for (const roles of multiRoleCombos) {
      expect(
        isProcurementSeniorOnly(roles) && isAssignedItemsOnly(roles),
        `Roles [${roles.join(",")}] matched both`
      ).toBe(false);
    }
  });

  it("at most one tier function returns true for any single role", () => {
    for (const role of allRoles) {
      const roles = [role];
      const matches = [
        isSalesOnly(roles) && "isSalesOnly",
        isAssignedItemsOnly(roles) && "isAssignedItemsOnly",
        isProcurementSeniorOnly(roles) && "isProcurementSeniorOnly",
      ].filter(Boolean);
      expect(
        matches.length,
        `Role [${role}] matched ${matches.length} tiers: ${matches.join(", ")}`
      ).toBeLessThanOrEqual(1);
    }
  });
});
