import { describe, expect, it } from "vitest";
import { buildMenuSections } from "../sidebar-menu";

/**
 * Testing 2 row 82 — РОЗ (head_of_procurement) reported no «Создать
 * клиента» button on /customers. Root cause was a missing sidebar link:
 * the "Клиенты" entry was gated to sales tier only, so РОЗ had no way
 * to navigate to the page (and no button surface to begin with).
 *
 * The widened gate must match the role set authorized by
 * `canCreateCustomer` — every role that can create must also have the
 * link in the nav.
 */

function findCustomersItem(roles: string[], isAdmin = false) {
  const sections = buildMenuSections({ roles, isAdmin });
  const registries = sections.find((s) => s.title === "Реестры");
  return registries?.items.find((item) => item.href === "/customers");
}

describe("sidebar — «Клиенты» link visibility (Testing 2 row 82)", () => {
  // -----------------------------------------------------------------------
  // Roles that must see the link
  // -----------------------------------------------------------------------

  it.each([
    ["sales"],
    ["head_of_sales"],
    ["top_manager"],
    ["procurement"],
    ["procurement_senior"],
    ["head_of_procurement"],
  ])("shows «Клиенты» for role %s", (role) => {
    const item = findCustomersItem([role]);
    expect(item).toBeDefined();
    expect(item?.label).toBe("Клиенты");
  });

  it("shows «Клиенты» for admin", () => {
    const item = findCustomersItem([], true);
    expect(item).toBeDefined();
  });

  // -----------------------------------------------------------------------
  // Roles that must NOT see the link
  // -----------------------------------------------------------------------

  it.each([
    ["logistics"],
    ["head_of_logistics"],
    ["customs"],
    ["head_of_customs"],
    ["finance"],
    ["quote_controller"],
    ["spec_controller"],
    ["currency_controller"],
  ])("hides «Клиенты» for role %s", (role) => {
    const item = findCustomersItem([role]);
    expect(item).toBeUndefined();
  });
});
