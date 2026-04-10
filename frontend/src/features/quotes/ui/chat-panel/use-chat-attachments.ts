"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import { createClient } from "@/shared/lib/supabase/client";

/**
 * Pending attachment state. Each entry progresses through:
 *   added (progress=0) → uploading → uploaded (progress=100, documentId set)
 *   or: added → error
 */
export interface PendingAttachment {
  /** Local id used for list keys and removal */
  tempId: string;
  file: File;
  /** Storage path, set after upload completes */
  storagePath?: string;
  /** documents.id — set after metadata row is inserted */
  documentId?: string;
  /** 0–100 */
  progress: number;
  error?: string;
}

const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;
const ALLOWED_MIME_PREFIXES = [
  "image/",
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument",
  "application/vnd.ms-excel",
  "application/zip",
] as const;

function isAllowedMime(mime: string): boolean {
  if (!mime) return false;
  return ALLOWED_MIME_PREFIXES.some((prefix) => mime.startsWith(prefix));
}

function formatSizeMb(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

interface UseChatAttachmentsParams {
  quoteId: string;
  orgId: string;
  userId: string;
}

export interface UseChatAttachmentsReturn {
  attachments: PendingAttachment[];
  addFiles: (files: File[]) => Promise<void>;
  removeAttachment: (tempId: string) => Promise<void>;
  clear: () => void;
  getReadyDocumentIds: () => string[];
  isUploading: boolean;
  hasAttachments: boolean;
}

/**
 * Manages pending chat attachments: validation, upload to Supabase Storage,
 * documents table row creation, and cleanup on removal.
 *
 * The hook does NOT create the chat comment — that happens separately in the
 * send handler, after which the caller passes the resulting document ids via
 * `getReadyDocumentIds()` so they can be linked to the comment.
 */
export function useChatAttachments({
  quoteId,
  orgId,
  userId,
}: UseChatAttachmentsParams): UseChatAttachmentsReturn {
  const [attachments, setAttachments] = useState<PendingAttachment[]>([]);

  const addFiles = useCallback(
    async (files: File[]) => {
      const supabase = createClient();

      // Validate and seed state
      const toUpload: PendingAttachment[] = [];
      for (const file of files) {
        if (file.size > MAX_FILE_SIZE_BYTES) {
          toast.error(
            `${file.name}: размер ${formatSizeMb(file.size)} превышает лимит 50 МБ`
          );
          continue;
        }
        if (!isAllowedMime(file.type)) {
          toast.error(`${file.name}: неподдерживаемый формат (${file.type || "unknown"})`);
          continue;
        }
        toUpload.push({
          tempId: crypto.randomUUID(),
          file,
          progress: 0,
        });
      }

      if (toUpload.length === 0) return;
      setAttachments((prev) => [...prev, ...toUpload]);

      // Upload in parallel
      await Promise.all(
        toUpload.map(async (att) => {
          const ext = att.file.name.split(".").pop()?.toLowerCase() || "bin";
          const storagePath = `quotes/${quoteId}/${crypto.randomUUID()}.${ext}`;

          try {
            const { error: uploadError } = await supabase.storage
              .from("kvota-documents")
              .upload(storagePath, att.file, {
                contentType: att.file.type || undefined,
                upsert: false,
              });
            if (uploadError) throw uploadError;

            const { data: docRow, error: insertError } = await supabase
              .from("documents")
              .insert({
                organization_id: orgId,
                entity_type: "quote",
                entity_id: quoteId,
                parent_quote_id: quoteId,
                storage_path: storagePath,
                original_filename: att.file.name,
                file_size_bytes: att.file.size,
                mime_type: att.file.type || null,
                uploaded_by: userId,
                // status defaults to 'draft' via migration 258
              })
              .select("id")
              .single();
            if (insertError) throw insertError;

            setAttachments((prev) =>
              prev.map((a) =>
                a.tempId === att.tempId
                  ? {
                      ...a,
                      storagePath,
                      documentId: docRow.id,
                      progress: 100,
                    }
                  : a
              )
            );
          } catch (err) {
            // Best-effort cleanup if storage succeeded but row insert failed
            await supabase.storage
              .from("kvota-documents")
              .remove([storagePath])
              .catch(() => {});

            const message = err instanceof Error ? err.message : "Ошибка загрузки";
            setAttachments((prev) =>
              prev.map((a) =>
                a.tempId === att.tempId ? { ...a, error: message } : a
              )
            );
            toast.error(`${att.file.name}: ${message}`);
          }
        })
      );
    },
    [quoteId, orgId, userId]
  );

  const removeAttachment = useCallback(async (tempId: string) => {
    const supabase = createClient();

    let target: PendingAttachment | undefined;
    setAttachments((prev) => {
      target = prev.find((a) => a.tempId === tempId);
      return prev.filter((a) => a.tempId !== tempId);
    });

    if (!target) return;

    // Cleanup remote state if it made it that far
    if (target.documentId) {
      await supabase
        .from("documents")
        .delete()
        .eq("id", target.documentId)
        .throwOnError();
    }
    if (target.storagePath) {
      await supabase.storage
        .from("kvota-documents")
        .remove([target.storagePath]);
    }
  }, []);

  const clear = useCallback(() => {
    setAttachments([]);
  }, []);

  const getReadyDocumentIds = useCallback((): string[] => {
    return attachments
      .filter((a) => a.documentId && !a.error)
      .map((a) => a.documentId as string);
  }, [attachments]);

  const isUploading = attachments.some(
    (a) => a.progress < 100 && !a.error
  );

  return {
    attachments,
    addFiles,
    removeAttachment,
    clear,
    getReadyDocumentIds,
    isUploading,
    hasAttachments: attachments.length > 0,
  };
}
