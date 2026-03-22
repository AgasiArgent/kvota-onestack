"use client";

import {
  useState,
  useRef,
  useCallback,
  useEffect,
  type KeyboardEvent,
} from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";

export interface OrgMember {
  userId: string;
  fullName: string;
}

interface ChatInputProps {
  onSend: (body: string, mentions?: string[]) => Promise<void>;
  disabled?: boolean;
  orgMembers?: OrgMember[];
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

export function ChatInput({ onSend, disabled, orgMembers }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const [mentions, setMentions] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
    if (!trimmed || sending) return;

    setSending(true);
    try {
      await onSend(trimmed, mentions.length > 0 ? mentions : undefined);
      setValue("");
      setMentions([]);
      setMentionQuery(null);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  }, [value, sending, onSend, mentions]);

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

  const canSend = value.trim().length > 0 && !sending && !disabled;
  const showDropdown = mentionQuery !== null && filteredMembers.length > 0;

  return (
    <div className="relative border-t border-border bg-background px-4 py-3">
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

      <div className="flex items-end gap-2">
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
          rows={1}
          className={cn(
            "flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
            "disabled:cursor-not-allowed disabled:opacity-50",
            "max-h-24"
          )}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={cn(
            "flex-shrink-0 flex items-center justify-center w-9 h-9 rounded-lg",
            "transition-colors",
            canSend
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
          aria-label="Отправить"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
