"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user/server";
import { revalidatePath } from "next/cache";

/**
 * Assigns a brand-slice of quote items to a procurement user (МОЗ) and
 * optionally pins the brand so future quotes with the same brand auto-route
 * to the same user.
 *
 * Server Action — called both from the distribution page and from the kanban
 * assign popover. Authorization is enforced server-side (admin,
 * head_of_procurement, procurement_senior).
 */
export async function assignBrandGroup(
  itemIds: string[],
  userId: string,
  pinBrand: boolean,
  orgId: string,
  brand: string | null
): Promise<{ success: boolean; error?: string }> {
  const user = await getSessionUser();
  if (!user?.orgId) return { success: false, error: "Not authenticated" };

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement") ||
    user.roles.includes("procurement_senior");
  if (!isAllowed) return { success: false, error: "Not authorized" };

  const supabase = createAdminClient();

  // 1. Assign all items in the group and set status to pending
  const { error: updateError } = await supabase
    .from("quote_items")
    .update({
      assigned_procurement_user: userId,
      procurement_status: "pending",
    })
    .in("id", itemIds);

  if (updateError) {
    return { success: false, error: updateError.message };
  }

  // 2. Optionally pin the brand rule
  if (pinBrand && brand) {
    const { error: brandError } = await supabase
      .from("brand_assignments")
      .insert({
        organization_id: orgId,
        brand,
        user_id: userId,
        created_by: user.id,
      });

    // Ignore unique constraint — brand may already be pinned
    if (
      brandError &&
      !brandError.message.includes("unique_brand_per_org") &&
      !brandError.message.includes("duplicate key")
    ) {
      console.error("Failed to pin brand:", brandError);
    }
  }

  revalidatePath("/procurement/distribution");
  revalidatePath("/procurement/kanban");
  return { success: true };
}
