import { createAdminClient } from "@/shared/lib/supabase/server";
import type { OrgMember, RoleOption, FeedbackItem, FeedbackDetail } from "./types";

export async function fetchOrgMembers(
  orgId: string,
  search?: string
): Promise<OrgMember[]> {
  const admin = createAdminClient();

  // 1. Fetch all organization members (active + suspended)
  const { data: members, error: membersError } = await admin
    .from("organization_members")
    .select("user_id, created_at, status")
    .eq("organization_id", orgId)
    .in("status", ["active", "suspended"]);

  if (membersError) throw membersError;
  if (!members || members.length === 0) return [];

  const userIds = members.map((m) => m.user_id);

  // 2. Batch-fetch profiles, roles, telegram in parallel
  const [profilesResult, rolesResult, telegramResult] =
    await Promise.all([
      admin
        .from("user_profiles")
        .select("user_id, full_name, position, sales_group_id, department_id")
        .in("user_id", userIds),
      admin
        .from("user_roles")
        .select("user_id, role_id, roles(id, slug, name)")
        .eq("organization_id", orgId)
        .in("user_id", userIds),
      admin
        .from("telegram_users")
        .select("user_id, telegram_username")
        .in("user_id", userIds),
    ]);

  if (profilesResult.error) throw profilesResult.error;
  if (rolesResult.error) throw rolesResult.error;
  if (telegramResult.error)
    console.error("Failed to fetch telegram users:", telegramResult.error);

  // Fetch emails via Supabase Auth Admin API (auth.users not accessible via PostgREST)
  const { data: authData } = await admin.auth.admin.listUsers({ perPage: 1000 });
  const authUsers = authData?.users ?? [];

  // Build lookup maps
  interface ProfileData {
    full_name: string | null;
    position: string | null;
    sales_group_id: string | null;
    department_id: string | null;
  }
  const profileMap = new Map<string, ProfileData>(
    (profilesResult.data ?? []).map((p) => [
      p.user_id,
      {
        full_name: p.full_name as string | null,
        position: (p as Record<string, unknown>).position as string | null,
        sales_group_id: (p as Record<string, unknown>).sales_group_id as string | null,
        department_id: (p as Record<string, unknown>).department_id as string | null,
      },
    ])
  );
  const emailMap = new Map(
    authUsers.map((u) => [u.id, u.email ?? ""])
  );
  const telegramMap = new Map<string, string | null>(
    (telegramResult.data ?? []).map((t) => [t.user_id, t.telegram_username as string | null])
  );

  // Group roles by user_id
  const rolesMap = new Map<string, { id: string; slug: string; name: string }[]>();
  for (const ur of rolesResult.data ?? []) {
    const role = ur.roles as unknown as { id: string; slug: string; name: string } | null;
    if (!role) continue;
    const existing = rolesMap.get(ur.user_id) ?? [];
    existing.push({ id: role.id, slug: role.slug, name: role.name });
    rolesMap.set(ur.user_id, existing);
  }

  // Build member objects
  const joinedMap = new Map(
    members.map((m) => [m.user_id, m.created_at])
  );
  const statusMap = new Map(
    members.map((m) => [m.user_id, (m.status ?? "active") as "active" | "suspended"])
  );

  // Count total admins for last-admin guard
  let adminCount = 0;
  for (const [, roles] of rolesMap) {
    if (roles.some((r) => r.slug === "admin")) {
      adminCount++;
    }
  }

  let result: OrgMember[] = userIds.map((uid) => {
    const profile = profileMap.get(uid);
    const userRoles = rolesMap.get(uid) ?? [];
    const isAdmin = userRoles.some((r) => r.slug === "admin");

    return {
      user_id: uid,
      full_name: profile?.full_name ?? null,
      email: emailMap.get(uid) ?? "",
      roles: userRoles,
      telegram_username: telegramMap.get(uid) ?? null,
      joined_at: joinedMap.get(uid) ?? "",
      status: statusMap.get(uid) ?? "active",
      position: profile?.position ?? null,
      sales_group_id: profile?.sales_group_id ?? null,
      department_id: profile?.department_id ?? null,
      is_last_admin: isAdmin && adminCount === 1,
    };
  });

  // Apply search filter (client-side — small dataset <50 users)
  if (search) {
    const q = search.toLowerCase();
    result = result.filter(
      (m) =>
        (m.full_name?.toLowerCase().includes(q) ?? false) ||
        m.email.toLowerCase().includes(q)
    );
  }

  // Sort by full_name
  result.sort((a, b) =>
    (a.full_name ?? "").localeCompare(b.full_name ?? "", "ru")
  );

  return result;
}

export async function fetchAllRoles(orgId: string): Promise<RoleOption[]> {
  const admin = createAdminClient();

  // Fetch roles that are used by the organization (via user_roles)
  // Then also fetch all system roles for the org
  const { data, error } = await admin
    .from("roles")
    .select("id, slug, name")
    .order("name");

  if (error) throw error;

  // Filter to active roles only (exclude deprecated/system-only)
  const activeSlugs = new Set([
    "admin",
    "sales",
    "procurement",
    "procurement_senior",
    "logistics",
    "customs",
    "quote_controller",
    "spec_controller",
    "finance",
    "top_manager",
    "head_of_sales",
    "head_of_procurement",
    "head_of_logistics",
  ]);

  return (data ?? [])
    .filter((r) => activeSlugs.has(r.slug))
    .map((r) => ({ id: r.id, slug: r.slug, name: r.name }));
}

export async function fetchSalesGroups(): Promise<
  { id: string; name: string }[]
> {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("sales_groups")
    .select("id, name")
    .order("name");

  if (error) throw error;
  return (data ?? []).map((g) => ({ id: g.id, name: g.name }));
}

export async function fetchDepartments(): Promise<
  { id: string; name: string }[]
> {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("departments")
    .select("id, name")
    .order("name");

  if (error) throw error;
  return (data ?? []).map((d) => ({ id: d.id, name: d.name }));
}

export async function fetchFeedbackList(
  orgId: string,
  status?: string,
  search?: string,
  page?: number,
  pageSize?: number
): Promise<{ data: FeedbackItem[]; total: number; page: number; pageSize: number }> {
  const admin = createAdminClient();
  const currentPage = page ?? 1;
  const validSizes = [25, 50, 100];
  const effectivePageSize = validSizes.includes(pageSize ?? 0)
    ? pageSize!
    : 50;
  const offset = (currentPage - 1) * effectivePageSize;

  let query = admin
    .from("user_feedback")
    .select(
      "short_id, feedback_type, description, user_name, user_email, status, clickup_task_id, created_at",
      { count: "exact" }
    )
    .eq("organization_id", orgId)
    .order("created_at", { ascending: false });

  if (status && status !== "all") {
    query = query.eq("status", status);
  }

  if (search) {
    query = query.or(
      `description.ilike.%${search}%,user_name.ilike.%${search}%,user_email.ilike.%${search}%,short_id.ilike.%${search}%`
    );
  }

  query = query.range(offset, offset + effectivePageSize - 1);

  const { data, count, error } = await query;
  if (error) throw error;

  const items: FeedbackItem[] = (data ?? []).map((row) => ({
    short_id: row.short_id ?? "",
    feedback_type: row.feedback_type as FeedbackItem["feedback_type"],
    description: row.description ?? "",
    user_name: row.user_name,
    user_email: row.user_email,
    status: row.status as FeedbackItem["status"],
    clickup_task_id: row.clickup_task_id,
    created_at: row.created_at ?? "",
  }));

  return {
    data: items,
    total: count ?? 0,
    page: currentPage,
    pageSize: effectivePageSize,
  };
}

export async function fetchFeedbackDetail(
  shortId: string,
  orgId: string
): Promise<FeedbackDetail | null> {
  const admin = createAdminClient();

  const { data, error } = await admin
    .from("user_feedback")
    .select(
      "short_id, feedback_type, description, user_name, user_email, status, clickup_task_id, created_at, page_url, screenshot_url, debug_context"
    )
    .eq("short_id", shortId)
    .eq("organization_id", orgId)
    .single();

  if (error) {
    if (error.code === "PGRST116") return null; // Not found
    throw error;
  }

  return {
    short_id: data.short_id ?? "",
    feedback_type: data.feedback_type as FeedbackDetail["feedback_type"],
    description: data.description ?? "",
    user_name: data.user_name,
    user_email: data.user_email,
    status: data.status as FeedbackDetail["status"],
    clickup_task_id: data.clickup_task_id,
    created_at: data.created_at ?? "",
    page_url: data.page_url,
    screenshot_url: data.screenshot_url,
    debug_context: data.debug_context as Record<string, unknown> | null,
  };
}
