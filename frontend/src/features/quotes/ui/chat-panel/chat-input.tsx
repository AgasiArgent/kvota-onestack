"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
} from "react";
import { Paperclip, Send, X, Loader2, FileIcon, ImageIcon } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { useChatAttachments } from "./use-chat-attachments";

export interface OrgMember {
  userId: string;
  fullName: string;
}

interface ChatInputProps {
  onSend: (
    body: string,
    mentions?: string[],
    attachmentDocumentIds?: string[]
  ) => Promise<void>;
  disabled?: boolean;
  orgMembers?: OrgMember[];
  quoteId: string;
  orgId: string;
  userId: string;
}

/**
 * Extract the @mention query from the current cursor position.
 * Returns { query, startIndex } if "@" was found before cursor, or null.
 */
function getMentionQuery(
  text: string,
  cursorPos: number
): { query: string; startIndex: number } | null {
  const beforeCursor = text.slice(0, cursorPos);
  const atIdx = beforeCursor.lastIndexOf("@");
  if (atIdx === -1) return null;

  // "@" must be at start of text or preceded by whitespace
  if (atIdx > 0 && !/\s/.test(beforeCursor[atIdx - 1])) return null;

  const query = beforeCursor.slice(atIdx + 1);
  if (query.includes("\n") || query.length > 40) return null;

  return { query, startIndex: atIdx };
}

export function ChatInput({
  onSend,
  disabled,
  orgMembers,
  quoteId,
  orgId,
  userId,
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const [mentions, setMentions] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    attachments,
    addFiles,
    removeAttachment,
    clear: clearAttachments,
    getReadyDocumentIds,
    isUploading,
    hasAttachments,
  } = useChatAttachments({ quoteId, orgId, userId });

  // Mention autocomplete state
  const [mentionQuery, setMentionQuery] = useState<{
    query: string;
    startIndex: number;
  } | null>(null);
  const [filteredMembers, setFilteredMembers] = useState<OrgMember[]>([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const hasMentions = orgMembers && orgMembers.length > 0;

  // Update filtered members when mention query changes
  useEffect(() => {
    if (!hasMentions || !mentionQuery) {
      setFilteredMembers([]);
      setSelectedIdx(0);
      return;
    }

    const q = mentionQuery.query.toLowerCase();
    const matches = orgMembers.filter((m) =>
      m.fullName.toLowerCase().includes(q)
    );
    setFilteredMembers(matches.slice(0, 8));
    setSelectedIdx(0);
  }, [mentionQuery, orgMembers, hasMentions]);

  const updateMentionState = useCallback(() => {
    if (!hasMentions) return;
    const textarea = textareaRef.current;
    if (!textarea) return;

    const result = getMentionQuery(value, textarea.selectionStart);
    setMentionQuery(result);
  }, [value, hasMentions]);

  const insertMention = useCallback(
    (member: OrgMember) => {
      if (!mentionQuery || !textareaRef.current) return;

      const before = value.slice(0, mentionQuery.startIndex);
      const after = value.slice(textareaRef.current.selectionStart);
      const mentionText = `@${member.fullName} `;
      const newValue = before + mentionText + after;

      setValue(newValue);
      setMentions((prev) =>
        prev.includes(member.userId) ? prev : [...prev, member.userId]
      );
      setMentionQuery(null);

      requestAnimationFrame(() => {
        const cursor = before.length + mentionText.length;
        textareaRef.current?.setSelectionRange(cursor, cursor);
        textareaRef.current?.focus();
      });
    },
    [mentionQuery, value]
  );

  const handleSend = useCallback(async () => {
    const trimmed = value.trim();
    const readyIds = getReadyDocumentIds();
    // Allow sending when there's either text or at least one ready attachment
    if ((!trimmed && readyIds.length === 0) || sending || isUploading) return;

    setSending(true);
    try {
      await onSend(
        trimmed,
        mentions.length > 0 ? mentions : undefined,
        readyIds.length > 0 ? readyIds : undefined
      );
      // Success path — clear composer state
      setValue("");
      setMentions([]);
      setMentionQuery(null);
      clearAttachments();
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    } catch (err) {
      // Send failed — remove the orphaned uploaded attachments so they
      // don't pile up in the bucket / documents table, and tell the user.
      await Promise.all(
        attachments
          .filter((a) => a.documentId && !a.error)
          .map((a) => removeAttachment(a.tempId))
      );
      const msg = err instanceof Error ? err.message : "Ошибка отправки";
      toast.error(msg);
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }, [
    value,
    sending,
    onSend,
    mentions,
    getReadyDocumentIds,
    isUploading,
    clearAttachments,
    attachments,
    removeAttachment,
  ]);

  const handleFileSelect = useCallback(
    async (e: ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      // Reset so selecting the same file again re-triggers change
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (files.length === 0) return;
      await addFiles(files);
    },
    [addFiles]
  );

  // ---- Drag & drop -------------------------------------------------------
  // Users can drag files from their OS directly onto the chat input area.
  // We count dragenter/dragleave events to distinguish "actually leaving"
  // from "moving over a child element" (which fires leave+enter pairs).
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  const handleDragEnter = useCallback((e: DragEvent) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current += 1;
    setIsDragOver(true);
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "copy";
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = Math.max(0, dragCounterRef.current - 1);
    if (dragCounterRef.current === 0) setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    async (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes("Files")) return;
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length === 0) return;
      await addFiles(files);
    },
    [addFiles]
  );

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Handle mention dropdown navigation
      if (mentionQuery && filteredMembers.length > 0) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setSelectedIdx((prev) =>
            prev < filteredMembers.length - 1 ? prev + 1 : 0
          );
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          setSelectedIdx((prev) =>
            prev > 0 ? prev - 1 : filteredMembers.length - 1
          );
          return;
        }
        if (e.key === "Enter") {
          e.preventDefault();
          insertMention(filteredMembers[selectedIdx]);
          return;
        }
        if (e.key === "Escape") {
          e.preventDefault();
          setMentionQuery(null);
          return;
        }
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend, mentionQuery, filteredMembers, selectedIdx, insertMention]
  );

  const handleInput = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 96)}px`;
  }, []);

  const hasReadyAttachments = attachments.some((a) => a.documentId && !a.error);
  const canSend =
    (value.trim().length > 0 || hasReadyAttachments) &&
    !sending &&
    !isUploading &&
    !disabled;
  const showDropdown = mentionQuery !== null && filteredMembers.length > 0;

  return (
    <div
      className={cn(
        "relative border-t border-border bg-background px-4 py-3 transition-colors",
        isDragOver && "bg-primary/5 ring-2 ring-inset ring-primary/40"
      )}
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Drop overlay hint */}
      {isDragOver && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center z-10">
          <div className="rounded-lg bg-background/95 border border-primary/40 px-4 py-2 text-sm text-primary shadow-sm">
            Отпустите файл для загрузки
          </div>
        </div>
      )}

      {/* Mention dropdown — positioned above input */}
      {showDropdown && (
        <div
          ref={dropdownRef}
          className="absolute bottom-full left-4 right-4 mb-1 bg-background border border-border rounded-lg shadow-lg max-h-48 overflow-y-auto z-10"
        >
          {filteredMembers.map((member, idx) => (
            <button
              key={member.userId}
              onMouseDown={(e) => {
                e.preventDefault();
                insertMention(member);
              }}
              className={cn(
                "w-full text-left px-3 py-2 text-sm transition-colors",
                idx === selectedIdx
                  ? "bg-primary/10 text-primary"
                  : "text-foreground hover:bg-muted"
              )}
            >
              {member.fullName}
            </button>
          ))}
        </div>
      )}

      {/* Pending attachments preview */}
      {hasAttachments && (
        <div className="mb-2 flex flex-wrap gap-2">
          {attachments.map((att) => {
            const isImage = att.file.type.startsWith("image/");
            return (
              <div
                key={att.tempId}
                className={cn(
                  "flex items-center gap-2 rounded-md border px-2 py-1 text-xs",
                  att.error
                    ? "border-destructive/40 bg-destructive/5 text-destructive"
                    : "border-border bg-muted/40"
                )}
              >
                {att.progress < 100 && !att.error ? (
                  <Loader2 className="w-3 h-3 animate-spin flex-shrink-0" />
                ) : isImage ? (
                  <ImageIcon className="w-3 h-3 flex-shrink-0 text-muted-foreground" />
                ) : (
                  <FileIcon className="w-3 h-3 flex-shrink-0 text-muted-foreground" />
                )}
                <span className="max-w-[140px] truncate">{att.file.name}</span>
                <button
                  onClick={() => removeAttachment(att.tempId)}
                  className="flex-shrink-0 p-0.5 rounded hover:bg-muted"
                  aria-label={`Удалить ${att.file.name}`}
                  type="button"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="flex items-stretch gap-2">
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx,.zip"
          onChange={handleFileSelect}
        />
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            handleInput();
            if (hasMentions) {
              requestAnimationFrame(() => updateMentionState());
            }
          }}
          onKeyDown={handleKeyDown}
          onClick={hasMentions ? updateMentionState : undefined}
          placeholder={
            hasMentions
              ? "Написать сообщение... (@имя для упоминания)"
              : "Написать сообщение..."
          }
          disabled={disabled || sending}
          rows={2}
          className={cn(
            "flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "min-h-[64px] max-h-40"
          )}
        />
        <div className="flex flex-col justify-between flex-shrink-0">
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={cn(
              "flex items-center justify-center w-9 h-9 rounded-lg transition-colors",
              canSend
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
            aria-label="Отправить"
            type="button"
          >
            <Send className="w-4 h-4" />
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || sending}
            className={cn(
              "flex items-center justify-center w-9 h-9 rounded-lg",
              "text-muted-foreground hover:text-foreground hover:bg-muted transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
            aria-label="Прикрепить файл"
            type="button"
          >
            <Paperclip className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
