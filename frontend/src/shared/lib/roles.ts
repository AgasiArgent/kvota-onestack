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

/**
 * Roles allowed to create customers via the «Новый клиент» dialog on the
 * /customers page (Testing 2 row 82). The complaint: РОЗ
 * (head_of_procurement) reported no create button. Underlying issue was
 * twofold — the sidebar entry was gated to sales-only, and there was no
 * explicit role gate on the dialog trigger.
 *
 * Authorized: admin, sales tier (МОП, РОП), procurement tier (МОЗ, СтМОЗ,
 * РОЗ), top_manager. Customers are a sales/procurement collaboration
 * surface — both tiers may need to add a new counterparty when triaging
 * a deal.
 *
 * Excluded: logistics, customs, finance, controllers, currency_controller,
 * newbie — they consume customer data downstream and have no business
 * creating new counterparties. The kvota.customers INSERT RLS policy is
 * organization-scoped (no role check), so this gate is the visibility
 * contract — backend trust is maintained by RLS at the org boundary.
 */
const CUSTOMER_CREATE_ROLES = [
  "admin",
  "top_manager",
  "sales",
  "head_of_sales",
  "procurement",
  "procurement_senior",
  "head_of_procurement",
];

/**
 * Returns true if the user may create a customer via the /customers page
 * «Новый клиент» dialog.
 */
export function canCreateCustomer(roles: string[]): boolean {
  return roles.some((r) => CUSTOMER_CREATE_ROLES.includes(r));
}

/**
 * Roles allowed to create / edit buyer companies (our legal entities used for
 * purchasing) via the /companies?tab=buyer page (Testing 2 row 82 follow-up).
 * The complaint: РОЗ (head_of_procurement) reported no Создать/Редактировать
 * buttons on the buyer tab.
 *
 * Authorized: admin, finance, procurement, procurement_senior,
 * head_of_procurement — matches the page-level ALLOWED_ROLES set and the
 * widened buyer_companies INSERT/UPDATE RLS policy (migration 331).
 *
 * Buyer companies are operational counterparties consumed by the procurement
 * workflow; the procurement tier is the natural maintainer alongside admin
 * and finance.
 */
const BUYER_COMPANY_MANAGE_ROLES = [
  "admin",
  "finance",
  "procurement",
  "procurement_senior",
  "head_of_procurement",
];

/**
 * Returns true if the user may create or edit buyer companies via the
 * /companies?tab=buyer page.
 */
export function canManageBuyerCompany(roles: string[]): boolean {
  return roles.some((r) => BUYER_COMPANY_MANAGE_ROLES.includes(r));
}

// ===========================================================================
// control-spec-workspace — Контроль расчёта / Контроль спецификации gates
// ===========================================================================
// Two control gates already exist in the quote rail:
//   - pending_quote_control → "Контроль расчёта", owned by quote_controller
//   - pending_spec_control  → "Контроль спецификации", owned by spec_controller
// These helpers gate the /workspace/control board visibility and the spec-control
// screen edit permissions. admin and top_manager are full-visibility roles and see
// both boards; top_manager is read-only (enforced via ROLE_EDITABLE_STEPS), so its
// board visibility is observe-only. All checks are plain membership → unknown roles
// fail closed (return false / { calc: false, spec: false }).

/** Roles that see every control board regardless of which gate they own. */
const CONTROL_BOARD_FULL_VISIBILITY_ROLES = ["admin", "top_manager"];

/** Returns true if the user holds the quote_controller (Контроль расчёта) role. */
export function isQuoteController(roles: string[]): boolean {
  return roles.includes("quote_controller");
}

/** Returns true if the user holds the spec_controller (Контроль спецификации) role. */
export function isSpecController(roles: string[]): boolean {
  return roles.includes("spec_controller");
}

/**
 * Which control kanban boards the user may see on /workspace/control.
 *   - quote_controller → calc board (Контроль расчёта)
 *   - spec_controller  → spec board (Контроль спецификации)
 *   - admin / top_manager → both
 * Anyone else sees neither (fail-closed) — the page guard redirects them.
 */
export function canSeeControlBoard(roles: string[]): {
  calc: boolean;
  spec: boolean;
} {
  const full = roles.some((r) => CONTROL_BOARD_FULL_VISIBILITY_ROLES.includes(r));
  return {
    calc: full || isQuoteController(roles),
    spec: full || isSpecController(roles),
  };
}

/**
 * Returns true if the user may edit the spec-control screen fields
 * (requisites, conditions, control stamp). The spec_controller is the
 * responsible-for-correctness party; admin may also edit. top_manager is
 * explicitly excluded (read-only); quote_controller owns the calc gate, not
 * spec editing. Mirrors the field-scope check on the Python API side.
 */
export function canEditSpecControl(roles: string[]): boolean {
  return roles.includes("admin") || isSpecController(roles);
}
