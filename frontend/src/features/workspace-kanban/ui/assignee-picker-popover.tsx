"use client";

import { useState } from "react";
import { Loader2, Search, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
// Direct import (not barrel) — barrel exports server-only queries that break
// "use client" bundling.
import {
  UserAvatarChip,
  type UserAvatarChipUser,
} from "@/entities/user/ui/user-avatar-chip";
import { cn } from "@/lib/utils";
// `reassignInvoice` lives in the workspace-logistics slice (head-only gate).
// Imported here directly: the kanban "use server" module cannot re-export it.
import { reassignInvoice } from "@/features/workspace-logistics";
import type { WorkspaceKanbanCard } from "../model/types";

export interface AssigneePickerPopoverProps {
  card: WorkspaceKanbanCard;
  domain: "logistics" | "customs";
  teamUsers: UserAvatarChipUser[];
  /** Controlled open state — the board opens this on a head drag. */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful (re)assignment. */
  onAssigned: () => void;
  /** Called when the picker closes without assigning (rollback on drag). */
  onCancelled: () => void;
}

/**
 * AssigneePickerPopover — head-only assignee picker (REQ-8). The trigger is an
 * inline button on the card; the board can also open it programmatically when
 * a head drags a card into «В работе».
 *
 * A searchable user list (project standard: every select is searchable) →
 * `reassignInvoice` server action.
 *
 * Adapted from `procurement-kanban/ui/assign-popover.tsx`; differs in that it
 * assigns a single invoice (not a brand group) and uses the workspace team
 * roster instead of procurement workload rows.
 */
export function AssigneePickerPopover({
  card,
  domain,
  teamUsers,
  open,
  onOpenChange,
  onAssigned,
  onCancelled,
}: AssigneePickerPopoverProps) {
  const [query, setQuery] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const filtered = teamUsers.filter((u) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      u.name.toLowerCase().includes(q) ||
      (u.email?.toLowerCase().includes(q) ?? false)
    );
  });

  async function handleAssign(userId: string) {
    if (submitting) return;
    setSubmitting(true);
    try {
      await reassignInvoice(card.id, domain, userId);
      const name =
        teamUsers.find((u) => u.id === userId)?.name ?? "сотрудника";
      toast.success(`${card.idn}: назначено на ${name}`);
      setQuery("");
      onAssigned();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка назначения";
      toast.error(msg);
      onCancelled();
    } finally {
      setSubmitting(false);
    }
  }

  function handleOpenChange(next: boolean) {
    if (submitting) return;
    if (!next) {
      setQuery("");
      onCancelled();
    }
    onOpenChange(next);
  }

  const triggerLabel =
    card.assignedUserId != null ? "Переназначить" : "Назначить";

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            // Keep dnd-kit from starting a drag when clicking the trigger.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            className="mt-2 inline-flex items-center gap-1 rounded-md border border-border-light bg-background px-2 py-1 text-xs font-medium text-text hover:bg-sidebar"
          >
            <UserPlus size={12} strokeWidth={2} aria-hidden />
            {triggerLabel}
          </button>
        }
      />
      <PopoverContent
        align="start"
        side="bottom"
        className="w-72 p-0"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-border-light p-2">
          <p className="mb-1.5 px-1 text-xs font-medium text-text">
            Назначить {domain === "logistics" ? "логиста" : "таможенника"}
          </p>
          <div className="relative">
            <Search
              size={12}
              strokeWidth={2}
              className="absolute left-2 top-1/2 -translate-y-1/2 text-text-subtle"
              aria-hidden
            />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Поиск..."
              className="h-8 pl-7 text-sm"
              autoFocus
              disabled={submitting}
            />
          </div>
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {submitting ? (
            <div className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-text-muted">
              <Loader2 size={14} className="animate-spin" aria-hidden />
              Назначаем...
            </div>
          ) : filtered.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs text-text-subtle">
              Никого не найдено
            </div>
          ) : (
            filtered.map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={() => handleAssign(u.id)}
                disabled={submitting}
                className={cn(
                  "w-full rounded-sm px-2 py-1.5 text-left",
                  "hover:bg-sidebar transition-colors",
                  "disabled:opacity-50",
                  card.assignedUserId === u.id && "bg-sidebar",
                )}
              >
                <UserAvatarChip user={u} size="sm" showEmail />
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
