import { createClient } from "@/shared/lib/supabase/client";

export async function markChangelogRead(): Promise<void> {
  const supabase = createClient();
  const {
    data: { user },
    error: authError,
  } = await supabase.auth.getUser();

  if (authError || !user) {
    return;
  }

  const today = new Date().toISOString().split("T")[0];

  await supabase.from("changelog_reads").upsert({
    user_id: user.id,
    last_read_date: today,
    last_read_at: new Date().toISOString(),
  });
}
