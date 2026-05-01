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

  const requiredRole =
    domain === "logistics" ? "head_of_logistics" : "head_of_customs";
  if (
    !user.roles.includes(requiredRole) &&
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
  const admin = createAdminClient();
  const updates: Record<string, string | null> = {
    [userCol]: newUserId,
    [assignedAtCol]: newUserId ? new Date().toISOString() : null,
  };
  const { error } = await admin
    .from("invoices")
    .update(updates)
    .eq("id", invoiceId);
  if (error) {
    console.error("[reassignInvoice] update failed:", error);
    throw new Error(error.message ?? "Failed to reassign");
  }

  revalidatePath(`/workspace/${domain}`);
}
