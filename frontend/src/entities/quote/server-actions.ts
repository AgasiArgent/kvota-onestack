"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";
import { getSessionUser } from "@/entities/user";
import { revalidatePath } from "next/cache";
import { maybeAdvanceBrandSlices } from "./kanban-auto-advance";

/**
 * Roles allowed to edit `sales_checklist.distribution_comment` after the
 * quote has already been transferred to procurement. Mirrors the sales-tier
 * gate used elsewhere on the quote (`canEditQuoteCustomerFields`) plus admin
 * for ops overrides.
 *
 * Testing 2 row 61: МОП / РОП requested inline edit on the sales step + edit
 * affordance on the context panel once the modal is no longer reachable. Other
 * roles (МОЗ / МОЛ / МОТ / финансы и т.д.) remain read-only on this field.
 */
const DISTRIBUTION_COMMENT_EDIT_ROLES = new Set([
  "admin",
  "sales",
  "head_of_sales",
]);

/**
 * Update the optional `sales_checklist.distribution_comment` JSONB field on a
 * quote without disturbing the rest of the checklist payload.
 *
 * Testing 2 row 61: МОП / РОП previously only had access to this field via
 * the «Передать в закупки» modal — invisible once the quote leaves the draft
 * stage, and easy to miss in the modal itself (buried below a mandatory
 * textarea). This action powers both the inline editor on the sales step and
 * the edit affordance on the context-panel sales-checklist block.
 *
 * Whitespace-only input is normalised to `null` so the JSONB shape stays
 * clean (matches the back-end normalisation in
 * `api/quotes.py::submit_procurement`).
 *
 * Server Action — called from client components on the quote detail page.
 * Authorization is enforced server-side: only admin / sales / head_of_sales
 * may write this field; the underlying RLS UPDATE policy on `kvota.quotes`
 * is the canonical enforcement layer.
 */
export async function updateDistributionComment(
  quoteId: string,
  comment: string | null,
): Promise<{ success: boolean; error?: string; value: string | null }> {
  const user = await getSessionUser();
  if (!user?.orgId) {
    return { success: false, error: "Not authenticated", value: null };
  }

  const allowed = user.roles.some((r) => DISTRIBUTION_COMMENT_EDIT_ROLES.has(r));
  if (!allowed) {
    return { success: false, error: "Not authorized", value: null };
  }

  const trimmed =
    typeof comment === "string" && comment.trim().length > 0
      ? comment.trim()
      : null;

  const supabase = createAdminClient();

  // Read-modify-write the JSONB so we only touch `distribution_comment` and
  // preserve every other key МОП already filled (is_estimate / is_tender /
  // direct_request / trading_org_request / equipment_description /
  // completed_at / completed_by). A bare UPDATE with `{distribution_comment}`
  // would overwrite the entire JSONB.
  const { data: row, error: readErr } = await supabase
    .from("quotes")
    .select("sales_checklist")
    .eq("id", quoteId)
    .eq("organization_id", user.orgId)
    .maybeSingle();
  if (readErr) {
    return { success: false, error: readErr.message, value: null };
  }
  if (!row) {
    return { success: false, error: "Quote not found", value: null };
  }

  const existing =
    (row.sales_checklist as Record<string, unknown> | null) ?? {};
  const next = { ...existing, distribution_comment: trimmed };

  const { error: updateErr } = await supabase
    .from("quotes")
    .update({ sales_checklist: next })
    .eq("id", quoteId)
    .eq("organization_id", user.orgId);
  if (updateErr) {
    return { success: false, error: updateErr.message, value: null };
  }

  // Revalidate the quote detail page so a fresh server render picks up the
  // new value (the inline editor itself is controlled and already in sync).
  revalidatePath(`/quotes/${quoteId}`);
  return { success: true, value: trimmed };
}

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
 *
 * Testing 2 row 75 v2: regular `procurement` (МОЗ) is now allowed too — they
 * cover for each other when someone is out. RLS on `kvota.quote_items`
 * scopes МОЗ to slices they're already assigned to, so they cannot
 * accidentally grief other people's work.
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
    user.roles.includes("procurement_senior") ||
    user.roles.includes("procurement");
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
