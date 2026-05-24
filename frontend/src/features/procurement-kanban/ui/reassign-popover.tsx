"use client";

import { useState } from "react";
import { Loader2, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { UserSearchSelect } from "@/shared/ui/procurement/user-search-select";
import { reassignBrandGroup } from "@/entities/quote/server-actions";
import { createClient } from "@/shared/lib/supabase/client";
import { extractErrorMessage } from "@/shared/lib/errors";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import type { KanbanBrandCard } from "../model/types";

export interface ReassignPopoverProps {
  card: KanbanBrandCard;
  users: ProcurementUserWorkload[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful reassignment — parent should resync kanban state. */
  onReassigned: () => void;
}

/**
 * Inline МОЗ reassignment popover for kanban cards that are already past
 * «Распределение». Testing 2 row 75: head_of_procurement needs to swap the
 * МОЗ on an in-flight brand-slice when someone is sick / on vacation /
 * overloaded without losing the slice's procurement_status.
 *
 * Differs from {@link AssignPopover}:
 *   - Fetches ALL items in the (quote, brand) slice, including already-
 *     assigned ones (the whole point — we're rerouting them).
 *   - Calls `reassignBrandGroup`, which keeps `procurement_status` intact
 *     and skips both brand-pin and auto-advance side effects.
 *   - Current assignee shown as context so the head knows who they're
 *     replacing.
 */
export function ReassignPopover({
  card,
  users,
  open,
  onOpenChange,
  onReassigned,
}: ReassignPopoverProps) {
  const [userId, setUserId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const brandForApi: string | null = card.brand === "" ? null : card.brand;
  const currentAssigneeLabel =
    card.procurement_user_names.length > 0
      ? card.procurement_user_names.join(", ")
      : "—";

  async function fetchSliceItemIds(): Promise<string[]> {
    const supabase = createClient();
    let query = supabase
      .from("quote_items")
      .select("id")
      .eq("quote_id", card.quote_id)
      .neq("is_unavailable", true);
    query =
      brandForApi === null
        ? query.is("brand", null)
        : query.eq("brand", brandForApi);

    const { data, error } = await query;
    if (error) throw new Error(error.message);
    return (data ?? []).map((r) => r.id);
  }

  async function handleReassign() {
    if (!userId || submitting) return;
    setSubmitting(true);
    try {
      const itemIds = await fetchSliceItemIds();
      if (itemIds.length === 0) {
        toast.info("Нет позиций в этой подгруппе");
        onReassigned();
        return;
      }
      const result = await reassignBrandGroup(itemIds, userId);
      if (!result.success) {
        toast.error(extractErrorMessage(result) ?? "Ошибка переназначения");
        return;
      }
      const userName =
        users.find((u) => u.user_id === userId)?.full_name ?? "закупщика";
      toast.success(
        `${card.idn_quote}: ${itemIds.length} поз. переназначено на ${userName}`,
      );
      setUserId("");
      onReassigned();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка переназначения";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    if (submitting) return;
    setUserId("");
    onOpenChange(false);
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger
        render={
          <button
            type="button"
            // Prevent dnd-kit from starting a drag when clicking the trigger.
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => e.stopPropagation()}
            className="mt-2 inline-flex items-center gap-1 rounded-md border border-border bg-background px-2 py-1 text-xs font-medium text-foreground hover:bg-accent/5"
            title="Переназначить МОЗ"
          >
            <RefreshCw className="size-3" />
            Переназначить
          </button>
        }
      />
      <PopoverContent align="start" side="bottom" className="w-[320px]">
        <div
          className="space-y-3"
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          <p className="text-xs text-muted-foreground">
            Текущий исполнитель:{" "}
            <span className="font-medium text-foreground">
              {currentAssigneeLabel}
            </span>
          </p>

          <UserSearchSelect
            users={users}
            value={userId}
            onValueChange={setUserId}
            disabled={submitting}
          />

          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              disabled={submitting}
            >
              Отмена
            </Button>
            <Button
              size="sm"
              onClick={handleReassign}
              disabled={!userId || submitting}
            >
              {submitting ? (
                <Loader2 size={14} className="mr-1 animate-spin" />
              ) : null}
              Переназначить
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
