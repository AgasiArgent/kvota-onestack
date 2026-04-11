const SALES_ROLES = ["sales", "head_of_sales"];

const PROCUREMENT_ROLES = ["procurement", "procurement_senior", "head_of_procurement"];

const NON_SALES_ROLES = [
  "admin",
  "top_manager",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
  "quote_controller",
  "spec_controller",
  "finance",
  "head_of_procurement",
  "head_of_logistics",
];

const NON_PROCUREMENT_ROLES = [
  "admin",
  "top_manager",
  "sales",
  "head_of_sales",
  "logistics",
  "customs",
  "quote_controller",
  "spec_controller",
  "finance",
  "head_of_logistics",
];

/**
 * Returns true if the user has ONLY sales-type roles (sales, head_of_sales)
 * and no other operational roles that grant broader visibility.
 */
export function isSalesOnly(roles: string[]): boolean {
  return (
    roles.some((r) => SALES_ROLES.includes(r)) &&
    !roles.some((r) => NON_SALES_ROLES.includes(r))
  );
}

/**
 * Returns true if the user has the head_of_sales role.
 * Head of sales sees all customers managed by anyone in their sales group.
 * Regular sales sees only their own customers.
 */
export function isHeadOfSales(roles: string[]): boolean {
  return roles.includes("head_of_sales");
}

/**
 * Returns true if the user has ONLY procurement-type roles
 * and no other operational roles that grant broader supplier visibility.
 * head_of_procurement sees all suppliers (not "procurement only").
 */
export function isProcurementOnly(roles: string[]): boolean {
  return (
    roles.some((r) => PROCUREMENT_ROLES.includes(r)) &&
    !roles.some((r) => NON_PROCUREMENT_ROLES.includes(r))
  );
}

/**
 * Returns true if the user has any procurement role (including head).
 * Used for page-level access checks (can user see supplier pages at all?).
 */
export function hasProcurementAccess(roles: string[]): boolean {
  return (
    roles.includes("admin") ||
    roles.includes("top_manager") ||
    roles.some((r) => PROCUREMENT_ROLES.includes(r))
  );
}

/**
 * Returns true if the user can manage supplier assignees.
 * Admin, head_of_procurement, and procurement_senior.
 */
export function canManageSupplierAssignees(roles: string[]): boolean {
  return (
    roles.includes("admin") ||
    roles.includes("head_of_procurement") ||
    roles.includes("procurement_senior")
  );
}

const ASSIGNED_ITEMS_ROLES = ["procurement", "logistics", "customs"];

/** Roles that grant broader quote access than procurement_senior's stage-only view. */
const ROLES_BROADER_THAN_PROCUREMENT_SENIOR = [
  "admin",
  "top_manager",
  "quote_controller",
  "spec_controller",
  "finance",
  "head_of_logistics",
  "head_of_procurement",
  "sales",
  "head_of_sales",
];

/** Roles that grant quote visibility beyond personal item assignment. */
const BROAD_QUOTE_ACCESS_ROLES = [
  "admin",
  "top_manager",
  "quote_controller",
  "spec_controller",
  "finance",
  "head_of_logistics",
  "head_of_procurement",
  "procurement_senior",
  "sales",
  "head_of_sales",
];

/**
 * Returns true if the user has procurement_senior and no other role that
 * grants broader quote access. These users see only quotes in procurement stage.
 * If combined with basic procurement/logistics/customs, procurement_senior
 * is the dominant tier (it's broader). If combined with admin/sales/etc.,
 * the user falls through to the broader tier.
 */
export function isProcurementSeniorOnly(roles: string[]): boolean {
  return (
    roles.includes("procurement_senior") &&
    !roles.some((r) => ROLES_BROADER_THAN_PROCUREMENT_SENIOR.includes(r))
  );
}

/**
 * Returns true if the user has ONLY assigned-items roles (procurement,
 * logistics, customs) and no other role that grants broader quote visibility.
 * These users should only see quotes where they are personally assigned.
 */
export function isAssignedItemsOnly(roles: string[]): boolean {
  return (
    roles.some((r) => ASSIGNED_ITEMS_ROLES.includes(r)) &&
    !roles.some((r) => BROAD_QUOTE_ACCESS_ROLES.includes(r))
  );
}

/** Roles that override the customs stage-only tier (grant full quote visibility). */
const ROLES_BROADER_THAN_CUSTOMS = ["admin", "top_manager"];

/**
 * Returns true if the user has the customs role and no full-visibility role
 * (admin, top_manager). Customs users see all quotes currently in customs
 * workflow stages (pending_customs, pending_logistics_and_customs) for their
 * organization — there is no per-user customs assignment mechanism yet.
 *
 * Checked BEFORE isAssignedItemsOnly in the access-tier chain, so a pure
 * customs user is routed to the stage-based filter instead of the (empty)
 * assignment-based filter.
 */
export function isCustomsOnly(roles: string[]): boolean {
  return (
    roles.includes("customs") &&
    !roles.some((r) => ROLES_BROADER_THAN_CUSTOMS.includes(r))
  );
}

/** Roles allowed to edit quote composition (pick per-item supplier).
 *
 * Phase 5b composition is a sales/procurement collaboration surface:
 * sales opens the picker to decide per-item which supplier to go with;
 * procurement roles need the same view to verify the state. Matches the
 * api/composition.py COMPOSITION_WRITE_ROLES set.
 *
 * Excluded: logistics, customs (ASSIGNED_ITEMS tier — composition is not
 * in their flow), head_of_logistics (org-wide logistics, not procurement).
 */
const COMPOSITION_EDIT_ROLES = [
  "admin",
  "top_manager",
  "procurement",
  "procurement_senior",
  "head_of_procurement",
  "sales",
  "head_of_sales",
  "finance",
  "quote_controller",
  "spec_controller",
];

/**
 * Returns true if the user may edit composition (POST to
 * /api/quotes/{id}/composition). Mirrors the backend's
 * COMPOSITION_WRITE_ROLES role set in api/composition.py.
 */
export function canEditComposition(roles: string[]): boolean {
  return roles.some((r) => COMPOSITION_EDIT_ROLES.includes(r));
}
