import { createClient } from "@/shared/lib/supabase/client";

export async function updateUserRoles(
  userId: string,
  orgId: string,
  roleSlugs: string[]
): Promise<void> {
  const supabase = createClient();

  // 1. Look up role IDs by slug
  const { data: roles, error: rolesError } = await supabase
    .from("roles")
    .select("id, slug")
    .in("slug", roleSlugs);

  if (rolesError) throw rolesError;
  if (!roles || roles.length === 0) {
    throw new Error("No matching roles found");
  }

  // 2. Delete existing user_roles for this user in this org
  const { error: deleteError } = await supabase
    .from("user_roles")
    .delete()
    .eq("user_id", userId)
    .eq("organization_id", orgId);

  if (deleteError) throw deleteError;

  // 3. Insert new roles
  const inserts = roles.map((role) => ({
    user_id: userId,
    role_id: role.id,
    organization_id: orgId,
  }));

  const { error: insertError } = await supabase
    .from("user_roles")
    .insert(inserts);

  if (insertError) throw insertError;
}

export async function updateFeedbackStatus(
  shortId: string,
  status: string
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("user_feedback")
    .update({ status, updated_at: new Date().toISOString() })
    .eq("short_id", shortId);

  if (error) throw new Error(error.message);
}
