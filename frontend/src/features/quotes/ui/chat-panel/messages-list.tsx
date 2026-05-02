"use client";

import { Fragment } from "react";
import type { QuoteComment } from "@/entities/quote/types";
import { ChatMessage } from "./chat-message";

/**
 * Telegram-style chat list — inserts a sticky-style date separator between
 * consecutive messages from different calendar days. Today / Yesterday /
 * "28 янв" / "12.04.2025" labels (МОЗ Тест 2026-05-01 fail #36).
 *
 * Caller is responsible for sorting `messages` ascending by `created_at`.
 * Both ``ChatPanel`` (right-side floating drawer) and ``MessagesInbox``
 * (full /messages route) render through this component to keep the
 * separators behaviour identical.
 */

interface MessagesListProps {
  messages: QuoteComment[];
  userId: string;
}

function formatDateSeparator(value: string): string {
  const date = new Date(value);
  const now = new Date();

  const startOfToday = new Date(now);
  startOfToday.setHours(0, 0, 0, 0);
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);

  if (date >= startOfToday) return "Сегодня";
  if (date >= startOfYesterday) return "Вчера";

  if (date.getFullYear() === now.getFullYear()) {
    return date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      timeZone: "Europe/Moscow",
    });
  }

  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Europe/Moscow",
  });
}

function dayKey(value: string): string {
  // Construct a "YYYY-MM-DD" key in Europe/Moscow time so messages around
  // midnight don't accidentally split into two days for a user east of UTC.
  const d = new Date(value);
  const moscow = new Date(
    d.toLocaleString("en-US", { timeZone: "Europe/Moscow" })
  );
  const y = moscow.getFullYear();
  const m = String(moscow.getMonth() + 1).padStart(2, "0");
  const day = String(moscow.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function MessagesList({ messages, userId }: MessagesListProps) {
  let lastKey: string | null = null;
  return (
    <>
      {messages.map((msg) => {
        const key = dayKey(msg.created_at);
        const showSeparator = key !== lastKey;
        lastKey = key;
        return (
          <Fragment key={msg.id}>
            {showSeparator && (
              <div className="flex items-center justify-center px-4 py-2">
                <span className="text-[11px] text-muted-foreground bg-muted/60 rounded-full px-2.5 py-0.5">
                  {formatDateSeparator(msg.created_at)}
                </span>
              </div>
            )}
            <ChatMessage comment={msg} isOwn={msg.user_id === userId} />
          </Fragment>
        );
      })}
    </>
  );
}
