import { createClient, createAdminClient } from "@/shared/lib/supabase/server";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import { ROLE_LABELS_RU } from "./types";

export async function fetchUserSalesGroupId(
  userId: string,
  orgId: string
): Promise<string | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("user_profiles")
    .select("sales_group_id")
    .eq("user_id", userId)
    .eq("organization_id", orgId)
    .maybeSingle();
  return data?.sales_group_id ?? null;
}

export interface UserDepartment {
  roles: Array<{ name: string; slug: string }>;
  supervisor: { full_name: string } | null;
}

export async function fetchUserDepartment(
  userId: string,
  orgId: string
): Promise<UserDepartment> {
  const supabase = await createClient();

  // Fetch roles
  const { data: roleRows } = await supabase
    .from("user_roles")
    .select("roles!inner(name, slug)")
    .eq("user_id", userId)
    .eq("organization_id", orgId);

  const roles = (roleRows ?? []).map((row) => {
    const r = row.roles as unknown as { name: string; slug: string };
    return {
      name: ROLE_LABELS_RU[r.slug] ?? r.name,
      slug: r.slug,
    };
  });

  // Fetch supervisor from organization_members (supervisor_id not in generated types yet)
  const { data: membership } = await supabase
    .from("organization_members")
    .select("supervisor_id" as string)
    .eq("user_id", userId)
    .eq("organization_id", orgId)
    .maybeSingle();

  let supervisor: { full_name: string } | null = null;
  const supervisorId = (membership as Record<string, unknown> | null)?.supervisor_id as string | null;
  if (supervisorId) {
    const { data: supProfile } = await supabase
      .from("user_profiles")
      .select("full_name")
      .eq("user_id", supervisorId)
      .eq("organization_id", orgId)
      .maybeSingle();

    if (supProfile?.full_name) {
      supervisor = { full_name: supProfile.full_name };
    }
  }

  return { roles, supervisor };
}

/**
 * Returns procurement users in the org with their current workload (count of
 * distinct active quotes they own items in). Shared by the distribution page
 * and the kanban assign popover.
 */
export async function fetchProcurementWorkload(
  orgId: string
): Promise<ProcurementUserWorkload[]> {
  const supabase = createAdminClient();

  // 1. Find all procurement users
  const { data: roleRows } = await supabase
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId);

  const procUserIds = new Set<string>();
  for (const row of roleRows ?? []) {
    const role = row.roles as unknown as { slug: string } | null;
    const slug = role?.slug;
    if (
      slug === "procurement" ||
      slug === "procurement_senior" ||
      slug === "head_of_procurement"
    ) {
      procUserIds.add(row.user_id);
    }
  }

  if (procUserIds.size === 0) return [];

  const userIdArr = [...procUserIds];

  // 2. Fetch profiles
  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .eq("organization_id", orgId)
    .in("user_id", userIdArr);

  const profileMap = new Map<string, string | null>();
  for (const p of profiles ?? []) {
    profileMap.set(p.user_id, p.full_name);
  }

  // 3. Count active quotes (not items) per user
  const { data: countRows } = await supabase
    .from("quote_items")
    .select("assigned_procurement_user, quote_id")
    .in("assigned_procurement_user", userIdArr)
    .in("procurement_status", ["pending", "in_progress"]);

  // Filter to non-deleted quotes
  const activeQuoteIds = new Set<string>();
  if (countRows && countRows.length > 0) {
    const qIds = [...new Set(countRows.map((r) => r.quote_id))];
    const { data: activeQuotes } = await supabase
      .from("quotes")
      .select("id")
      .in("id", qIds)
      .is("deleted_at", null);
    for (const q of activeQuotes ?? []) {
      activeQuoteIds.add(q.id);
    }
  }

  // Count unique quote_ids per user (not individual items)
  const quotesPerUser = new Map<string, Set<string>>();
  for (const row of countRows ?? []) {
    if (!activeQuoteIds.has(row.quote_id)) continue;
    const uid = row.assigned_procurement_user;
    if (uid) {
      const quotes = quotesPerUser.get(uid) ?? new Set();
      quotes.add(row.quote_id);
      quotesPerUser.set(uid, quotes);
    }
  }

  return userIdArr.map((uid) => ({
    user_id: uid,
    full_name: profileMap.get(uid) ?? null,
    active_quotes: quotesPerUser.get(uid)?.size ?? 0,
  }));
}
