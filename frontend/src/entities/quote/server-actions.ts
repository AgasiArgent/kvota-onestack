"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user";
import { revalidatePath } from "next/cache";
import { maybeAdvanceBrandSlices } from "./kanban-auto-advance";

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
): Promise<{
  success: boolean;
  error?: string;
  /**
   * Brand-slices the auto-advance helper just promoted forward as a
   * side-effect of this assignment. UI surfaces this as a toast so
   * пользователь видит, что канбан изменился без его ручного действия.
   */
  advancedSlices?: Array<{ quote_id: string; brand: string; to: string }>;
}> {
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

  // 3. Auto-advance kanban brand-slices that just became fully routed.
  //    Best-effort — failures here must not roll back the assignment.
  let advancedSlices: Array<{ quote_id: string; brand: string; to: string }> = [];
  try {
    const { data: assignedItems } = await supabase
      .from("quote_items")
      .select("quote_id, brand")
      .in("id", itemIds);
    const seen = new Set<string>();
    const slices: Array<{ quote_id: string; brand: string }> = [];
    for (const it of (assignedItems ?? []) as Array<{
      quote_id: string;
      brand: string | null;
    }>) {
      const key = `${it.quote_id}|${it.brand ?? ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      slices.push({ quote_id: it.quote_id, brand: it.brand ?? "" });
    }
    if (slices.length > 0) {
      const res = await maybeAdvanceBrandSlices({
        trigger: "distribution",
        slices,
        userId: user.id,
      });
      advancedSlices = res.advanced;
    }
  } catch (err) {
    console.error("[assignBrandGroup] auto-advance failed:", err);
  }

  revalidatePath("/procurement/distribution");
  revalidatePath("/procurement/kanban");
  return { success: true, advancedSlices };
}

/**
 * Reassigns a brand-slice that's already been distributed to a different
 * procurement user (МОЗ). Differs from `assignBrandGroup` in three ways:
 *   - Touches `assigned_procurement_user` only — never resets
 *     `procurement_status`, so an in-progress slice keeps its status when
 *     the head_of_procurement swaps the owner.
 *   - Does NOT trigger `maybeAdvanceBrandSlices` — the slice is already
 *     past «Распределение», so auto-advance can only mis-fire.
 *   - Does NOT pin the brand — the head is overriding a single slice, not
 *     setting a default rule.
 *
 * Testing 2 row 75: «Кнопка переназначения в канбане закупок» — the head
 * needs to swap МОЗ on already-routed slices when someone is sick / on
 * vacation / overloaded without resetting the workflow.
 */
export async function reassignBrandGroup(
  itemIds: string[],
  userId: string
): Promise<{ success: boolean; error?: string }> {
  const user = await getSessionUser();
  if (!user?.orgId) return { success: false, error: "Not authenticated" };

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement") ||
    user.roles.includes("procurement_senior");
  if (!isAllowed) return { success: false, error: "Not authorized" };

  if (itemIds.length === 0) {
    return { success: false, error: "Нет позиций для переназначения" };
  }

  const supabase = createAdminClient();

  const { error: updateError } = await supabase
    .from("quote_items")
    .update({ assigned_procurement_user: userId })
    .in("id", itemIds);

  if (updateError) {
    return { success: false, error: updateError.message };
  }

  revalidatePath("/procurement/kanban");
  return { success: true };
}

/**
 * Phase B trigger: called from the letter-draft-composer right after the
 * Python `/api/invoices/{id}/letter-draft/send` succeeds. Promotes every
 * brand-slice represented in the invoice's items from
 * `searching_supplier` → `waiting_prices`.
 *
 * Best-effort — failures are swallowed so the «Письмо отправлено» path
 * doesn't break if the kanban update misfires.
 */
export async function notifyInvoiceSentForKanban(
  invoiceId: string
): Promise<{
  advancedSlices: Array<{ quote_id: string; brand: string; to: string }>;
}> {
  const user = await getSessionUser();
  if (!user?.orgId) return { advancedSlices: [] };

  const supabase = createAdminClient();

  // Discover (quote_id, brand) pairs from this invoice's items.
  const { data: invoice, error: invErr } = await supabase
    .from("invoices")
    .select("quote_id")
    .eq("id", invoiceId)
    .maybeSingle();
  if (invErr || !invoice) {
    console.error("[notifyInvoiceSentForKanban] invoice lookup failed", invErr);
    return { advancedSlices: [] };
  }
  const quoteId = (invoice as { quote_id: string }).quote_id;

  const { data: items, error: itemsErr } = await supabase
    .from("invoice_items")
    .select("brand")
    .eq("invoice_id", invoiceId);
  if (itemsErr) {
    console.error("[notifyInvoiceSentForKanban] items lookup failed", itemsErr);
    return { advancedSlices: [] };
  }

  const brands = Array.from(
    new Set(
      ((items ?? []) as Array<{ brand: string | null }>).map(
        (it) => it.brand ?? ""
      )
    )
  );
  if (brands.length === 0) return { advancedSlices: [] };

  const res = await maybeAdvanceBrandSlices({
    trigger: "send",
    slices: brands.map((b) => ({ quote_id: quoteId, brand: b })),
    userId: user.id,
  });

  revalidatePath("/procurement/kanban");
  return { advancedSlices: res.advanced };
}

/**
 * Phase C trigger: called from the КП card right after the user clicks
 * «Завершить закупку по КП». Per requirement, advances `waiting_prices`
 * → `prices_ready` ONLY when every non-unavailable quote_item of the
 * (quote, brand) is now covered by at least one procurement-completed
 * invoice. Gate evaluated inside the helper.
 *
 * Best-effort — failures swallowed so the completion path itself isn't
 * broken.
 */
export async function notifyInvoiceCompletedForKanban(
  invoiceId: string
): Promise<{
  advancedSlices: Array<{ quote_id: string; brand: string; to: string }>;
}> {
  const user = await getSessionUser();
  if (!user?.orgId) return { advancedSlices: [] };

  const supabase = createAdminClient();

  const { data: invoice, error: invErr } = await supabase
    .from("invoices")
    .select("quote_id")
    .eq("id", invoiceId)
    .maybeSingle();
  if (invErr || !invoice) {
    console.error(
      "[notifyInvoiceCompletedForKanban] invoice lookup failed",
      invErr
    );
    return { advancedSlices: [] };
  }
  const quoteId = (invoice as { quote_id: string }).quote_id;

  const { data: items, error: itemsErr } = await supabase
    .from("invoice_items")
    .select("brand")
    .eq("invoice_id", invoiceId);
  if (itemsErr) {
    console.error(
      "[notifyInvoiceCompletedForKanban] items lookup failed",
      itemsErr
    );
    return { advancedSlices: [] };
  }

  const brands = Array.from(
    new Set(
      ((items ?? []) as Array<{ brand: string | null }>).map(
        (it) => it.brand ?? ""
      )
    )
  );
  if (brands.length === 0) return { advancedSlices: [] };

  const res = await maybeAdvanceBrandSlices({
    trigger: "procurement_complete",
    slices: brands.map((b) => ({ quote_id: quoteId, brand: b })),
    userId: user.id,
  });

  revalidatePath("/procurement/kanban");
  return { advancedSlices: res.advanced };
}
