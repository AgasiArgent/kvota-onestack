"use server";

import { revalidatePath } from "next/cache";
import { getSessionUser } from "@/entities/user";
import { createAdminClient } from "@/shared/lib/supabase/server";

/**
 * Workspace-kanban server actions.
 *
 * `selfPullInvoice` is the member self-assign path (REQ-7): a logistics /
 * customs member drags a card from «Нераспределено» to «В работе» and the
 * invoice is assigned to *themselves* — they cannot assign anyone else.
 *
 * Head assign / reassign (REQ-8) goes through `reassignInvoice` (from the
 * `workspace-logistics` slice) — imported directly by the assignee picker.
 * A `"use server"` module may only export locally-declared async actions, so
 * it cannot re-export it here. Its head-only role gate stays intact.
 */

type WorkspaceDomain = "logistics" | "customs";

const DOMAIN_ROLES: Record<WorkspaceDomain, string> = {
  logistics: "logistics",
  customs: "customs",
};

/**
 * selfPullInvoice — assigns an unassigned invoice to the current user.
 *
 * Role gate: the domain member role (`logistics` / `customs`) OR a head role
 * (heads can also self-pull). A user lacking the domain role is rejected.
 *
 * The write is guarded against races (REQ-7, Risk 5): the update only lands
 * when `assigned_{domain}_user IS NULL` — if another member pulled the card
 * first, zero rows update and we surface an error so the optimistic move
 * rolls back.
 */
export async function selfPullInvoice(
  invoiceId: string,
  domain: WorkspaceDomain
): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");
  if (!user.orgId) throw new Error("No organization context");

  const isHead =
    user.roles.includes("head_of_logistics") ||
    user.roles.includes("head_of_customs") ||
    user.roles.includes("admin") ||
    user.roles.includes("top_manager");
  const isMember = user.roles.includes(DOMAIN_ROLES[domain]);
  if (!isMember && !isHead) {
    throw new Error("Forbidden");
  }

  const userCol =
    domain === "logistics"
      ? "assigned_logistics_user"
      : "assigned_customs_user";
  const assignedAtCol =
    domain === "logistics"
      ? "logistics_assigned_at"
      : "customs_assigned_at";

  const admin = createAdminClient();

  // Org scoping — invoices has no organization_id; verify ownership through
  // the quotes join before writing (same guard as reassignInvoice).
  const { data: ownership, error: ownershipError } = await admin
    .from("invoices")
    .select("id, quotes!inner(organization_id)")
    .eq("id", invoiceId)
    .eq("quotes.organization_id", user.orgId)
    .maybeSingle();
  if (ownershipError) {
    console.error("[selfPullInvoice] ownership check failed:", ownershipError);
    throw new Error("Не удалось взять заявку");
  }
  if (!ownership) {
    // Wrong org or wrong id — don't differentiate (no UUID enumeration leak).
    throw new Error("Forbidden");
  }

  // Race guard: only claim the invoice if it is still unassigned.
  const { data: updated, error } = await admin
    .from("invoices")
    .update({
      [userCol]: user.id,
      [assignedAtCol]: new Date().toISOString(),
    })
    .eq("id", invoiceId)
    .is(userCol, null)
    .select("id");
  if (error) {
    console.error("[selfPullInvoice] update failed:", error);
    throw new Error("Не удалось взять заявку");
  }
  if (!updated || updated.length === 0) {
    // Another member pulled it first.
    throw new Error("Заявку уже взял другой сотрудник");
  }

  revalidatePath(`/workspace/${domain}`);
}
