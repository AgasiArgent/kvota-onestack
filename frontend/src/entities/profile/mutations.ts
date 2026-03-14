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
