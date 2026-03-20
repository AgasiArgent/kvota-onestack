"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/shared/lib/supabase/client";
import { sendQuoteComment } from "@/entities/quote";
import type { QuoteComment } from "@/entities/quote";
import type { RealtimeChannel } from "@supabase/supabase-js";

interface UseRealtimeCommentsReturn {
  messages: QuoteComment[];
  sendMessage: (body: string) => Promise<void>;
  isConnected: boolean;
}

export function useRealtimeComments(
  quoteId: string,
  userId: string,
  initialComments: QuoteComment[]
): UseRealtimeCommentsReturn {
  const [messages, setMessages] = useState<QuoteComment[]>(initialComments);
  const [isConnected, setIsConnected] = useState(false);
  const channelRef = useRef<RealtimeChannel | null>(null);
  const supabaseRef = useRef(createClient());

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

          // Skip if we already have this message (optimistic add)
          setMessages((prev) => {
            if (prev.some((m) => m.id === newRow.id)) return prev;

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
              },
            ];
          });
        }
      )
      .subscribe((status) => {
        setIsConnected(status === "SUBSCRIBED");
      });

    channelRef.current = channel;

    return () => {
      channel.unsubscribe();
      channelRef.current = null;
    };
  }, [quoteId]);

  const sendMessage = useCallback(
    async (body: string) => {
      const trimmed = body.trim();
      if (!trimmed) return;

      // Optimistic: add message locally before server confirms
      const optimisticId = crypto.randomUUID();
      const optimisticMessage: QuoteComment = {
        id: optimisticId,
        quote_id: quoteId,
        user_id: userId,
        body: trimmed,
        mentions: null,
        created_at: new Date().toISOString(),
        user_profile: null, // Will be resolved when realtime event arrives
      };

      setMessages((prev) => [...prev, optimisticMessage]);

      try {
        const result = await sendQuoteComment(quoteId, userId, trimmed);
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
      } catch {
        // Remove optimistic message on failure
        setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
      }
    },
    [quoteId, userId]
  );

  return { messages, sendMessage, isConnected };
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
