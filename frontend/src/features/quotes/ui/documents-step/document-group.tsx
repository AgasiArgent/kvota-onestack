"use client";

import { useState } from "react";
import {
  FileText,
  FileImage,
  FileSpreadsheet,
  File,
  Download,
  Trash2,
  ChevronDown,
  Loader2,
  BadgePlus,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { createClient } from "@/shared/lib/supabase/client";
import {
  DOCUMENT_TYPE_LABELS,
  getMimeCategory,
  formatFileSize,
} from "./constants";

export interface DocumentRow {
  id: string;
  entity_type: string;
  entity_id: string;
  storage_path: string;
  original_filename: string;
  file_size_bytes: number | null;
  mime_type: string | null;
  document_type: string | null;
  description: string | null;
  created_at: string | null;
  comment_id?: string | null;
  status?: string | null;
}

const MIME_ICONS: Record<string, typeof FileText> = {
  pdf: FileText,
  image: FileImage,
  spreadsheet: FileSpreadsheet,
  doc: FileText,
  file: File,
};

interface DocumentGroupProps {
  title: string;
  documents: DocumentRow[];
  onDeleted: () => void;
  /** When provided, shows a "Promote to official" button per document. */
  onPromote?: (doc: DocumentRow) => void;
  /** Optional empty-state message */
  emptyMessage?: string;
}

export function DocumentGroup({
  title,
  documents,
  onDeleted,
  onPromote,
  emptyMessage,
}: DocumentGroupProps) {
  const [open, setOpen] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  async function handleDownload(doc: DocumentRow) {
    setDownloadingId(doc.id);
    try {
      const supabase = createClient();
      // Pass `download: <filename>` so Supabase Storage serves the URL with
      // Content-Disposition: attachment. The HTML `download` attribute alone
      // is ignored on cross-origin URLs, so we additionally fetch the bytes
      // and trigger a real blob download. This guarantees the file is saved
      // to disk instead of opening as a PDF/image preview in a new tab
      // (МОП fail QP4).
      const { data, error } = await supabase.storage
        .from("kvota-documents")
        .createSignedUrl(doc.storage_path, 3600, {
          download: doc.original_filename,
        });
      if (error || !data?.signedUrl) throw error ?? new Error("No URL");

      const response = await fetch(data.signedUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = doc.original_filename;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      // Defer revoke so the browser has time to start the download.
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch {
      toast.error("Не удалось получить ссылку для скачивания");
    } finally {
      setDownloadingId(null);
    }
  }

  async function handleDelete(doc: DocumentRow) {
    const confirmed = window.confirm(
      `Удалить файл "${doc.original_filename}"?`
    );
    if (!confirmed) return;

    setDeletingId(doc.id);
    try {
      const supabase = createClient();

      // Delete the DB row first and ask PostgREST to return the affected
      // row(s) via `.select()`. RLS-blocked DELETEs return success with an
      // empty array (PostgREST does not surface this as an error), so we
      // must check the row count to detect silent permission failures.
      // documents_delete_policy (migration 143) restricts delete to admin /
      // sales_manager / quote_controller / finance — for any other role
      // (e.g. МОП = sales) the previous handler appeared to "do nothing"
      // because the empty success was treated as success (МОП fail QP3).
      const { data: deletedRows, error: dbError } = await supabase
        .from("documents")
        .delete()
        .eq("id", doc.id)
        .select("id");
      if (dbError) throw dbError;
      if (!deletedRows || deletedRows.length === 0) {
        toast.error("Недостаточно прав для удаления файла");
        return;
      }

      // Storage cleanup is best-effort — if it fails the DB row is already
      // gone so the file disappears from the UI; the orphan blob can be
      // cleaned up by a janitor job.
      const { error: storageError } = await supabase.storage
        .from("kvota-documents")
        .remove([doc.storage_path]);
      if (storageError) {
        console.warn("Storage delete failed (orphan blob):", storageError);
      }

      toast.success("Файл удалён");
      onDeleted();
    } catch {
      toast.error("Не удалось удалить файл");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-4 py-3 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <ChevronDown
          size={16}
          className={cn(
            "text-muted-foreground transition-transform",
            !open && "-rotate-90"
          )}
        />
        <span className="text-sm font-medium flex-1">{title}</span>
        <Badge variant="secondary" className="text-xs">
          {documents.length}
        </Badge>
      </button>

      {open && documents.length === 0 && emptyMessage && (
        <div className="border-t border-border px-4 py-6 text-center text-xs text-muted-foreground">
          {emptyMessage}
        </div>
      )}

      {open && documents.length > 0 && (
        <div className="border-t border-border divide-y divide-border">
          {documents.map((doc) => {
            const category = getMimeCategory(doc.mime_type);
            const Icon = MIME_ICONS[category] ?? File;
            const typeLabel = doc.document_type
              ? DOCUMENT_TYPE_LABELS[doc.document_type] ?? doc.document_type
              : null;

            return (
              <div
                key={doc.id}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30 transition-colors"
              >
                <Icon
                  size={18}
                  className="text-muted-foreground shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm truncate">{doc.original_filename}</p>
                  <div className="flex items-center gap-2 mt-0.5">
                    {typeLabel && (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                        {typeLabel}
                      </Badge>
                    )}
                    {doc.description && (
                      <span className="text-xs text-muted-foreground truncate">
                        {doc.description}
                      </span>
                    )}
                  </div>
                </div>
                <span className="text-xs text-muted-foreground shrink-0">
                  {formatFileSize(doc.file_size_bytes)}
                </span>
                <span className="text-xs text-muted-foreground shrink-0">
                  {doc.created_at
                    ? new Date(doc.created_at).toLocaleDateString("ru-RU", { timeZone: "Europe/Moscow" })
                    : ""}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0"
                  disabled={downloadingId === doc.id}
                  onClick={() => handleDownload(doc)}
                  title="Скачать"
                >
                  {downloadingId === doc.id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Download size={14} />
                  )}
                </Button>
                {onPromote && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0 text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                    onClick={() => onPromote(doc)}
                    title="Сделать официальным"
                  >
                    <BadgePlus size={14} />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 text-red-500 hover:text-red-600 hover:bg-red-50"
                  disabled={deletingId === doc.id}
                  onClick={() => handleDelete(doc)}
                  title="Удалить"
                >
                  {deletingId === doc.id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Trash2 size={14} />
                  )}
                </Button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
