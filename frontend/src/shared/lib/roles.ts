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
  if (roles.includes("head_of_procurement")) return false; // Match docstring: head sees all
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

/**
 * Returns true if the user can use the «Переназначить» button on a
 * procurement kanban card (Testing 2 row 75 v2).
 *
 * v1 (PR #217) limited reassignment to admin / head_of_procurement /
 * procurement_senior — the heads. v2 widens the gate to include regular
 * `procurement` (МОЗ) so they can also reroute their own brand-slices to
 * colleagues (cover sickness / vacation / overload).
 *
 * The РЛС policy on `kvota.quote_items` is the canonical authorization
 * layer — МОЗ only sees rows they're assigned to anyway, so this UI gate
 * is the visibility contract rather than the security boundary.
 */
export function canReassignBrandGroup(roles: string[]): boolean {
  return (
    roles.includes("admin") ||
    roles.includes("head_of_procurement") ||
    roles.includes("procurement_senior") ||
    roles.includes("procurement")
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
export const BROAD_QUOTE_ACCESS_ROLES = [
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

/**
 * Roles allowed to view quote financial summary (Прибыль / Маржа / Наценка)
 * on the quote profile header. Procurement / logistics / customs roles are
 * intentionally excluded — they don't need (and shouldn't see) margin info.
 *
 * Issue МОЗ-60: a procurement manager (МОЗ) flagged that they shouldn't be
 * able to see profit/margin/markup of a quote.
 */
const QUOTE_FINANCIALS_ROLES = [
  "admin",
  "top_manager",
  "finance",
  "sales",
  "head_of_sales",
  "quote_controller",
  "spec_controller",
  "currency_controller",
];

/**
 * Returns true if the user may see quote financial figures (profit, margin,
 * markup) on the quote detail page. Excludes procurement, logistics, customs
 * and their leads.
 */
export function canViewQuoteFinancials(roles: string[]): boolean {
  return roles.some((r) => QUOTE_FINANCIALS_ROLES.includes(r));
}

/** Roles allowed to mutate sales-side customer-facing fields on a quote
 * (contact person, delivery address). Procurement / logistics / customs /
 * finance / controllers must not change which contact or address is on a
 * quote — that's a sales decision.
 */
const QUOTE_CUSTOMER_FIELDS_EDIT_ROLES = ["admin", "sales", "head_of_sales"];

/**
 * Returns true if the user may edit customer-facing fields (contact, address)
 * on a quote. Restricted to admin and the sales tier.
 */
export function canEditQuoteCustomerFields(roles: string[]): boolean {
  return roles.some((r) => QUOTE_CUSTOMER_FIELDS_EDIT_ROLES.includes(r));
}

/** Roles that should see financial aggregate columns (Сумма / Прибыль /
 * Выручка / Спец) in list views. Procurement / logistics / customs roles
 * execute later pipeline stages — financial summary noise just confuses them.
 */
const FINANCIALS_VISIBLE_ROLES = [
  "admin",
  "sales",
  "head_of_sales",
  "quote_controller",
  "spec_controller",
  "finance",
  "top_manager",
];

/**
 * Returns true if the user should see financial aggregate columns in list
 * views. Excludes procurement, logistics, customs and their leads.
 */
export function shouldShowFinancials(roles: string[]): boolean {
  return roles.some((r) => FINANCIALS_VISIBLE_ROLES.includes(r));
}

/**
 * Roles allowed to create rows in kvota.locations from the /locations page
 * (Testing 2 row 13). Mirrors the page-level access set — every role that
 * sees the registry can extend it.
 *
 * Sales / head_of_sales are intentionally excluded: they don't see the
 * /locations page (redirected away by ALLOWED_ROLES in route handler), so
 * granting them write access here would be moot.
 */
const LOCATION_CREATE_ROLES = [
  "admin",
  "top_manager",
  "logistics",
  "head_of_logistics",
  "customs",
  "head_of_customs",
  "procurement",
  "procurement_senior",
  "head_of_procurement",
];

/**
 * Returns true if the user may create a new location via the /locations
 * page «Создать локацию» dialog.
 */
export function canCreateLocation(roles: string[]): boolean {
  return roles.some((r) => LOCATION_CREATE_ROLES.includes(r));
}
