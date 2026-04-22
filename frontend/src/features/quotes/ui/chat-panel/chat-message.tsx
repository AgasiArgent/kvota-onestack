"use client";

import { cn } from "@/lib/utils";
import type { QuoteComment } from "@/entities/quote/types";
import { MessageAttachment } from "./message-attachment";

const ROLE_BADGE_COLORS: Record<string, string> = {
  sales: "bg-blue-100 text-blue-700",
  head_of_sales: "bg-blue-100 text-blue-700",
  procurement: "bg-amber-100 text-amber-700",
  head_of_procurement: "bg-amber-100 text-amber-700",
  logistics: "bg-green-100 text-green-700",
  head_of_logistics: "bg-green-100 text-green-700",
  customs: "bg-purple-100 text-purple-700",
  finance: "bg-emerald-100 text-emerald-700",
  admin: "bg-slate-100 text-slate-700",
  quote_controller: "bg-indigo-100 text-indigo-700",
  spec_controller: "bg-indigo-100 text-indigo-700",
  top_manager: "bg-slate-100 text-slate-700",
};

const ROLE_AVATAR_COLORS: Record<string, string> = {
  sales: "bg-blue-500",
  head_of_sales: "bg-blue-500",
  procurement: "bg-amber-500",
  head_of_procurement: "bg-amber-500",
  logistics: "bg-green-500",
  head_of_logistics: "bg-green-500",
  customs: "bg-purple-500",
  finance: "bg-emerald-500",
  admin: "bg-slate-500",
  quote_controller: "bg-indigo-500",
  spec_controller: "bg-indigo-500",
  top_manager: "bg-slate-500",
};

const ROLE_LABELS: Record<string, string> = {
  sales: "Продажи",
  head_of_sales: "Рук. продаж",
  procurement: "Закупки",
  head_of_procurement: "Рук. закупок",
  logistics: "Логистика",
  head_of_logistics: "Рук. логистики",
  customs: "Таможня",
  finance: "Финансы",
  admin: "Админ",
  quote_controller: "Контроль КП",
  spec_controller: "Контроль спец.",
  top_manager: "Руководитель",
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMin < 1) return "только что";
  if (diffMin < 60) return `${diffMin} мин назад`;
  if (diffHours < 24) return `${diffHours} ч назад`;
  if (diffDays === 1) return "вчера";
  if (diffDays < 7) return `${diffDays} дн назад`;

  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "short",
    timeZone: "Europe/Moscow",
    });
}

interface ChatMessageProps {
  comment: QuoteComment;
  isOwn: boolean;
}

export function ChatMessage({ comment, isOwn }: ChatMessageProps) {
  const profile = comment.user_profile;
  const roleSlug = profile?.role_slug ?? "unknown";
  const fullName = profile?.full_name || "...";
  const firstLetter = fullName.charAt(0).toUpperCase() || "?";

  const avatarColor = ROLE_AVATAR_COLORS[roleSlug] ?? "bg-gray-400";
  const badgeColor = ROLE_BADGE_COLORS[roleSlug] ?? "bg-gray-100 text-gray-700";
  const roleLabel = ROLE_LABELS[roleSlug] ?? roleSlug;

  return (
    <div className={cn("flex gap-2.5 px-4 py-2", isOwn && "flex-row-reverse")}>
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium",
          avatarColor
        )}
      >
        {firstLetter}
      </div>

      {/* Content */}
      <div className={cn("flex flex-col max-w-[260px]", isOwn && "items-end")}>
        {/* Name + Role + Time */}
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="text-xs font-medium text-foreground truncate max-w-[120px]">
            {fullName}
          </span>
          <span
            className={cn(
              "inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none",
              badgeColor
            )}
          >
            {roleLabel}
          </span>
          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
            {formatRelativeTime(comment.created_at)}
          </span>
        </div>

        {/* Message body */}
        {comment.body && (
          <div
            className={cn(
              "rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words",
              isOwn
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-foreground"
            )}
          >
            {comment.body}
          </div>
        )}

        {/* Attachments */}
        {comment.attachments && comment.attachments.length > 0 && (
          <div className={cn("flex flex-col gap-1", isOwn && "items-end")}>
            {comment.attachments.map((att) => (
              <MessageAttachment key={att.id} attachment={att} isOwn={isOwn} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
