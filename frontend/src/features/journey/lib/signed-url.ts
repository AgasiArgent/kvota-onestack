/**
 * Signed-URL helper for the private `journey-verification-attachments`
 * bucket (Task 24 — Req 9.7).
 *
 * Req 9.7: read access to attachments is granted only via signed URLs with
 * a 1-hour default TTL. Anonymous access is never permitted.
 *
 * The helper intentionally returns `null` on error instead of throwing —
 * verification history (Req 14.6) must keep rendering even when a file is
 * missing or a signed URL fails to issue; the UI surfaces a broken-image
 * icon in that case. Throwing would bubble into React error boundaries and
 * hide the rest of the history entry, which is the opposite of what we want.
 */

// Minimal surface of the Supabase client we depend on. Declared structurally
// so tests can pass fakes without the full client type.
export interface SupabaseStorageLike {
  readonly storage: {
    readonly from: (bucket: string) => {
      readonly createSignedUrl: (
        path: string,
        ttl: number,
      ) => Promise<{
        data: { signedUrl: string } | null;
        error: unknown | null;
      }>;
    };
  };
}

export const DEFAULT_SIGNED_URL_TTL_SECONDS = 3600;

/**
 * Issue a signed URL for `path` in `bucket`. Returns the URL on success,
 * null on any error (including thrown exceptions from the client).
 */
export async function getSignedUrl(
  supabase: SupabaseStorageLike,
  bucket: string,
  path: string,
  ttlSeconds: number = DEFAULT_SIGNED_URL_TTL_SECONDS,
): Promise<string | null> {
  try {
    const { data, error } = await supabase.storage
      .from(bucket)
      .createSignedUrl(path, ttlSeconds);
    if (error || !data) return null;
    return data.signedUrl;
  } catch {
    return null;
  }
}
