"use client";

/**
 * Thumbnails for verification screenshot attachments (Task 24 — Req 9.4, 14.6).
 *
 * Renders a row of 64×64 image thumbnails for a verification's
 * `attachment_urls` (Supabase Storage keys). Each thumbnail is fetched via
 * a signed URL (1-hour TTL per Req 9.7) so the private bucket never leaks.
 *
 * Req 14.6: if a signed URL fails to load, we show a broken-image icon
 * inline without crashing the surrounding row — the verification metadata
 * (timestamp, note) must still render.
 *
 * Rendered from `pin-list-section.tsx` next to the latest verification's
 * result badge. Not used for full-history rendering (which would be its own
 * expander; out of scope here — see Req 5.7).
 *
 * Uses TanStack Query per path so signed-URL fetches are cached across
 * re-renders; staleTime matches the signed-URL TTL (1 hour) to avoid
 * requesting the same URL twice within its validity window.
 */

import { useState } from "react";
import { useQueries } from "@tanstack/react-query";
import { ImageOff } from "lucide-react";

import { createClient } from "@/shared/lib/supabase/client";
import {
  DEFAULT_SIGNED_URL_TTL_SECONDS,
  getSignedUrl,
  type SupabaseStorageLike,
} from "@/features/journey/lib/signed-url";
import { ATTACHMENT_BUCKET } from "@/features/journey/lib/attachment-upload";

export interface VerificationThumbnailsProps {
  readonly paths: readonly string[] | null;
  /**
   * Override for tests. Production callers always omit this — the real
   * Supabase browser client is created lazily.
   */
  readonly supabase?: SupabaseStorageLike;
}

export function VerificationThumbnails({
  paths,
  supabase,
}: VerificationThumbnailsProps) {
  const safePaths = paths ?? [];
  const client: SupabaseStorageLike = supabase ?? createClient();

  const queries = useQueries({
    queries: safePaths.map((p) => ({
      queryKey: ["journey", "signed-url", ATTACHMENT_BUCKET, p] as const,
      queryFn: () => getSignedUrl(client, ATTACHMENT_BUCKET, p),
      // Signed URL is valid for the TTL window; don't re-fetch within it.
      staleTime: (DEFAULT_SIGNED_URL_TTL_SECONDS - 60) * 1000,
      refetchOnWindowFocus: false,
    })),
  });

  if (safePaths.length === 0) return null;

  return (
    <ul
      data-testid="verification-thumbnails"
      className="mt-1 flex flex-wrap gap-1"
    >
      {queries.map((q, i) => (
        <ThumbnailCell
          key={`${safePaths[i]}-${i}`}
          state={
            q.isLoading
              ? { status: "loading" }
              : q.data
                ? { status: "ok", url: q.data }
                : { status: "error" }
          }
        />
      ))}
    </ul>
  );
}

type ThumbState =
  | { readonly status: "loading" }
  | { readonly status: "ok"; readonly url: string }
  | { readonly status: "error" };

function ThumbnailCell({ state }: { state: ThumbState }) {
  const [imgError, setImgError] = useState(false);
  const effective: ThumbState =
    state.status === "ok" && imgError ? { status: "error" } : state;

  return (
    <li className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-md border border-border-light bg-background">
      {effective.status === "loading" && (
        <span className="text-[11px] text-text-subtle">…</span>
      )}
      {effective.status === "ok" && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={effective.url}
          alt="Скриншот верификации"
          className="h-full w-full object-cover"
          onError={() => setImgError(true)}
        />
      )}
      {effective.status === "error" && (
        <ImageOff
          className="h-5 w-5 text-text-subtle"
          aria-label="Изображение недоступно"
        />
      )}
    </li>
  );
}
