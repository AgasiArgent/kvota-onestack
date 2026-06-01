import { describe, expect, it } from "vitest";

import {
  deriveUserDepartments,
  isTrainingMaterialVisible,
} from "../roles";

/**
 * Testing 2 row 54 — training material access split by department AND role.
 *
 * A material is visible when its visibility allow-lists are empty (visible to
 * everyone) OR the viewer's department is in `visible_departments` OR one of
 * the viewer's role slugs is in `visible_role_slugs` (union of the lists).
 */

describe("deriveUserDepartments", () => {
  it("maps sales roles to the sales department", () => {
    expect(deriveUserDepartments(["sales"])).toEqual(["sales"]);
    expect(deriveUserDepartments(["head_of_sales"])).toEqual(["sales"]);
  });

  it("maps all procurement-tier roles to the procurement department", () => {
    expect(deriveUserDepartments(["procurement"])).toEqual(["procurement"]);
    expect(deriveUserDepartments(["procurement_senior"])).toEqual([
      "procurement",
    ]);
    expect(deriveUserDepartments(["head_of_procurement"])).toEqual([
      "procurement",
    ]);
  });

  it("maps logistics / customs / finance / management roles", () => {
    expect(deriveUserDepartments(["logistics"])).toEqual(["logistics"]);
    expect(deriveUserDepartments(["customs"])).toEqual(["customs"]);
    expect(deriveUserDepartments(["finance"])).toEqual(["finance"]);
    expect(deriveUserDepartments(["admin"])).toEqual(["management"]);
    expect(deriveUserDepartments(["top_manager"])).toEqual(["management"]);
  });

  it("returns multiple departments for multi-role users (deduped, ordered)", () => {
    expect(deriveUserDepartments(["sales", "logistics"])).toEqual([
      "sales",
      "logistics",
    ]);
  });

  it("returns no department for cross-cutting roles with no mapping", () => {
    expect(deriveUserDepartments(["quote_controller"])).toEqual([]);
    expect(deriveUserDepartments(["spec_controller"])).toEqual([]);
    expect(deriveUserDepartments(["newbie"])).toEqual([]);
    expect(deriveUserDepartments([])).toEqual([]);
  });
});

describe("isTrainingMaterialVisible", () => {
  it("shows unrestricted material (both lists empty) to everyone", () => {
    expect(isTrainingMaterialVisible([], [], ["sales"])).toBe(true);
    expect(isTrainingMaterialVisible([], [], ["logistics"])).toBe(true);
    expect(isTrainingMaterialVisible([], [], [])).toBe(true);
  });

  it("shows a department-restricted material to matching department users", () => {
    expect(isTrainingMaterialVisible(["sales"], [], ["sales"])).toBe(true);
    // head_of_sales is in the sales department
    expect(isTrainingMaterialVisible(["sales"], [], ["head_of_sales"])).toBe(
      true,
    );
  });

  it("hides a department-restricted material from non-matching users", () => {
    expect(isTrainingMaterialVisible(["sales"], [], ["logistics"])).toBe(false);
    expect(isTrainingMaterialVisible(["customs"], [], ["procurement"])).toBe(
      false,
    );
  });

  it("shows a role-restricted material only to the exact role", () => {
    expect(
      isTrainingMaterialVisible([], ["procurement_senior"], ["procurement_senior"]),
    ).toBe(true);
    // a plain procurement МОЗ is NOT procurement_senior → hidden
    expect(
      isTrainingMaterialVisible([], ["procurement_senior"], ["procurement"]),
    ).toBe(false);
  });

  it("uses union semantics — match by department OR role", () => {
    // restricted to sales department + the customs role; a customs user
    // matches via the role list even though their department differs
    expect(
      isTrainingMaterialVisible(["sales"], ["customs"], ["customs"]),
    ).toBe(true);
    // a logistics user matches neither → hidden
    expect(
      isTrainingMaterialVisible(["sales"], ["customs"], ["logistics"]),
    ).toBe(false);
  });

  it("hides any restricted material from a user with no roles", () => {
    expect(isTrainingMaterialVisible(["sales"], [], [])).toBe(false);
    expect(isTrainingMaterialVisible([], ["sales"], [])).toBe(false);
  });
});
