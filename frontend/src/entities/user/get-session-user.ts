import { createClient } from "@/shared/lib/supabase/server";
import type { SessionUser } from "./types";
import { ACTIVE_ROLES } from "./types";

export async function getSessionUser(): Promise<SessionUser | null> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  // Get organization membership
  const { data: orgMembers } = await supabase
    .from("organization_members")
    .select("organization_id, organizations(id, name)")
    .eq("user_id", user.id)
    .eq("status", "active")
    .limit(1);

  const orgData = orgMembers?.[0];
  const orgId = orgData?.organization_id ?? null;
  const org = orgData?.organizations as unknown as { name: string } | null;
  const orgName = org?.name ?? "No Organization";

  // Get user roles
  let roles: string[] = [];
  if (orgId) {
    const { data: userRoles } = await supabase
      .from("user_roles")
      .select("roles(slug)")
      .eq("user_id", user.id)
      .eq("organization_id", orgId);

    roles = (userRoles ?? [])
      .map((ur) => (ur.roles as unknown as { slug: string } | null)?.slug)
      .filter((slug): slug is string => slug !== null && slug !== undefined);

    // training_manager gets all roles (super-role for demos)
    if (roles.includes("training_manager")) {
      roles = [...new Set([...roles, ...ACTIVE_ROLES, "training_manager"])];
    }
  }

  return {
    id: user.id,
    email: user.email ?? "",
    orgId,
    orgName,
    roles,
  };
}
