import { describe, expect, it } from "vitest";
import {
  isNewbieOnly,
  canAssignNewbie,
  filterAssignableRoles,
  NEWBIE_ASSIGNER_ROLES,
} from "../types";

/**
 * Testing 2 row 38p2 — guards for the `newbie` parking role.
 *
 * `isNewbieOnly` decides whether a user must be redirected to the
 * /awaiting-role placeholder. `canAssignNewbie` decides whether the
 * admin UI may expose the `newbie` option in role pickers. Both
 * underpin business rules pre-approved in
 * docs/plans/2026-05-24-product-decisions.md.
 */

describe("isNewbieOnly", () => {
  it("returns false for an empty roles list (no newbie at all)", () => {
    expect(isNewbieOnly([])).toBe(false);
  });

  it("returns false for a user with only functional roles", () => {
    expect(isNewbieOnly(["sales"])).toBe(false);
    expect(isNewbieOnly(["admin"])).toBe(false);
    expect(isNewbieOnly(["sales", "head_of_sales"])).toBe(false);
  });

  it("returns true when newbie is the only role", () => {
    expect(isNewbieOnly(["newbie"])).toBe(true);
  });

  it("returns false when newbie is combined with another role", () => {
    // Mixed assignment is treated as the functional role being active.
    expect(isNewbieOnly(["newbie", "sales"])).toBe(false);
    expect(isNewbieOnly(["procurement", "newbie"])).toBe(false);
  });

  it("returns true even when newbie appears multiple times", () => {
    // Defensive — duplicates can occur from a JOIN.
    expect(isNewbieOnly(["newbie", "newbie"])).toBe(true);
  });
});

describe("canAssignNewbie", () => {
  it("returns false for users without an assigner role", () => {
    expect(canAssignNewbie([])).toBe(false);
    expect(canAssignNewbie(["sales"])).toBe(false);
    expect(canAssignNewbie(["procurement"])).toBe(false);
    expect(canAssignNewbie(["top_manager"])).toBe(false);
  });

  it("returns true for admin", () => {
    expect(canAssignNewbie(["admin"])).toBe(true);
  });

  it("returns true for every head_of_* role", () => {
    expect(canAssignNewbie(["head_of_sales"])).toBe(true);
    expect(canAssignNewbie(["head_of_procurement"])).toBe(true);
    expect(canAssignNewbie(["head_of_logistics"])).toBe(true);
    expect(canAssignNewbie(["head_of_customs"])).toBe(true);
  });

  it("returns true when an assigner role is mixed with other roles", () => {
    expect(canAssignNewbie(["sales", "head_of_sales"])).toBe(true);
    expect(canAssignNewbie(["procurement", "admin"])).toBe(true);
  });

  it("locks the assigner allowlist to a stable set", () => {
    // Guards against accidental expansion. If the product decision
    // changes, update both the constant and this assertion.
    expect([...NEWBIE_ASSIGNER_ROLES].sort()).toEqual(
      [
        "admin",
        "head_of_customs",
        "head_of_logistics",
        "head_of_procurement",
        "head_of_sales",
      ].sort(),
    );
  });
});

describe("filterAssignableRoles", () => {
  const ROLES = [
    { slug: "admin" },
    { slug: "sales" },
    { slug: "head_of_sales" },
    { slug: "newbie" },
  ];

  it("hides `newbie` when the caller is not an assigner", () => {
    const filtered = filterAssignableRoles(ROLES, ["sales"]);
    expect(filtered.map((r) => r.slug)).toEqual(["admin", "sales", "head_of_sales"]);
  });

  it("keeps `newbie` visible when the caller is admin", () => {
    const filtered = filterAssignableRoles(ROLES, ["admin"]);
    expect(filtered.map((r) => r.slug)).toContain("newbie");
  });

  it("keeps `newbie` visible when the caller is a head_of_*", () => {
    const filtered = filterAssignableRoles(ROLES, ["head_of_sales"]);
    expect(filtered.map((r) => r.slug)).toContain("newbie");
  });

  it("keeps `newbie` visible for a non-assigner caller IF the member already has it", () => {
    // Edit-mode safety: a top_manager opening the sheet on an existing
    // newbie user must still see the chip so they understand the state,
    // even if the checkbox itself is locked at the component layer.
    const filtered = filterAssignableRoles(ROLES, ["top_manager"], {
      memberHasNewbie: true,
    });
    expect(filtered.map((r) => r.slug)).toContain("newbie");
  });

  it("hides `newbie` for a non-assigner caller when the member does not have it", () => {
    const filtered = filterAssignableRoles(ROLES, ["top_manager"], {
      memberHasNewbie: false,
    });
    expect(filtered.map((r) => r.slug)).not.toContain("newbie");
  });
});
