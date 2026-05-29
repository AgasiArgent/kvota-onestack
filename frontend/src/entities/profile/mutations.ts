import { createClient } from "@/shared/lib/supabase/client";
import type { ProfileFormData } from "./types";

export async function updateProfile(
  profileId: string,
  data: ProfileFormData
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("user_profiles")
    .update(data)
    .eq("id", profileId);

  if (error) throw error;
}

/**
 * Self-service password change. Re-verifies the current password (Supabase has
 * no dedicated "verify password" call) before setting the new one. Supabase
 * returns a fresh session, so the user stays logged in.
 */
export async function changePassword(
  email: string,
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const supabase = createClient();

  const { error: verifyError } = await supabase.auth.signInWithPassword({
    email,
    password: currentPassword,
  });
  if (verifyError) {
    throw new Error("CURRENT_PASSWORD_INVALID");
  }

  const { error: updateError } = await supabase.auth.updateUser({
    password: newPassword,
  });
  if (updateError) throw updateError;
}
