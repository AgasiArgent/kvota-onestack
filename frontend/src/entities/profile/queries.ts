import { createClient } from "@/shared/lib/supabase/server";
import type { UserProfile } from "./types";

export async function fetchCurrentUserProfile(): Promise<UserProfile | null> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const { data, error } = await supabase
    .from("user_profiles")
    .select("*")
    .eq("user_id", user.id)
    .single();

  if (error) return null;

  return data as UserProfile;
}
