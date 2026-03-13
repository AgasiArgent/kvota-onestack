"use client";

import { createClient } from "@/shared/lib/supabase/client";
import { dataUrlToBlob } from "../lib/compressScreenshot";

export type FeedbackType = "bug" | "ux_ui" | "suggestion" | "question";

interface SubmitFeedbackParams {
  feedbackType: FeedbackType;
  description: string;
  pageUrl: string;
  pageTitle: string;
  debugContext: Record<string, unknown>;
  screenshotDataUrl?: string;
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
    const apiBaseUrl = process.env.NEXT_PUBLIC_PYTHON_API_URL || "";
    const response = await fetch(`${apiBaseUrl}/api/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${session.access_token}`,
      },
      body: JSON.stringify({
        feedback_type: params.feedbackType,
        description: params.description,
        page_url: params.pageUrl,
        page_title: params.pageTitle,
        debug_context: params.debugContext,
        screenshot_url: screenshotUrl,
      }),
    });

    const result = await response.json();
    if (!response.ok || !result.success) {
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
