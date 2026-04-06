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
 * Only admin and head_of_procurement.
 */
export function canManageSupplierAssignees(roles: string[]): boolean {
  return roles.includes("admin") || roles.includes("head_of_procurement");
}
