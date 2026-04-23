/**
 * Access control helpers for the Customer Journey Map.
 *
 * Authoritative rules live in
 * `.kiro/specs/customer-journey-map/requirements.md` §6.4, §6.5, §7.1,
 * §8.1, §9.1–9.2, and in `.kiro/steering/access-control.md`.
 *
 * ACL snapshot (post-amendment 32c46fa8 — 2026-04-22):
 *
 *   impl_status     → admin, head_of_{sales,procurement,logistics},
 *                     sales, procurement, procurement_senior, logistics, customs
 *   qa_status       → admin, quote_controller, spec_controller
 *   notes           → impl ∪ qa
 *   ghost node CUD  → admin only
 *   pin CUD         → admin, quote_controller, spec_controller
 *   verification    → admin, quote_controller, spec_controller (INSERT only)
 *
 * Every set is exposed both as a `ReadonlySet<RoleSlug>` (for O(1) lookups
 * and enumeration) and as a boolean guard taking the caller's held roles.
 * `top_manager` is deliberately view-only per access-control.md — it does
 * not appear in any writer set.
 */

import type { RoleSlug } from "./types";

// ---------------------------------------------------------------------------
// Writer sets
// ---------------------------------------------------------------------------

/** Roles permitted to write `impl_status` (Req 6.4). */
export const IMPL_STATUS_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  "admin",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "sales",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
]);

/** Roles permitted to write `qa_status` (Req 6.5). */
export const QA_STATUS_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  "admin",
  "quote_controller",
  "spec_controller",
]);

/** Roles permitted to edit notes — union of impl and qa writer sets. */
export const NOTES_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  ...IMPL_STATUS_WRITERS,
  ...QA_STATUS_WRITERS,
]);

/** Roles permitted to create / update / delete ghost nodes (Req 7.1 — admin only). */
export const GHOST_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>(["admin"]);

/** Roles permitted to create / update / delete pins (Req 8.1). */
export const PIN_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  "admin",
  "quote_controller",
  "spec_controller",
]);

/** Roles permitted to INSERT verification rows (Req 9.1, 9.2 — append-only). */
export const VERIFICATION_WRITERS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  "admin",
  "quote_controller",
  "spec_controller",
]);

// ---------------------------------------------------------------------------
// Guard functions
// ---------------------------------------------------------------------------

function anyMatch(held: readonly RoleSlug[], allowed: ReadonlySet<RoleSlug>): boolean {
  for (const slug of held) {
    if (allowed.has(slug)) return true;
  }
  return false;
}

/** True iff the caller holds at least one role in {@link IMPL_STATUS_WRITERS}. */
export function canEditImpl(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, IMPL_STATUS_WRITERS);
}

/** True iff the caller holds at least one role in {@link QA_STATUS_WRITERS}. */
export function canEditQa(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, QA_STATUS_WRITERS);
}

/** True iff the caller can edit either impl or qa status (notes follow this rule). */
export function canEditNotes(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, NOTES_WRITERS);
}

/** True iff the caller is admin (ghost CUD is admin-only per Req 7.1). */
export function canCreateGhost(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, GHOST_WRITERS);
}

/** True iff the caller holds at least one role in {@link PIN_WRITERS}. */
export function canCreatePin(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, PIN_WRITERS);
}

/** True iff the caller holds at least one role in {@link VERIFICATION_WRITERS}. */
export function canRecordVerification(heldRoles: readonly RoleSlug[]): boolean {
  return anyMatch(heldRoles, VERIFICATION_WRITERS);
}
