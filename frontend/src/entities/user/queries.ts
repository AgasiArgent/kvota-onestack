import { createClient } from "@/shared/lib/supabase/server";
import { ROLE_LABELS_RU } from "./types";

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
