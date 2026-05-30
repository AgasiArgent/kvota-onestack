/**
 * Control-board fetcher (control-spec-workspace Req 9.2 / 9.3 / 9.5 / 9.6).
 *
 * Reads quotes sitting in the control gates and shapes them into clickable
 * kanban cards. Org-scoped: every query filters `organization_id` to the
 * caller's org (the service-role admin client bypasses RLS, so the explicit
 * org filter IS the access boundary here — same pattern as the approvals page
 * and the logistics/customs kanban fetcher).
 *
 * - calc domain  → pending_quote_control + pending_approval, controller =
 *   `quote_controller_id`.
 * - spec domain  → pending_spec_control + pending_signature, controller =
 *   `spec_controller_id`.
 *
 * Reads `total_quote_currency` (the canonical quote total written by the calc
 * engine — NOT the dropped `total_amount_quote`, NOT the deal-side
 * `total_amount`).
 */

import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { boardStatuses, type ControlBoardDomain } from "./model/types";
import type { ControlKanbanCard } from "./model/types";

/** Columns read off kvota.quotes for a control card. */
const QUOTE_COLUMNS = `
  id,
  idn_quote,
  workflow_status,
  total_quote_currency,
  currency,
  quote_controller_id,
  spec_controller_id,
  customer:customers!customer_id(id, name)
`;

interface QuoteRowRaw {
  id: string;
  idn_quote: string | null;
  workflow_status: string | null;
  total_quote_currency: number | null;
  currency: string | null;
  quote_controller_id: string | null;
  spec_controller_id: string | null;
  customer: { id: string; name: string | null } | null;
}

/**
 * Resolve ФИО for a set of user ids from `kvota.user_profiles.full_name` — the
 * same canonical name source the logistics/customs kanban and quotes-list chips
 * use (auth `user_metadata` is unreliable). Unresolved ids are simply absent
 * from the map; the card then shows `null`.
 */
async function fetchControllerNames(
  admin: ReturnType<typeof createAdminClient>,
  userIds: string[],
): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  const unique = Array.from(new Set(userIds.filter(Boolean)));
  if (unique.length === 0) return map;

  const { data, error } = await admin
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", unique);

  if (error) {
    console.error("fetchControllerNames: user_profiles query failed", error);
    return map;
  }

  for (const row of data ?? []) {
    const name = (row.full_name ?? "").trim();
    if (name) map.set(row.user_id, name);
  }
  return map;
}

/**
 * Fetch the control board for a domain — every quote currently sitting in one
 * of the domain's control gates, org-scoped, newest-first.
 *
 * Path: server-only (called from the /workspace/control server page).
 * Params:
 *   domain: 'calc' | 'spec' — which board to build.
 *   user: { id; roles; orgId } — the acting user (org scoping).
 * Returns: ControlKanbanCard[] — one card per quote.
 * Roles: quote_controller / spec_controller / admin / top_manager (gated by
 *   the page guard; this fetcher trusts its caller).
 */
export async function fetchControlBoard(
  domain: ControlBoardDomain,
  user: { id: string; roles: string[]; orgId: string },
): Promise<ControlKanbanCard[]> {
  const admin = createAdminClient();
  const statuses = boardStatuses(domain);

  const { data, error } = await admin
    .from("quotes")
    // Generated types lack FK-join relationship metadata, so the customer join
    // emits a SelectQueryError at the type level — runtime is correct.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(QUOTE_COLUMNS as any)
    .eq("organization_id", user.orgId)
    .is("deleted_at", null)
    .in("workflow_status", statuses as unknown as string[])
    .order("updated_at", { ascending: false });

  if (error) {
    console.error(`fetchControlBoard(${domain}): quotes query failed`, error);
    return [];
  }

  const rows = (data ?? []) as unknown as QuoteRowRaw[];
  if (rows.length === 0) return [];

  // The controller field is per-domain — calc reads quote_controller_id, spec
  // reads spec_controller_id.
  const controllerIdOf = (row: QuoteRowRaw): string | null =>
    domain === "calc" ? row.quote_controller_id : row.spec_controller_id;

  const controllerIds = rows
    .map(controllerIdOf)
    .filter((id): id is string => !!id);
  const nameById = await fetchControllerNames(admin, controllerIds);

  return rows.map((row) => {
    const controllerId = controllerIdOf(row);
    return {
      quoteId: row.id,
      idnQuote: row.idn_quote ?? row.id.slice(0, 8),
      customerName: row.customer?.name ?? "—",
      total: row.total_quote_currency,
      currency: row.currency ?? "USD",
      workflowStatus: row.workflow_status ?? "",
      controllerName: controllerId ? nameById.get(controllerId) ?? null : null,
    };
  });
}
