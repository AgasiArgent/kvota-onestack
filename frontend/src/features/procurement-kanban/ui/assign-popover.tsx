"use client";

import { useState } from "react";
import { Loader2, Pin } from "lucide-react";
import { toast } from "sonner";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { UserSearchSelect } from "@/shared/ui/procurement/user-search-select";
import { assignBrandGroup } from "@/entities/quote";
import { createClient } from "@/shared/lib/supabase/client";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";
import type { KanbanBrandCard } from "../model/types";

export interface AssignPopoverProps {
  card: KanbanBrandCard;
  users: ProcurementUserWorkload[];
  orgId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Optional inline notice shown above the user select (e.g. drag-guard hint). */
  notice?: string;
  /** Called after a successful assignment — parent should resync kanban state. */
  onAssigned: () => void;
}

/**
 * Inline МОЗ assignment popover anchored to a kanban card in the
 * "Распределение" column. Fetches the unassigned item IDs for the
 * (quote, brand) slice on demand and calls the shared `assignBrandGroup`
 * server action.
 */
export function AssignPopover({
  card,
  users,
  orgId,
  open,
  onOpenChange,
  notice,
  onAssigned,
}: AssignPopoverProps) {
  const [userId, setUserId] = useState("");
  const [pinBrand, setPinBrand] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Kanban uses brand="" for unbranded slices; the server action expects `null`.
  const brandForApi: string | null = card.brand === "" ? null : card.brand;
  const canPinBrand = brandForApi !== null;

  async function fetchUnassignedItemIds(): Promise<string[]> {
    const supabase = createClient();
    let query = supabase
      .from("quote_items")
      .select("id")
      .eq("quote_id", card.quote_id)
      .is("assigned_procurement_user", null)
      .neq("is_unavailable", true);
    query = brandForApi === null
      ? query.is("brand", null)
      : query.eq("brand", brandForApi);

    const { data, error } = await query;
    if (error) throw new Error(error.message);
    return (data ?? []).map((r) => r.id);
  }

  async function handleAssign() {
    if (!userId || submitting) return;
    setSubmitting(true);
    try {
      const itemIds = await fetchUnassignedItemIds();
      if (itemIds.length === 0) {
        toast.info("Нет нераспределённых позиций для этой подгруппы");
        onAssigned();
        return;
      }
      const result = await assignBrandGroup(
        itemIds,
        userId,
        pinBrand && canPinBrand,
        orgId,
        brandForApi
      );
      if (!result.success) {
        toast.error(result.error ?? "Ошибка назначения");
        return;
      }
      const userName =
        users.find((u) => u.user_id === userId)?.full_name ?? "закупщика";
      toast.success(
        `${card.idn_quote}: ${itemIds.length} поз. назначено на ${userName}`
      );
      // Reset local state; parent will close popover via onAssigned.
      setUserId("");
      setPinBrand(false);
      onAssigned();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка назначения";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  function handleCancel() {
    if (submitting) return;
    setUserId("");
    setPinBrand(false);
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
            className="mt-2 inline-flex items-center rounded-md border border-border bg-background px-2 py-1 text-xs font-medium text-foreground hover:bg-accent/5"
          >
            Распределить
          </button>
        }
      />
      <PopoverContent align="start" side="bottom" className="w-[320px]">
        <div
          className="space-y-3"
          // Keep pointer events on the popover from bubbling to the draggable card.
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => e.stopPropagation()}
        >
          {notice && (
            <p className="text-xs text-amber-600 dark:text-amber-400">{notice}</p>
          )}

          <UserSearchSelect
            users={users}
            value={userId}
            onValueChange={setUserId}
            disabled={submitting}
          />

          <label
            className={`flex items-center gap-1.5 text-xs ${
              canPinBrand
                ? "cursor-pointer text-foreground"
                : "cursor-not-allowed text-muted-foreground opacity-60"
            }`}
            title={
              canPinBrand
                ? undefined
                : "Нельзя закрепить без бренда"
            }
          >
            <Checkbox
              checked={pinBrand}
              onCheckedChange={(checked) =>
                setPinBrand(checked === true)
              }
              disabled={!canPinBrand || submitting}
              className="size-3.5"
            />
            <Pin size={12} className="text-muted-foreground" />
            <span>
              Закрепить бренд{card.brand ? ` ${card.brand}` : ""} за этим МОЗ
            </span>
          </label>

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
              onClick={handleAssign}
              disabled={!userId || submitting}
            >
              {submitting ? (
                <Loader2 size={14} className="mr-1 animate-spin" />
              ) : null}
              Назначить
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
