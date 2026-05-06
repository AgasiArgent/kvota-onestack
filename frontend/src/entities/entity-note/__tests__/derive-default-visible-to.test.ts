/**
 * МОП-1 regression: composer's default visibility must derive from the
 * current user's department role, not "Видно всем".
 *
 * The bug: panel hardcoded ["*"] as defaultVisibleTo, so МОП notes leaked
 * to logistics/customs/etc. Derived defaults narrow visibility to the
 * note author's own department.
 */
import { describe, expect, it } from "vitest";
import { deriveDefaultVisibleTo } from "../ui/entity-notes-panel";

describe("deriveDefaultVisibleTo (МОП-1)", () => {
  it("returns ['sales'] for sales-only user", () => {
    expect(deriveDefaultVisibleTo(["sales"])).toEqual(["sales"]);
  });

  it("returns ['procurement'] for procurement user", () => {
    expect(deriveDefaultVisibleTo(["procurement"])).toEqual(["procurement"]);
  });

  it("returns ['logistics'] for logistics user", () => {
    expect(deriveDefaultVisibleTo(["logistics"])).toEqual(["logistics"]);
  });

  it("returns ['customs'] for customs user", () => {
    expect(deriveDefaultVisibleTo(["customs"])).toEqual(["customs"]);
  });

  it("prefers working role over admin when user is both admin and a department role", () => {
    // A user who is both admin and procurement defaults to procurement —
    // their day-to-day department, not the all-seeing admin lens.
    expect(deriveDefaultVisibleTo(["admin", "procurement"])).toEqual([
      "procurement",
    ]);
  });

  it("returns ['*'] for admin-only users (no department fallback)", () => {
    // Admin without a working role can't be narrowed to a department —
    // their notes default to all-visible.
    expect(deriveDefaultVisibleTo(["admin"])).toEqual(["*"]);
  });

  it("returns ['*'] for users with no roles", () => {
    expect(deriveDefaultVisibleTo([])).toEqual(["*"]);
  });

  it("respects DEPARTMENT_ROLE_PRIORITY order — sales wins over head_of_sales", () => {
    // When a user holds both МОП-level and РОП-level roles, the more
    // specific (sales) wins so notes stay tied to their working scope.
    expect(deriveDefaultVisibleTo(["head_of_sales", "sales"])).toEqual([
      "sales",
    ]);
  });

  it("falls back to head_of_<dept> if only the head role is present", () => {
    expect(deriveDefaultVisibleTo(["head_of_logistics"])).toEqual([
      "head_of_logistics",
    ]);
  });
});
