"use server";

import { revalidatePath } from "next/cache";
import { getSessionUser } from "@/entities/user";
import { createAdminClient } from "@/shared/lib/supabase/server";

/**
 * reassignInvoice — assigns / unassigns the invoice's logistics or customs
 * owner.
 *
 * Per-invoice procurement completion (Phase «per-invoice») decoupled
 * assignment from the legacy quote-level workflow transition. The Python
 * `/workflow/reassign` endpoint guards on quote.workflow_status which now
 * stays at `pending_procurement` even when individual КП are finalized —
 * making the endpoint refuse and surface as «failed to reassign» in the
 * UI.
 *
 * Frontend writes directly to `invoices.assigned_logistics_user` /
 * `assigned_customs_user` via the admin client. Auth is enforced here
 * (same role gate the Python endpoint had).
 */

export async function reassignInvoice(
  invoiceId: string,
  domain: "logistics" | "customs",
  newUserId: string | null,
): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");
  if (!user.orgId) throw new Error("No organization context");

  // head_of_logistics ↔ head_of_customs are dual-hat (PR #105): either head
  // role can reassign in BOTH domains.
  if (
    !user.roles.includes("head_of_logistics") &&
    !user.roles.includes("head_of_customs") &&
    !user.roles.includes("admin") &&
    !user.roles.includes("top_manager")
  ) {
    throw new Error("Forbidden");
  }

  const userCol =
    domain === "logistics" ? "assigned_logistics_user" : "assigned_customs_user";
  const assignedAtCol =
    domain === "logistics" ? "logistics_assigned_at" : "customs_assigned_at";

  // Workspace stats and SLA averages count off the *_assigned_at timestamp,
  // not the *_user UUID. Stamp it on assign, clear it on unassign — same
  // contract the legacy Python workflow honoured.
  //
  // Org scoping: the legacy Python /workflow/reassign endpoint scoped writes
  // by organization_id. The strangler-fig migration to a Server Action
  // dropped that filter, leaving cross-org reassignment possible by guessing
  // an invoice UUID. Restore the filter here. `.select()` after `.update()`
  // returns the affected rows; an empty array means the invoice was not in
  // this user's org (or the id is wrong) — surface as Forbidden either way.
  const admin = createAdminClient();
  const updates: Record<string, string | null> = {
    [userCol]: newUserId,
    [assignedAtCol]: newUserId ? new Date().toISOString() : null,
  };
  const { data, error } = await admin
    .from("invoices")
    .update(updates)
    .eq("id", invoiceId)
    .eq("organization_id", user.orgId)
    .select("id");
  if (error) {
    console.error("[reassignInvoice] update failed:", error);
    throw new Error(error.message ?? "Failed to reassign");
  }
  if (!data || data.length === 0) {
    throw new Error("Forbidden");
  }

  revalidatePath(`/workspace/${domain}`);
}
