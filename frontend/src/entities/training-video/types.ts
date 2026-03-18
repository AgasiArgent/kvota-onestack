export interface TrainingVideo {
  id: string;
  organization_id: string;
  title: string;
  description: string | null;
  youtube_id: string;
  category: string;
  platform: "rutube" | "youtube" | "loom";
  thumbnail_url: string | null;
  sort_order: number;
  is_active: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  creator?: { full_name: string | null } | null;
}

export interface TrainingVideoFormData {
  title: string;
  url: string;
  category: string;
  description: string;
}

export type VideoPlatform = "rutube" | "youtube" | "loom";

/**
 * Parse a video URL into platform + video_id.
 * Returns null if the URL is not recognized.
 */
export function parseVideoUrl(
  url: string
): { videoId: string; platform: VideoPlatform } | null {
  const trimmed = url.trim();

  // RuTube private: https://rutube.ru/video/private/HASH/?p=TOKEN
  const rutubePrivate = trimmed.match(
    /rutube\.ru\/video\/private\/([a-f0-9]+)\/?(?:\?(.+))?/i
  );
  if (rutubePrivate) {
    const hash = rutubePrivate[1];
    const queryString = rutubePrivate[2] ?? "";
    const params = new URLSearchParams(queryString);
    const token = params.get("p");
    const videoId = token ? `${hash}?p=${token}` : hash;
    return { videoId, platform: "rutube" };
  }

  // RuTube public: https://rutube.ru/video/HASH/
  const rutubePublic = trimmed.match(/rutube\.ru\/video\/([a-f0-9]+)/i);
  if (rutubePublic) {
    return { videoId: rutubePublic[1], platform: "rutube" };
  }

  // YouTube: https://www.youtube.com/watch?v=ID or https://youtu.be/ID
  const ytWatch = trimmed.match(
    /(?:youtube\.com\/watch\?.*v=|youtu\.be\/)([a-zA-Z0-9_-]+)/
  );
  if (ytWatch) {
    return { videoId: ytWatch[1], platform: "youtube" };
  }

  return null;
}

/**
 * Generate an embeddable URL for a video.
 */
export function getEmbedUrl(
  videoId: string,
  platform: VideoPlatform
): string {
  if (platform === "youtube") {
    return `https://www.youtube.com/embed/${videoId}`;
  }

  // RuTube embed
  // If videoId contains ?, append &, otherwise use ?
  const separator = videoId.includes("?") ? "&" : "?";
  return `https://rutube.ru/play/embed/${videoId}${separator}autoplay=0`;
}
