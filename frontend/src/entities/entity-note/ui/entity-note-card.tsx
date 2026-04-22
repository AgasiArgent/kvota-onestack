import type { ReactNode } from "react";
import { Pin, MoreHorizontal, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { UserAvatarChip } from "@/entities/user/ui/user-avatar-chip";
import { cn } from "@/lib/utils";

/**
 * EntityNoteCard — one comment row for EntityNotesPanel.
 *
 * Displays: author, role, relative timestamp, body, visibility indicator,
 * pin/delete actions (author or privileged role only).
 *
 * Source: kvota.entity_notes row + joined author user.
 */

export interface EntityNoteCardData {
  id: string;
  body: string;
  authorRole: string;
  author: {
    id: string;
    name: string;
    email?: string;
    avatarUrl?: string | null;
  };
  visibleTo: string[]; // role slugs or ['*']
  pinned: boolean;
  createdAt: string | Date;
}

interface EntityNoteCardProps {
  note: EntityNoteCardData;
  canModify: boolean;
  onTogglePin: (id: string) => void;
  onDelete: (id: string) => void;
}

const ROLE_LABEL_RU: Record<string, string> = {
  sales: "МОП",
  procurement: "МОЗ",
  logistics: "Логист",
  customs: "Таможенник",
  head_of_sales: "Рук. продаж",
  head_of_procurement: "Рук. закупок",
  head_of_logistics: "Рук. логистики",
  head_of_customs: "Рук. таможни",
  admin: "Админ",
  finance: "Финансы",
  top_manager: "ТОП",
};

function roleLabel(slug: string): string {
  return ROLE_LABEL_RU[slug] ?? slug;
}

function formatRelative(value: string | Date): string {
  const then = new Date(value).getTime();
  const now = Date.now();
  const diffSec = Math.max(0, Math.round((now - then) / 1000));
  if (diffSec < 60) return "только что";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour} ч назад`;
  const diffDay = Math.round(diffHour / 24);
  if (diffDay < 7) return `${diffDay} дн назад`;
  return new Date(value).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "short",
  });
}

function visibilityLabel(visibleTo: string[]): string {
  if (visibleTo.includes("*")) return "Видно всем";
  if (visibleTo.length === 1) return `Видно: ${roleLabel(visibleTo[0])}`;
  return `Видно: ${visibleTo.map(roleLabel).join(", ")}`;
}

export function EntityNoteCard({
  note,
  canModify,
  onTogglePin,
  onDelete,
}: EntityNoteCardProps) {
  return (
    <article
      className={cn(
        "rounded-md border border-border-light bg-card p-3",
        note.pinned && "border-accent/30 bg-accent-subtle/50",
      )}
    >
      <header className="flex items-start gap-2 mb-2">
        <UserAvatarChip user={note.author} size="sm" />
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="text-sm font-medium text-text truncate">
              {note.author.name}
            </span>
            <span className="text-xs text-text-muted">{roleLabel(note.authorRole)}</span>
          </div>
          <div className="text-xs text-text-subtle tabular-nums">
            {formatRelative(note.createdAt)}
          </div>
        </div>
        <NoteActions
          pinned={note.pinned}
          canModify={canModify}
          onTogglePin={() => onTogglePin(note.id)}
          onDelete={() => onDelete(note.id)}
        />
      </header>
      <p className="text-sm text-text whitespace-pre-wrap break-words">
        {note.body}
      </p>
      <footer className="mt-2 flex items-center gap-1.5 text-xs text-text-subtle">
        <Tooltip>
          <TooltipTrigger render={<span className="inline-flex items-center gap-1 cursor-default" />}>
            <Eye size={12} strokeWidth={2} aria-hidden />
            <span>{visibilityLabel(note.visibleTo)}</span>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="text-xs">
            {note.visibleTo.includes("*")
              ? "Видят все роли в организации"
              : note.visibleTo.map(roleLabel).join(" · ")}
          </TooltipContent>
        </Tooltip>
        {note.pinned && (
          <span className="inline-flex items-center gap-1 text-accent">
            <Pin size={12} strokeWidth={2} aria-hidden />
            Закреплено
          </span>
        )}
      </footer>
    </article>
  );
}

function NoteActions({
  pinned,
  canModify,
  onTogglePin,
  onDelete,
}: {
  pinned: boolean;
  canModify: boolean;
  onTogglePin: () => void;
  onDelete: () => void;
}): ReactNode {
  if (!canModify) return null;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-text-muted hover:text-text"
            aria-label="Действия с заметкой"
          />
        }
      >
        <MoreHorizontal size={14} strokeWidth={2} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        <DropdownMenuItem onSelect={onTogglePin}>
          <Pin size={14} strokeWidth={2} className="mr-2" aria-hidden />
          {pinned ? "Открепить" : "Закрепить"}
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={onDelete}
          className="text-error focus:text-error focus:bg-error-bg"
        >
          Удалить
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
