"use server";

import { createAdminClient } from "@/shared/lib/supabase/server";

/**
 * Kanban auto-advance — best-effort helper that promotes (quote, brand)
 * brand-slices on the procurement kanban when the gating condition for a
 * given user action holds.
 *
 * Wired into existing Server Actions / mutations: `assignBrandGroup`
 * (distribution), the «отправить КП» send path, and
 * `completeInvoiceProcurement`. Failures are logged and swallowed so they
 * never roll back the originating action.
 *
 * Idempotent — UPDATE WHERE substatus = '<expected>' guarantees that a
 * second invocation against an already-advanced slice is a no-op.
 */

export type AdvanceTrigger =
  | "distribution"
  | "send"
  | "procurement_complete";

export interface AdvanceSlice {
  quote_id: string;
  /** Empty string for unbranded items — matches DB representation. */
  brand: string;
}

export interface AdvanceArgs {
  trigger: AdvanceTrigger;
  slices: AdvanceSlice[];
  /** auth.uid() of the caller — recorded in status_history.transitioned_by. */
  userId: string;
}

export interface AdvanceResult {
  advanced: Array<{ quote_id: string; brand: string; to: string }>;
}

interface TransitionRule {
  from: string;
  to: string;
  reason: string;
}

const RULES: Record<AdvanceTrigger, TransitionRule> = {
  distribution: {
    from: "distributing",
    to: "searching_supplier",
    reason: "auto: all items routed",
  },
  send: {
    from: "searching_supplier",
    to: "waiting_prices",
    reason: "auto: КП sent to supplier",
  },
  procurement_complete: {
    from: "waiting_prices",
    to: "prices_ready",
    reason: "auto: КП procurement completed",
  },
};

/**
 * Evaluate the trigger-specific gate. Returns true when the slice is
 * eligible to advance (current substatus already verified by the caller).
 *
 * - `distribution`: all items of (quote, brand) are routed (МОЗ-assigned
 *   or marked unavailable).
 * - `send`: no extra gate — the user's send action IS the trigger.
 * - `procurement_complete`: all non-unavailable items of (quote, brand)
 *   are covered by at least one invoice_item belonging to an invoice with
 *   procurement_completed_at IS NOT NULL.
 */
async function evaluateGate(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  admin: any,
  trigger: AdvanceTrigger,
  slice: AdvanceSlice
): Promise<boolean> {
  if (trigger === "send") return true;

  if (trigger === "distribution") {
    const { data, error } = await admin
      .from("quote_items")
      .select("id, assigned_procurement_user, is_unavailable, brand")
      .eq("quote_id", slice.quote_id);
    if (error) {
      console.error("[kanban-auto-advance] gate fetch failed", error);
      return false;
    }
    const items = (data ?? []).filter(
      (it: { brand: string | null }) => (it.brand ?? "") === slice.brand
    );
    if (items.length === 0) return false;
    return items.every(
      (it: { assigned_procurement_user: string | null; is_unavailable: boolean | null }) =>
        it.assigned_procurement_user != null || it.is_unavailable === true
    );
  }

  // procurement_complete: every non-unavailable quote_item of (q, b) is
  // covered by ≥1 invoice_item belonging to a procurement-completed invoice.
  const { data: items, error: itemsErr } = await admin
    .from("quote_items")
    .select("id, brand, is_unavailable")
    .eq("quote_id", slice.quote_id);
  if (itemsErr) {
    console.error("[kanban-auto-advance] gate items fetch failed", itemsErr);
    return false;
  }
  const requiredItemIds = (items ?? [])
    .filter(
      (it: { brand: string | null; is_unavailable: boolean | null }) =>
        (it.brand ?? "") === slice.brand && it.is_unavailable !== true
    )
    .map((it: { id: string }) => it.id);
  if (requiredItemIds.length === 0) return false;

  const { data: cov, error: covErr } = await admin
    .from("invoice_item_coverage")
    .select(
      "quote_item_id, invoice_items!inner(invoice_id, invoices!inner(procurement_completed_at))"
    )
    .in("quote_item_id", requiredItemIds);
  if (covErr) {
    console.error("[kanban-auto-advance] coverage fetch failed", covErr);
    return false;
  }

  const coveredQiIds = new Set<string>();
  for (const row of (cov ?? []) as unknown as Array<{
    quote_item_id: string;
    invoice_items: { invoices: { procurement_completed_at: string | null } };
  }>) {
    const completed = row.invoice_items?.invoices?.procurement_completed_at;
    if (completed) coveredQiIds.add(row.quote_item_id);
  }

  return requiredItemIds.every((id: string) => coveredQiIds.has(id));
}

export async function maybeAdvanceBrandSlices(
  args: AdvanceArgs
): Promise<AdvanceResult> {
  const advanced: AdvanceResult["advanced"] = [];
  if (args.slices.length === 0) return { advanced };

  let admin;
  try {
    admin = createAdminClient();
  } catch (err) {
    console.error("[kanban-auto-advance] admin client unavailable", err);
    return { advanced };
  }

  const rule = RULES[args.trigger];

  // Dedupe slices to avoid double-processing.
  const seen = new Set<string>();
  const uniqueSlices = args.slices.filter((s) => {
    const k = `${s.quote_id}|${s.brand}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });

  for (const slice of uniqueSlices) {
    try {
      // Read current substatus — bail if not in the expected state.
      const { data: current, error: readErr } = await admin
        .from("quote_brand_substates")
        .select("substatus")
        .eq("quote_id", slice.quote_id)
        .eq("brand", slice.brand)
        .maybeSingle();
      if (readErr || !current) continue;
      if ((current as { substatus: string }).substatus !== rule.from) continue;

      const gateOk = await evaluateGate(admin, args.trigger, slice);
      if (!gateOk) continue;

      // Conditional UPDATE — second concurrent caller will affect 0 rows
      // and silently move on (Req 5.3 idempotency).
      const { data: updated, error: updErr } = await admin
        .from("quote_brand_substates")
        .update({
          substatus: rule.to,
          updated_at: new Date().toISOString(),
          updated_by: args.userId,
        })
        .eq("quote_id", slice.quote_id)
        .eq("brand", slice.brand)
        .eq("substatus", rule.from)
        .select("quote_id, brand, substatus");
      if (updErr) {
        console.error("[kanban-auto-advance] update failed", updErr);
        continue;
      }
      const rows = (updated ?? []) as Array<{
        quote_id: string;
        brand: string;
        substatus: string;
      }>;
      if (rows.length === 0) continue;

      // Append status_history audit row. Failure here is logged but the
      // substatus update has already landed — partial state acceptable.
      const { error: histErr } = await admin.from("status_history").insert({
        quote_id: slice.quote_id,
        brand: slice.brand,
        from_status: "pending_procurement",
        from_substatus: rule.from,
        to_status: "pending_procurement",
        to_substatus: rule.to,
        transitioned_by: args.userId,
        reason: rule.reason,
      });
      if (histErr) {
        console.error("[kanban-auto-advance] history insert failed", histErr);
      }

      advanced.push({
        quote_id: slice.quote_id,
        brand: slice.brand,
        to: rule.to,
      });
    } catch (err) {
      console.error("[kanban-auto-advance] slice processing crashed", err);
      // Swallow per Req 5.2.
    }
  }

  return { advanced };
}
