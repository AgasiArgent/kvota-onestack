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

  // Org scoping: the legacy Python /workflow/reassign endpoint scoped writes
  // by quote.organization_id (invoices has no `organization_id` column —
  // only quote_id, FK to quotes which has the org). The strangler-fig
  // migration to a Server Action dropped that filter, leaving cross-org
  // reassignment possible by guessing an invoice UUID. Restore the filter
  // by pre-checking via the quotes join, then updating by id.
  const admin = createAdminClient();
  const { data: ownership, error: ownershipError } = await admin
    .from("invoices")
    .select("id, quotes!inner(organization_id)")
    .eq("id", invoiceId)
    .eq("quotes.organization_id", user.orgId)
    .maybeSingle();
  if (ownershipError) {
    console.error("[reassignInvoice] ownership check failed:", ownershipError);
    throw new Error("Failed to reassign");
  }
  if (!ownership) {
    // Wrong org or wrong id — don't differentiate (no UUID enumeration leak).
    throw new Error("Forbidden");
  }

  // Workspace stats and SLA averages count off the *_assigned_at timestamp,
  // not the *_user UUID. Stamp it on assign, clear it on unassign — same
  // contract the legacy Python workflow honoured.
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
    throw new Error("Failed to reassign");
  }

  revalidatePath(`/workspace/${domain}`);
}
