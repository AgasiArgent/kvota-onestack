import { createClient } from "@/shared/lib/supabase/client";
import { apiClient } from "@/shared/lib/api";
import { dataUrlToBlob } from "../lib/compressScreenshot";
import type { DebugContext } from "../lib/debugContext";

export type FeedbackType = "bug" | "ux_ui" | "suggestion" | "question";

interface SubmitFeedbackParams {
  feedbackType: FeedbackType;
  description: string;
  pageUrl: string;
  pageTitle: string;
  debugContext: DebugContext;
  screenshotDataUrl?: string;
  /**
   * Optional Customer Journey Map node id (`app:<route>` or `ghost:<slug>`).
   * Populated when feedback is submitted from within `/journey` or any page
   * that knows its manifest node. Written to `kvota.user_feedback.node_id`
   * so the feedback is visible on that node's drawer (Req 11.1 b-half).
   */
  nodeId?: string;
}

interface SubmitResult {
  success: boolean;
  shortId?: string;
  error?: string;
}

export async function submitFeedback(
  params: SubmitFeedbackParams
): Promise<SubmitResult> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    return { success: false, error: "Not authenticated" };
  }

  let screenshotUrl = "";

  if (params.screenshotDataUrl) {
    try {
      const blob = dataUrlToBlob(params.screenshotDataUrl);
      const timestamp = Date.now();
      const path = `${session.user.id}/${timestamp}.jpg`;

      const { error: uploadError } = await supabase.storage
        .from("feedback-screenshots")
        .upload(path, blob, { contentType: "image/jpeg", upsert: false });

      if (uploadError) throw uploadError;

      const { data: urlData } = supabase.storage
        .from("feedback-screenshots")
        .getPublicUrl(path);

      screenshotUrl = urlData.publicUrl;
    } catch (err) {
      console.warn("Screenshot upload failed, submitting without:", err);
    }
  }

  try {
    const result = await apiClient<{ short_id: string }>("/feedback", {
      method: "POST",
      body: JSON.stringify({
        feedback_type: params.feedbackType,
        description: params.description,
        page_url: params.pageUrl,
        page_title: params.pageTitle,
        debug_context: params.debugContext,
        screenshot_url: screenshotUrl,
        ...(params.nodeId ? { node_id: params.nodeId } : {}),
      }),
    });

    if (!result.success) {
      return {
        success: false,
        error: result.error?.message || "Submit failed",
      };
    }
    return { success: true, shortId: result.data?.short_id };
  } catch {
    return { success: false, error: "Network error" };
  }
}
