// @ts-nocheck
/**
 * Workspace invoice queries (logistics + customs workspace pages).
 *
 * ⚠️ STATUS: schema-rewrite pending.
 *
 * Claude Design authored these queries against a speculative schema that
 * doesn't match reality:
 *   - kvota.invoices has no `org_id` / `organization_id` — org is resolved
 *     via quote_id → quotes.organization_id
 *   - Fields `idn`, `items_count`, `hs_codes_filled`, `hs_codes_total`,
 *     `licenses_required`, `delivery_country`, `delivery_city` do NOT exist
 *     on kvota.invoices (delivery_* live on quotes; counts need aggregation
 *     from quote_items)
 *   - `kvota.users` table does not exist (user lookup must go through
 *     auth.admin.getUserById)
 *
 * Rewriting against the real schema is a standalone refactor (quote_id
 * subquery or `!inner` embed, aggregated counts via RPC or separate query,
 * user display info via auth admin API). Until then, these functions
 * return empty lists so the `/workspace/{logistics,customs}` pages render
 * an empty state instead of crashing with 500.
 *
 * `fetchTeamUsers` works correctly because it uses user_roles +
 * auth.admin.getUserById — that is the real-schema path.
 */

import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  WorkspaceInvoiceRow,
} from "@/features/workspace-logistics/ui/workspace-invoices-table";
import type { UnassignedInvoiceRow } from "@/features/workspace-logistics/ui/unassigned-inbox";
import type { UserAvatarChipUser } from "@/entities/user";

type Domain = "logistics" | "customs";

/**
 * Stub — returns []. Schema rewrite TODO.
 */
export async function fetchMyAssignedInvoices(
  _domain: Domain,
  _userId: string,
  _orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  return [];
}

/**
 * Stub — returns []. Schema rewrite TODO.
 */
export async function fetchMyCompletedInvoices(
  _domain: Domain,
  _userId: string,
  _orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  return [];
}

/**
 * Stub — returns []. Schema rewrite TODO. head_of_* users will see an
 * empty "Неназначенные" inbox until rewrite.
 */
export async function fetchUnassignedInvoices(
  _domain: Domain,
  _orgId: string,
): Promise<UnassignedInvoiceRow[]> {
  return [];
}

/**
 * Stub — returns []. Schema rewrite TODO.
 */
export async function fetchAllActiveInvoices(
  _domain: Domain,
  _orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  return [];
}

/**
 * fetchTeamUsers — real implementation.
 * Resolves users with the given role in org via user_roles + auth admin API.
 */
export async function fetchTeamUsers(
  domain: Domain,
  orgId: string,
): Promise<UserAvatarChipUser[]> {
  const admin = createAdminClient();
  const roleSlug = domain === "logistics" ? "logistics" : "customs";

  const { data: memberships, error: rolesErr } = await admin
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId)
    .eq("roles.slug", roleSlug);

  if (rolesErr) {
    // Fail soft — log and return empty list so UI doesn't explode.
    console.error("fetchTeamUsers: user_roles query failed", rolesErr);
    return [];
  }

  const userIds = Array.from(
    new Set((memberships ?? []).map((m) => m.user_id as string))
  );
  if (userIds.length === 0) return [];

  const profiles = await Promise.all(
    userIds.map(async (uid) => {
      try {
        const { data } = await admin.auth.admin.getUserById(uid);
        const u = data?.user;
        if (!u) return null;
        const meta = (u.user_metadata ?? {}) as Record<string, unknown>;
        return {
          id: u.id,
          name:
            (meta.full_name as string) ||
            (meta.name as string) ||
            u.email ||
            "—",
          email: u.email ?? undefined,
          avatarUrl:
            ((meta.avatar_url as string) || null) ?? undefined,
        } satisfies UserAvatarChipUser;
      } catch {
        return null;
      }
    })
  );

  return profiles.filter((p): p is UserAvatarChipUser => p !== null);
}

/**
 * Stub — returns null-ish stats. Schema rewrite TODO.
 */
export async function fetchWorkspaceStats(
  _domain: Domain,
  _orgId: string,
): Promise<{
  active: number;
  overdue: number;
  completedThisWeek: number;
  avgSlaHours: number;
}> {
  return {
    active: 0,
    overdue: 0,
    completedThisWeek: 0,
    avgSlaHours: 0,
  };
}
