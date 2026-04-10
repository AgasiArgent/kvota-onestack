"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/shared/lib/supabase/client";
import { sendQuoteComment } from "@/entities/quote/mutations";
import { apiClient } from "@/shared/lib/api";
import type { QuoteComment } from "@/entities/quote/types";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface UseRealtimeCommentsReturn {
  messages: QuoteComment[];
  sendMessage: (
    body: string,
    mentions?: string[],
    attachmentDocumentIds?: string[]
  ) => Promise<void>;
  isConnected: boolean;
}

export function useRealtimeComments(
  quoteId: string,
  userId: string,
  initialComments: QuoteComment[],
  onNewMessage?: () => void
): UseRealtimeCommentsReturn {
  const onNewMessageRef = useRef(onNewMessage);
  onNewMessageRef.current = onNewMessage;
  const [messages, setMessages] = useState<QuoteComment[]>(initialComments);
  const [isConnected, setIsConnected] = useState(false);
  const channelRef = useRef<RealtimeChannel | null>(null);
  const supabaseRef = useRef(createClient());

  // Track IDs of messages we sent (to skip realtime duplicates)
  const sentIdsRef = useRef(new Set<string>());

  // Sync initial comments when they change (e.g. server re-fetch)
  useEffect(() => {
    setMessages(initialComments);
  }, [initialComments]);

  useEffect(() => {
    const supabase = supabaseRef.current;

    const channel = supabase
      .channel(`quote-comments:${quoteId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "kvota",
          table: "quote_comments",
          filter: `quote_id=eq.${quoteId}`,
        },
        async (payload) => {
          const newRow = payload.new as {
            id: string;
            quote_id: string;
            user_id: string;
            body: string;
            mentions: string[] | null;
            created_at: string;
          };

          // Skip if this is our own message (already added optimistically)
          if (sentIdsRef.current.has(newRow.id)) {
            sentIdsRef.current.delete(newRow.id);
            return;
          }

          // Skip if we already have this message
          setMessages((prev) => {
            if (prev.some((m) => m.id === newRow.id)) return prev;

            // Notify wrapper about new message (for unread badge)
            onNewMessageRef.current?.();

            // Fetch user profile for the new message
            resolveUserProfile(supabase, newRow.user_id).then((profile) => {
              setMessages((current) =>
                current.map((m) =>
                  m.id === newRow.id && !m.user_profile
                    ? { ...m, user_profile: profile }
                    : m
                )
              );
            });

            // Fetch attachments for the new message (if any). The realtime
            // payload only contains the comment row — attachments live in
            // the documents table and are linked async by sendQuoteComment.
            resolveAttachments(supabase, newRow.id).then((attachments) => {
              if (attachments.length === 0) return;
              setMessages((current) =>
                current.map((m) =>
                  m.id === newRow.id ? { ...m, attachments } : m
                )
              );
            });

            return [
              ...prev,
              {
                id: newRow.id,
                quote_id: newRow.quote_id,
                user_id: newRow.user_id,
                body: newRow.body,
                mentions: newRow.mentions,
                created_at: newRow.created_at,
                user_profile: null,
                attachments: [],
              },
            ];
          });
        }
      )
      .subscribe((status, _err) => {
        if (status === "SUBSCRIBED") {
          setIsConnected(true);
        } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT" || status === "CLOSED") {
          setIsConnected(false);
        }
      });

    channelRef.current = channel;

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [quoteId]);

  const sendMessage = useCallback(
    async (
      body: string,
      mentionIds?: string[],
      attachmentDocumentIds?: string[]
    ) => {
      const trimmed = body.trim();
      const hasAttachments =
        attachmentDocumentIds !== undefined && attachmentDocumentIds.length > 0;
      if (!trimmed && !hasAttachments) return;

      // Optimistic: add message locally before server confirms
      const optimisticId = crypto.randomUUID();
      const optimisticMessage: QuoteComment = {
        id: optimisticId,
        quote_id: quoteId,
        user_id: userId,
        body: trimmed,
        mentions: mentionIds ?? null,
        created_at: new Date().toISOString(),
        user_profile: null, // Will be resolved when realtime event arrives
      };

      setMessages((prev) => [...prev, optimisticMessage]);

      try {
        const result = await sendQuoteComment(
          quoteId,
          userId,
          trimmed,
          mentionIds,
          attachmentDocumentIds
        );
        // Track this ID so realtime event is skipped
        sentIdsRef.current.add(result.id);
        // Replace optimistic message with server result
        setMessages((prev) =>
          prev.map((m) =>
            m.id === optimisticId
              ? {
                  ...result,
                  mentions: (result.mentions ?? null) as string[] | null,
                  user_profile: m.user_profile,
                }
              : m
          )
        );

        // Fire-and-forget: send Telegram notification (best-effort)
        const mentions = (result.mentions ?? []) as string[];
        apiClient("/chat/notify", {
          method: "POST",
          body: JSON.stringify({
            quote_id: quoteId,
            body: trimmed,
            mentions,
          }),
        }).catch(() => {});
      } catch {
        // Remove optimistic message on failure
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      }
    },
    [quoteId, userId]
  );

  return { messages, sendMessage, isConnected };
}

async function resolveAttachments(
  supabase: ReturnType<typeof createClient>,
  commentId: string
): Promise<NonNullable<QuoteComment["attachments"]>> {
  try {
    const { data } = await supabase
      .from("documents")
      .select(
        "id, original_filename, storage_path, mime_type, file_size_bytes"
      )
      .eq("comment_id", commentId);
    return (data ?? []).map((d) => ({
      id: d.id,
      original_filename: d.original_filename,
      storage_path: d.storage_path,
      mime_type: d.mime_type,
      file_size_bytes: d.file_size_bytes,
    }));
  } catch {
    return [];
  }
}

async function resolveUserProfile(
  supabase: ReturnType<typeof createClient>,
  userId: string
): Promise<QuoteComment["user_profile"]> {
  try {
    const [profileRes, memberRes] = await Promise.all([
      supabase
        .from("user_profiles")
        .select("user_id, full_name")
        .eq("user_id", userId)
        .single(),
      supabase
        .from("organization_members")
        .select("user_id, roles!inner(slug)")
        .eq("user_id", userId)
        .limit(1)
        .single(),
    ]);

    const fullName = profileRes.data?.full_name ?? "";
    const roleSlug =
      (memberRes.data?.roles as unknown as { slug: string })?.slug ?? "unknown";

    return { id: userId, full_name: fullName, role_slug: roleSlug };
  } catch {
    return { id: userId, full_name: "", role_slug: "unknown" };
  }
}
