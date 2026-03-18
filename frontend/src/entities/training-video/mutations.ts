import { createClient } from "@/shared/lib/supabase/client";
import { parseVideoUrl } from "./types";

interface CreateVideoInput {
  orgId: string;
  userId: string;
  title: string;
  url: string;
  category: string;
  description: string;
}

export async function createTrainingVideo(
  input: CreateVideoInput
): Promise<{ id: string }> {
  const parsed = parseVideoUrl(input.url);
  if (!parsed) {
    throw new Error("Не удалось распознать ссылку на видео");
  }

  const supabase = createClient();

  const { data, error } = await supabase
    .from("training_videos")
    .insert({
      organization_id: input.orgId,
      title: input.title.trim(),
      description: input.description.trim() || null,
      youtube_id: parsed.videoId,
      category: input.category.trim() || "Общее",
      platform: parsed.platform,
      created_by: input.userId,
    })
    .select("id")
    .single();

  if (error) throw error;
  return { id: data.id };
}

interface UpdateVideoInput {
  title: string;
  url: string;
  category: string;
  description: string;
}

export async function updateTrainingVideo(
  id: string,
  orgId: string,
  input: UpdateVideoInput
): Promise<void> {
  const parsed = parseVideoUrl(input.url);
  if (!parsed) {
    throw new Error("Не удалось распознать ссылку на видео");
  }

  const supabase = createClient();

  const { error } = await supabase
    .from("training_videos")
    .update({
      title: input.title.trim(),
      description: input.description.trim() || null,
      youtube_id: parsed.videoId,
      category: input.category.trim() || "Общее",
      platform: parsed.platform,
    })
    .eq("id", id)
    .eq("organization_id", orgId);

  if (error) throw error;
}

export async function deleteTrainingVideo(id: string, orgId: string): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("training_videos")
    .delete()
    .eq("id", id)
    .eq("organization_id", orgId);

  if (error) throw error;
}
