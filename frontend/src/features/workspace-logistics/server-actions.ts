"use server";

import { revalidatePath } from "next/cache";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user";

/**
 * reassignInvoice — single endpoint for both logistics & customs reassignment.
 * Per spec §6.3: POST /workflow/reassign { invoice_id, type, new_user_id }.
 * One auth policy, one business-logic path, one changelog record.
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

  const res = await apiServerClient("/workflow/reassign", {
    method: "POST",
    body: JSON.stringify({
      invoice_id: invoiceId,
      type: domain,
      new_user_id: newUserId,
    }),
  });
  if (!res.success) {
    throw new Error(res.error?.message ?? "Failed to reassign");
  }

  revalidatePath(`/workspace/${domain}`);
}
