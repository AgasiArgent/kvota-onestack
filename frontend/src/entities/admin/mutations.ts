import { createClient } from "@/shared/lib/supabase/client";
import type { FeedbackDetail } from "./types";

/**
 * Update user profile fields directly via Supabase.
 * For single-table CRUD — no need for Python API.
 */
export async function updateUserProfile(
  userId: string,
  orgId: string,
  data: { full_name?: string; position?: string | null; sales_group_id?: string | null; department_id?: string | null }
) {
  const supabase = createClient();
  return supabase
    .from("user_profiles")
    .update(data)
    .eq("user_id", userId)
    .eq("organization_id", orgId);
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

export async function bulkUpdateFeedbackStatus(
  shortIds: string[],
  status: "new" | "in_progress" | "resolved" | "closed"
): Promise<void> {
  if (shortIds.length === 0) return;

  const supabase = createClient();

  const { error } = await supabase
    .from("user_feedback")
    .update({ status, updated_at: new Date().toISOString() })
    .in("short_id", shortIds);

  if (error) throw new Error(error.message);
}

export async function fetchFeedbackDetailClient(
  shortId: string
): Promise<FeedbackDetail | null> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("user_feedback")
    .select(
      "short_id, feedback_type, description, user_name, user_email, status, clickup_task_id, created_at, page_url, screenshot_url, debug_context"
    )
    .eq("short_id", shortId)
    .single();

  if (error) {
    if (error.code === "PGRST116") return null;
    throw new Error(error.message);
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
