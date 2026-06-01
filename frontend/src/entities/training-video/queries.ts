import { createClient } from "@/shared/lib/supabase/server";
import { isTrainingMaterialVisible } from "@/shared/lib/roles";
import type { TrainingVideo } from "./types";

/**
 * Fetch active training videos for an organization, filtered by the viewer's
 * department + role visibility (Testing 2 row 54).
 *
 * A material is returned when its visibility allow-lists are empty (visible to
 * everyone) OR the viewer's department / role matches. When `userRoles` is
 * omitted (e.g. admin editor preview), no visibility filter is applied — all
 * active materials are returned. Filtering happens on the data path here, not
 * just hidden in the UI.
 *
 * Optionally filter by category. Ordered by sort_order asc, created_at desc.
 */
export async function fetchTrainingVideos(
  orgId: string,
  category?: string,
  userRoles?: readonly string[]
): Promise<TrainingVideo[]> {
  const supabase = await createClient();

  let query = supabase
    .from("training_videos")
    .select(
      "id, organization_id, title, description, youtube_id, category, platform, thumbnail_url, sort_order, is_active, visible_departments, visible_role_slugs, created_by, created_at, updated_at"
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

  const allRows = data ?? [];

  // Department + role visibility filter. Skipped when userRoles is undefined
  // (admin editor / unrestricted contexts pass no roles).
  const rows =
    userRoles === undefined
      ? allRows
      : allRows.filter((row) =>
          isTrainingMaterialVisible(
            row.visible_departments ?? [],
            row.visible_role_slugs ?? [],
            userRoles
          )
        );

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
    visible_departments: row.visible_departments ?? [],
    visible_role_slugs: row.visible_role_slugs ?? [],
    created_by: row.created_by,
    created_at: row.created_at,
    updated_at: row.updated_at,
    creator: row.created_by ? creatorMap.get(row.created_by) ?? null : null,
  }));
}

/**
 * Fetch distinct categories from active training videos.
 *
 * When `userRoles` is provided, only categories the viewer can actually see
 * (per department + role visibility) are returned — so a viewer never gets a
 * category tab whose only materials are hidden from them. When omitted, all
 * active categories are returned (admin editor context).
 */
export async function fetchCategories(
  orgId: string,
  userRoles?: readonly string[]
): Promise<string[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("training_videos")
    .select("category, visible_departments, visible_role_slugs")
    .eq("organization_id", orgId)
    .eq("is_active", true);

  if (error) throw error;

  const visibleRows =
    userRoles === undefined
      ? (data ?? [])
      : (data ?? []).filter((row) =>
          isTrainingMaterialVisible(
            row.visible_departments ?? [],
            row.visible_role_slugs ?? [],
            userRoles
          )
        );

  const categories = Array.from(
    new Set(visibleRows.map((row) => row.category))
  );

  return categories.sort((a, b) => a.localeCompare(b, "ru"));
}
