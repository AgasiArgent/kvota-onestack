import { createClient } from "@/shared/lib/supabase/server";
import type { TrainingVideo } from "./types";

/**
 * Fetch active training videos for an organization.
 * Optionally filter by category. Ordered by sort_order asc, created_at desc.
 */
export async function fetchTrainingVideos(
  orgId: string,
  category?: string
): Promise<TrainingVideo[]> {
  const supabase = await createClient();

  let query = supabase
    .from("training_videos")
    .select(
      "id, organization_id, title, description, youtube_id, category, platform, thumbnail_url, sort_order, is_active, created_by, created_at, updated_at"
    )
    .eq("organization_id", orgId)
    .eq("is_active", true)
    .order("sort_order", { ascending: true })
    .order("created_at", { ascending: false });

  if (category) {
    query = query.eq("category", category);
  }

  const { data, error } = await query;
  if (error) throw error;

  const rows = data ?? [];

  // Batch-resolve creator names
  const creatorIds = Array.from(
    new Set(
      rows.map((r) => r.created_by).filter((id): id is string => id !== null)
    )
  );

  let creatorMap = new Map<string, { full_name: string | null }>();
  if (creatorIds.length > 0) {
    const { data: profiles, error: profilesError } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", creatorIds);

    if (!profilesError && profiles) {
      creatorMap = new Map(
        profiles.map((p) => [p.user_id, { full_name: p.full_name }])
      );
    }
  }

  return rows.map((row) => ({
    id: row.id,
    organization_id: row.organization_id,
    title: row.title,
    description: row.description,
    youtube_id: row.youtube_id,
    category: row.category,
    platform: (["rutube", "youtube", "loom"].includes(row.platform) ? row.platform : "rutube") as TrainingVideo["platform"],
    thumbnail_url: row.thumbnail_url,
    sort_order: row.sort_order,
    is_active: row.is_active,
    created_by: row.created_by,
    created_at: row.created_at,
    updated_at: row.updated_at,
    creator: row.created_by ? creatorMap.get(row.created_by) ?? null : null,
  }));
}

/**
 * Fetch distinct categories from active training videos.
 */
export async function fetchCategories(orgId: string): Promise<string[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("training_videos")
    .select("category")
    .eq("organization_id", orgId)
    .eq("is_active", true);

  if (error) throw error;

  const categories = Array.from(
    new Set((data ?? []).map((row) => row.category))
  );

  return categories.sort((a, b) => a.localeCompare(b, "ru"));
}
