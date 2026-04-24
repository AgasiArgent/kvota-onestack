/**
 * Verification-attachment upload helpers (Task 24 — Req 9.5–9.8).
 *
 * The `kvota.journey_verifications` INSERT accepts up to 3 screenshots per
 * event (Req 9.8), stored in the private Supabase Storage bucket
 * `journey-verification-attachments` (Req 9.7). Read access is signed-URL
 * only — that lives in `./signed-url.ts`.
 *
 * This module is pure business logic:
 *
 *   1. `validateAttachments(files, existingCount)` — client-side gate that
 *      matches the DB bucket constraints (mime/size) and caps the per-row
 *      count at 3. Called on every file-picker change so rejection is
 *      immediate and user-visible.
 *   2. `uploadAttachments(files, opts)` — serial upload driver with
 *      best-effort rollback. Partial attachment is not permitted per
 *      Req 9.6, so a single failure triggers cleanup of already-uploaded
 *      keys before returning failure.
 *
 * The driver takes `supabaseUpload` and `supabaseRemove` as callbacks so it
 * stays pure and unit-testable without a real Supabase client.
 *
 * IMPORTANT — three places enforce the size/mime/count limits:
 *   - Storage bucket config (migration 503)
 *   - UI validation (this module)
 *   - spec: requirements.md §9.8
 * Keep all three in sync when changing limits.
 */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const MAX_ATTACHMENTS = 3;
export const MAX_FILE_BYTES = 2 * 1024 * 1024; // 2 MB
export const ALLOWED_MIME = [
  "image/png",
  "image/jpeg",
  "image/webp",
] as const;

export const ATTACHMENT_BUCKET = "journey-verification-attachments";

// ---------------------------------------------------------------------------
// validateAttachments
// ---------------------------------------------------------------------------

export type AttachmentRejectionReason = "too_large" | "bad_mime" | "over_limit";

export interface AttachmentRejection {
  readonly file: File;
  readonly reason: AttachmentRejectionReason;
}

export interface AttachmentValidationResult {
  readonly valid: readonly File[];
  readonly rejected: readonly AttachmentRejection[];
}

function isAllowedMime(mime: string): boolean {
  return (ALLOWED_MIME as readonly string[]).includes(mime);
}

/**
 * Partition `files` into accepted + rejected. Rejection reasons are checked
 * in order: bad_mime → too_large → over_limit. Each rejected file carries
 * its own reason so the caller can toast per-file.
 */
export function validateAttachments(
  files: readonly File[],
  existingCount: number,
): AttachmentValidationResult {
  const remaining = Math.max(0, MAX_ATTACHMENTS - existingCount);
  const valid: File[] = [];
  const rejected: AttachmentRejection[] = [];

  for (const file of files) {
    if (!isAllowedMime(file.type)) {
      rejected.push({ file, reason: "bad_mime" });
      continue;
    }
    if (file.size > MAX_FILE_BYTES) {
      rejected.push({ file, reason: "too_large" });
      continue;
    }
    if (valid.length >= remaining) {
      rejected.push({ file, reason: "over_limit" });
      continue;
    }
    valid.push(file);
  }

  return { valid, rejected };
}

// ---------------------------------------------------------------------------
// uploadAttachments
// ---------------------------------------------------------------------------

/** Supabase Storage `upload` shape (minimal surface we depend on). */
export type SupabaseUploadFn = (
  path: string,
  file: File,
) => Promise<{
  data: { path: string } | null;
  error: unknown | null;
}>;

/** Supabase Storage `remove` shape (best-effort cleanup). */
export type SupabaseRemoveFn = (paths: string[]) => Promise<unknown>;

export interface UploadAttachmentsOptions {
  readonly bucket: string;
  /** Key prefix (e.g. `{node_id_safe}/{pin_id}`). No trailing slash. */
  readonly keyPrefix: string;
  readonly supabaseUpload: SupabaseUploadFn;
  readonly supabaseRemove: SupabaseRemoveFn;
}

export type UploadAttachmentsResult =
  | { readonly success: true; readonly paths: string[] }
  | {
      readonly success: false;
      readonly reason: string;
      readonly partialPathsToCleanup: string[];
    };

/**
 * Safe-filename: replace anything outside [A-Za-z0-9._-] with `_`. This is
 * conservative but matches the storage key regex contract in migration 503
 * (S3-style keys are permissive, but matching [A-Za-z0-9._-] avoids any
 * path-traversal / URL-encoding surprises).
 */
function safeFilename(name: string): string {
  // Collapse runs of disallowed chars into a single underscore to avoid
  // `foo___bar.png`-style keys from Cyrillic filenames.
  const collapsed = name.replace(/[^A-Za-z0-9._-]+/g, "_");
  // Don't let the name start with `.` — some storage backends treat hidden
  // files differently.
  return collapsed.replace(/^\.+/, "_");
}

function randomUuid(): string {
  // Modern browsers + Node ≥ 19 expose `crypto.randomUUID`. In tests we
  // fall back to a deterministic-ish string to avoid a hard require.
  const g = globalThis as { crypto?: { randomUUID?: () => string } };
  if (g.crypto && typeof g.crypto.randomUUID === "function") {
    return g.crypto.randomUUID();
  }
  // Fallback: timestamp + Math.random. Not cryptographic — only used in
  // tests that don't have the Node crypto global.
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

/**
 * Compose a storage key: `{keyPrefix}/{uuid}-{safe_filename}`. Keeping the
 * uuid prefix ensures two uploads of the same filename never collide.
 */
export function composeAttachmentKey(keyPrefix: string, filename: string): string {
  const prefix = keyPrefix.replace(/\/+$/, "");
  return `${prefix}/${randomUuid()}-${safeFilename(filename)}`;
}

/**
 * Upload a batch of files serially. Three files max (see MAX_ATTACHMENTS)
 * means parallelism isn't worth the complexity of partial-failure bookkeeping.
 *
 * On any single failure, already-uploaded keys are cleaned up via
 * `supabaseRemove`. Cleanup errors are swallowed — the DB INSERT will not
 * happen anyway (Req 9.6), so the worst case is orphan objects that a
 * storage-side retention policy can sweep.
 */
export async function uploadAttachments(
  files: readonly File[],
  opts: UploadAttachmentsOptions,
): Promise<UploadAttachmentsResult> {
  const paths: string[] = [];

  for (const file of files) {
    const key = composeAttachmentKey(opts.keyPrefix, file.name);
    let resp: { data: { path: string } | null; error: unknown | null };
    try {
      resp = await opts.supabaseUpload(key, file);
    } catch (e) {
      await cleanup(opts, paths);
      const message =
        e instanceof Error ? e.message : "Unknown upload error";
      return {
        success: false,
        reason: message,
        partialPathsToCleanup: [...paths],
      };
    }
    if (resp.error || !resp.data) {
      await cleanup(opts, paths);
      const message = extractErrorMessage(resp.error) ?? "Upload failed";
      return {
        success: false,
        reason: message,
        partialPathsToCleanup: [...paths],
      };
    }
    paths.push(resp.data.path);
  }

  return { success: true, paths };
}

async function cleanup(
  opts: UploadAttachmentsOptions,
  paths: readonly string[],
): Promise<void> {
  if (paths.length === 0) return;
  try {
    await opts.supabaseRemove([...paths]);
  } catch {
    // Best-effort — the INSERT won't happen, so orphans are acceptable.
  }
}

function extractErrorMessage(err: unknown): string | null {
  if (err === null || err === undefined) return null;
  if (typeof err === "string") return err;
  const maybe = err as { message?: unknown };
  if (typeof maybe.message === "string") return maybe.message;
  return null;
}
