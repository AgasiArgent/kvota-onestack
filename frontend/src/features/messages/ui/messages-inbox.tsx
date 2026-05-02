"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { MessageSquare, ArrowLeft, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatInput } from "@/features/quotes/ui/chat-panel/chat-input";
import { MessagesList } from "@/features/quotes/ui/chat-panel/messages-list";
import type { OrgMember } from "@/features/quotes/ui/chat-panel/chat-input";
import { useRealtimeComments } from "@/features/quotes/ui/chat-panel/use-realtime-comments";
import type { ChatListItem } from "../queries";
import type { QuoteComment } from "@/entities/quote/types";

// ---------------------------------------------------------------------------
// Relative time formatter
// ---------------------------------------------------------------------------
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин`;
  if (diffHours < 24) return `${diffHours} ч`;
  if (diffDays === 1) return "вчера";
  if (diffDays < 7) return `${diffDays} дн`;

  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
  });
}

function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen).trimEnd() + "...";
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MessagesInboxProps {
  /** Chats the user can see at all (role-scoped). Drives the "Все" tab. */
  chats: ChatListItem[];
  /**
   * Chats where the user is a responsible party (МОП ownership, МОЗ item
   * assignment, МОЛ/МОТ quote-level assignment). Drives "Мои КП".
   * Server-resolved via {@link resolveMyAssignedQuoteIds}.
   */
  myChats: ChatListItem[];
  initialFilter?: "all" | "my";
  userId: string;
  orgId: string;
  orgMembers: OrgMember[];
}

// ---------------------------------------------------------------------------
// Chat Panel (right side) — wraps useRealtimeComments for a selected quote
// ---------------------------------------------------------------------------

function ActiveChat({
  quoteId,
  idnQuote,
  userId,
  orgId,
  initialComments,
  orgMembers,
}: {
  quoteId: string;
  idnQuote: string;
  userId: string;
  orgId: string;
  initialComments: QuoteComment[];
  orgMembers: OrgMember[];
}) {
  const { messages, sendMessage, isConnected } = useRealtimeComments(
    quoteId,
    userId,
    initialComments
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const initialRenderRef = useRef(true);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: initialRenderRef.current ? "instant" : "smooth",
    });
    initialRenderRef.current = false;
  }, [messages.length]);

  // Reset initial render flag when quote changes
  useEffect(() => {
    initialRenderRef.current = true;
  }, [quoteId]);

  const handleSend = useCallback(
    async (body: string, mentions?: string[]) => {
      await sendMessage(body, mentions);
    },
    [sendMessage]
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-background">
        <div className="flex items-center gap-2 min-w-0">
          <Link
            href={`/quotes/${quoteId}`}
            className="text-sm font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-1"
          >
            {idnQuote}
            <ExternalLink className="w-3 h-3" />
          </Link>
          <span
            className={cn(
              "flex-shrink-0 w-2 h-2 rounded-full",
              isConnected ? "bg-green-500" : "bg-gray-300"
            )}
            title={isConnected ? "Подключено" : "Нет соединения"}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-3">
        {messages.length === 0 ? (
          <div className="flex items-center justify-center h-full px-6">
            <p className="text-sm text-muted-foreground text-center">
              Нет сообщений
            </p>
          </div>
        ) : (
          <>
            <MessagesList messages={messages} userId={userId} />
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <ChatInput
        onSend={handleSend}
        orgMembers={orgMembers}
        quoteId={quoteId}
        orgId={orgId}
        userId={userId}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Inbox Component
// ---------------------------------------------------------------------------

export function MessagesInbox({
  chats,
  myChats,
  initialFilter = "all",
  userId,
  orgId,
  orgMembers,
}: MessagesInboxProps) {
  const [filter, setFilter] = useState<"all" | "my">(initialFilter);
  const [selectedQuoteId, setSelectedQuoteId] = useState<string | null>(null);
  const [comments, setComments] = useState<QuoteComment[]>([]);
  const [loadingComments, setLoadingComments] = useState(false);
  const [mobileShowChat, setMobileShowChat] = useState(false);

  // "Мои КП" comes from a server-resolved set of personally-assigned quotes —
  // not from "did I author the last message" (the old client filter, which
  // hid every chat where the user was a participant but had not yet replied).
  const filteredChats = filter === "my" ? myChats : chats;

  const selectedChat = filteredChats.find((c) => c.quoteId === selectedQuoteId);

  // Load comments when a chat is selected
  useEffect(() => {
    if (!selectedQuoteId) {
      setComments([]);
      return;
    }

    let cancelled = false;
    setLoadingComments(true);

    // Use the browser client to fetch comments directly
    async function loadComments() {
      const { createClient } = await import("@/shared/lib/supabase/client");
      const supabase = createClient();

      const { data } = await supabase
        .from("quote_comments")
        .select("*")
        .eq("quote_id", selectedQuoteId!)
        .order("created_at", { ascending: true });

      if (cancelled) return;

      if (!data?.length) {
        setComments([]);
        setLoadingComments(false);
        return;
      }

      // Batch-resolve user profiles
      const userIds = [...new Set(data.map((c) => c.user_id))];

      // Role lookup goes through ``user_roles`` (the actual mapping table)
      // rather than ``organization_members.roles!inner(slug)`` — the
      // direct FK on ``organization_members.role_id`` was dropped in
      // migration 255, so the embedded join silently returned an empty
      // map, which the chat then rendered as "unknown" for every sender.
      // МОЗ Тест 2026-05-01 fail #35.
      const [profilesRes, rolesRes] = await Promise.all([
        supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", userIds),
        supabase
          .from("user_roles")
          .select("user_id, roles!inner(slug)")
          .in("user_id", userIds),
      ]);

      if (cancelled) return;

      const profileMap = new Map(
        (profilesRes.data ?? []).map((p) => [p.user_id, p])
      );
      // Pick the first non-admin role per user (stable display preference —
      // admin users that also have an operational role render as that role).
      const roleMap = new Map<string, string>();
      for (const row of rolesRes.data ?? []) {
        const slug = (row.roles as unknown as { slug: string } | null)?.slug;
        if (!slug) continue;
        const existing = roleMap.get(row.user_id);
        if (!existing || (existing === "admin" && slug !== "admin")) {
          roleMap.set(row.user_id, slug);
        }
      }

      const resolved: QuoteComment[] = data.map((c) => {
        const profile = profileMap.get(c.user_id);
        return {
          ...c,
          mentions: (c.mentions ?? null) as string[] | null,
          user_profile: profile
            ? {
                id: profile.user_id,
                full_name: profile.full_name ?? "",
                role_slug: roleMap.get(c.user_id) ?? "unknown",
              }
            : null,
        };
      });

      setComments(resolved);
      setLoadingComments(false);
    }

    loadComments();
    return () => {
      cancelled = true;
    };
  }, [selectedQuoteId]);

  function handleSelectChat(quoteId: string) {
    setSelectedQuoteId(quoteId);
    setMobileShowChat(true);
  }

  function handleBack() {
    setMobileShowChat(false);
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] border border-border rounded-lg overflow-hidden bg-background">
      {/* Left Panel — Chat List */}
      <div
        className={cn(
          "w-full md:w-[360px] md:min-w-[360px] border-r border-border flex flex-col",
          mobileShowChat && "hidden md:flex"
        )}
      >
        {/* Filter tabs */}
        <div className="flex border-b border-border px-3 py-2 gap-2">
          <button
            onClick={() => setFilter("all")}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              filter === "all"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            Все
          </button>
          <button
            onClick={() => setFilter("my")}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              filter === "my"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            )}
          >
            Мои КП
          </button>
        </div>

        {/* Chat list */}
        <div className="flex-1 overflow-y-auto">
          {filteredChats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-sm px-6 text-center">
              <MessageSquare className="w-8 h-8 mb-2 opacity-50" />
              <p>Нет обсуждений</p>
            </div>
          ) : (
            filteredChats.map((chat) => (
              <button
                key={chat.quoteId}
                onClick={() => handleSelectChat(chat.quoteId)}
                className={cn(
                  "w-full text-left px-4 py-3 border-b border-border/50 hover:bg-muted/50 transition-colors",
                  selectedQuoteId === chat.quoteId && "bg-muted"
                )}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-foreground">
                    {chat.idnQuote}
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    {chat.lastMessageAt
                      ? formatRelativeTime(chat.lastMessageAt)
                      : ""}
                  </span>
                </div>
                {chat.customerName && (
                  <p className="text-xs text-muted-foreground mb-1 truncate">
                    {chat.customerName}
                  </p>
                )}
                <p className="text-xs text-muted-foreground/80 truncate italic">
                  {chat.commentCount === 0 ? (
                    <span className="text-muted-foreground/60">
                      Нет сообщений
                    </span>
                  ) : (
                    <>
                      {chat.lastMessageUserName && (
                        <span className="font-medium text-muted-foreground not-italic">
                          {chat.lastMessageUserName.split(" ")[0]}:{" "}
                        </span>
                      )}
                      <span className="not-italic">
                        {truncate(chat.lastMessageBody, 60)}
                      </span>
                    </>
                  )}
                </p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right Panel — Selected Chat */}
      <div
        className={cn(
          "flex-1 flex flex-col",
          !mobileShowChat && "hidden md:flex"
        )}
      >
        {/* Mobile back button */}
        {mobileShowChat && (
          <button
            onClick={handleBack}
            className="md:hidden flex items-center gap-1 px-4 py-2 text-sm text-muted-foreground hover:text-foreground border-b border-border"
          >
            <ArrowLeft className="w-4 h-4" />
            Назад
          </button>
        )}

        {!selectedQuoteId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <div className="text-center">
              <MessageSquare className="w-10 h-10 mx-auto mb-3 opacity-30" />
              <p>Выберите чат из списка</p>
            </div>
          </div>
        ) : loadingComments ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            Загрузка...
          </div>
        ) : (
          <ActiveChat
            key={selectedQuoteId}
            quoteId={selectedQuoteId}
            idnQuote={selectedChat?.idnQuote ?? ""}
            userId={userId}
            orgId={orgId}
            initialComments={comments}
            orgMembers={orgMembers}
          />
        )}
      </div>
    </div>
  );
}
