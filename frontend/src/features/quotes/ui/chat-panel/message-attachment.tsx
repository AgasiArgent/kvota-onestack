"use client";

import { useEffect, useState } from "react";
import { FileIcon, Download } from "lucide-react";
import { createClient } from "@/shared/lib/supabase/client";
import { cn } from "@/lib/utils";
import type { CommentAttachment } from "@/entities/quote/types";

function formatFileSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isImage(mime: string | null): boolean {
  return mime?.startsWith("image/") ?? false;
}

interface MessageAttachmentProps {
  attachment: CommentAttachment;
  isOwn?: boolean;
}

/**
 * Renders a single comment attachment. Images are shown inline with a
 * click-to-expand behavior (opens the signed URL in a new tab). Other files
 * show as a compact download card.
 *
 * Signed URLs have a 1-hour expiry which is generated lazily on mount.
 */
export function MessageAttachment({ attachment, isOwn }: MessageAttachmentProps) {
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [urlError, setUrlError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const supabase = createClient();

    void (async () => {
      const { data, error } = await supabase.storage
        .from("kvota-documents")
        .createSignedUrl(attachment.storage_path, 60 * 60);
      if (cancelled) return;
      if (error || !data?.signedUrl) {
        setUrlError(true);
        return;
      }
      setSignedUrl(data.signedUrl);
    })();

    return () => {
      cancelled = true;
    };
  }, [attachment.storage_path]);

  if (isImage(attachment.mime_type)) {
    if (!signedUrl) {
      return (
        <div
          className={cn(
            "mt-1 rounded-md border bg-muted/30 w-40 h-40 flex items-center justify-center text-xs text-muted-foreground",
            urlError && "text-destructive"
          )}
        >
          {urlError ? "Ошибка" : "..."}
        </div>
      );
    }
    return (
      <a
        href={signedUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 block max-w-xs rounded-md overflow-hidden border hover:opacity-90 transition-opacity"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={signedUrl}
          alt={attachment.original_filename}
          className="w-full h-auto max-h-64 object-contain bg-muted/30"
        />
      </a>
    );
  }

  // Non-image: compact download card.
  // The `download` attribute tells Chrome to save the file with its
  // original filename instead of rendering it (e.g. the PDF viewer),
  // which both matches user intent for a file-attachment card and
  // sidesteps Chrome's PDF viewer showing confusing error states for
  // malformed files.
  return (
    <a
      href={signedUrl ?? "#"}
      download={attachment.original_filename}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => {
        if (!signedUrl) e.preventDefault();
      }}
      className={cn(
        "mt-1 flex items-center gap-2 rounded-md border px-2.5 py-1.5 max-w-[240px] text-xs transition-colors",
        isOwn
          ? "bg-primary/5 border-primary/20 hover:bg-primary/10"
          : "bg-background hover:bg-muted"
      )}
    >
      <FileIcon className="w-3.5 h-3.5 flex-shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="truncate font-medium">{attachment.original_filename}</div>
        {attachment.file_size_bytes && (
          <div className="text-[10px] text-muted-foreground">
            {formatFileSize(attachment.file_size_bytes)}
          </div>
        )}
      </div>
      <Download className="w-3 h-3 flex-shrink-0 text-muted-foreground" />
    </a>
  );
}
