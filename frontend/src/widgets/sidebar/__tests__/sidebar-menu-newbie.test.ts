import { describe, expect, it } from "vitest";
import { buildMenuSections } from "../sidebar-menu";

/**
 * Testing 2 row 38p2 — sidebar must be empty for users whose only role
 * is `newbie`. Mixed assignments (e.g., newbie + sales) revert to the
 * functional role's nav surface.
 */

describe("buildMenuSections — newbie role", () => {
  it("returns no sections for a newbie-only user", () => {
    const sections = buildMenuSections({
      roles: ["newbie"],
      isAdmin: false,
    });
    expect(sections).toEqual([]);
  });

  it("returns the normal nav when newbie is combined with a functional role", () => {
    const sections = buildMenuSections({
      roles: ["newbie", "sales"],
      isAdmin: false,
    });
    // Functional roles get at least the "Главное" section.
    expect(sections.length).toBeGreaterThan(0);
    expect(sections.some((s) => s.title === "Главное")).toBe(true);
  });

  it("does not short-circuit the admin path when admin + newbie are paired", () => {
    const sections = buildMenuSections({
      roles: ["newbie", "admin"],
      isAdmin: true,
    });
    expect(sections.length).toBeGreaterThan(0);
    // Admin sees the Администрирование block.
    expect(sections.some((s) => s.title === "Администрирование")).toBe(true);
  });

  it("returns normal nav for non-newbie users", () => {
    const sections = buildMenuSections({
      roles: ["sales"],
      isAdmin: false,
    });
    expect(sections.length).toBeGreaterThan(0);
  });
});
