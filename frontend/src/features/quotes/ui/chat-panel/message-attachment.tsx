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
 * Renders a single comment attachment.
 *
 * Images show inline with a small download-button overlay in the top-right
 * corner. Clicking the image itself opens the preview in a new tab; clicking
 * the download button forces a download.
 *
 * Non-image files render as a compact card; the whole card is a download
 * link.
 *
 * We generate TWO signed URLs per attachment:
 *   - viewUrl     — plain signed URL for inline preview / open-in-tab
 *   - downloadUrl — signed URL created with { download: filename } so
 *                   Supabase Storage serves the file with
 *                   Content-Disposition: attachment. This works across
 *                   origins, unlike the plain HTML `download` attribute
 *                   which is ignored for cross-origin links.
 * Both expire in 1 hour.
 */
export function MessageAttachment({ attachment, isOwn }: MessageAttachmentProps) {
  const [viewUrl, setViewUrl] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [urlError, setUrlError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const supabase = createClient();

    void (async () => {
      const [viewRes, downloadRes] = await Promise.all([
        supabase.storage
          .from("kvota-documents")
          .createSignedUrl(attachment.storage_path, 60 * 60),
        supabase.storage
          .from("kvota-documents")
          .createSignedUrl(attachment.storage_path, 60 * 60, {
            download: attachment.original_filename,
          }),
      ]);
      if (cancelled) return;
      if (viewRes.error || !viewRes.data?.signedUrl) {
        setUrlError(true);
        return;
      }
      setViewUrl(viewRes.data.signedUrl);
      setDownloadUrl(downloadRes.data?.signedUrl ?? viewRes.data.signedUrl);
    })();

    return () => {
      cancelled = true;
    };
  }, [attachment.storage_path, attachment.original_filename]);

  if (isImage(attachment.mime_type)) {
    if (!viewUrl) {
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
      <div className="mt-1 relative inline-block max-w-xs rounded-md overflow-hidden border">
        <a
          href={viewUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block hover:opacity-90 transition-opacity"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={viewUrl}
            alt={attachment.original_filename}
            className="w-full h-auto max-h-64 object-contain bg-muted/30"
          />
        </a>
        {downloadUrl && (
          <a
            href={downloadUrl}
            download={attachment.original_filename}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Скачать ${attachment.original_filename}`}
            className={cn(
              "absolute top-1.5 right-1.5 flex items-center justify-center w-7 h-7 rounded-full",
              "bg-background/80 backdrop-blur-sm border shadow-sm",
              "text-foreground hover:bg-background transition-colors"
            )}
          >
            <Download className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    );
  }

  // Non-image: compact download card.
  // The card's href uses the download-option signed URL, so clicking
  // anywhere on the card triggers a file download (Content-Disposition:
  // attachment from Supabase Storage).
  return (
    <a
      href={downloadUrl ?? "#"}
      download={attachment.original_filename}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => {
        if (!downloadUrl) e.preventDefault();
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
