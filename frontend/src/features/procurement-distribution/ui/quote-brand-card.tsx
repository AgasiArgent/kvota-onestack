"use client";

import { useState } from "react";
import { Loader2, Pin } from "lucide-react";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { UserSearchSelect } from "@/shared/ui/procurement/user-search-select";
import { assignBrandGroup } from "@/entities/quote";
import type {
  QuoteWithBrandGroups,
  BrandGroup,
  ProcurementUserWorkload,
} from "../model/types";

interface Props {
  data: QuoteWithBrandGroups;
  users: ProcurementUserWorkload[];
  orgId: string;
}

interface GroupState {
  userId: string;
  pinBrand: boolean;
}

export function QuoteBrandCard({ data, users, orgId }: Props) {
  const { quote, brandGroups } = data;
  const router = useRouter();
  const [groupStates, setGroupStates] = useState<Record<string, GroupState>>(
    {}
  );
  const [assigningKey, setAssigningKey] = useState<string | null>(null);

  function getKey(bg: BrandGroup): string {
    return bg.brand ?? "__null__";
  }

  function getState(bg: BrandGroup): GroupState {
    return groupStates[getKey(bg)] ?? { userId: "", pinBrand: false };
  }

  function updateState(bg: BrandGroup, partial: Partial<GroupState>) {
    const key = getKey(bg);
    setGroupStates((prev) => ({
      ...prev,
      [key]: { ...getState(bg), ...partial },
    }));
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
    });
  }

  async function handleAssign(bg: BrandGroup) {
    const state = getState(bg);
    if (!state.userId) return;

    const key = getKey(bg);
    setAssigningKey(key);

    const result = await assignBrandGroup(
      bg.itemIds,
      state.userId,
      state.pinBrand,
      orgId,
      bg.brand
    );

    if (result.success) {
      const userName =
        users.find((u) => u.user_id === state.userId)?.full_name ?? "закупщика";
      toast.success(
        `${bg.itemCount} поз. назначено на ${userName}`
      );
      router.refresh();
    } else {
      toast.error(result.error ?? "Ошибка назначения");
    }

    setAssigningKey(null);
  }

  return (
    <div className="rounded-lg border border-border-light bg-surface">
      {/* Quote header */}
      <div className="px-4 py-3 border-b border-border-light bg-background rounded-t-lg">
        <div className="flex items-center gap-3 text-sm">
          <Link
            href={`/quotes/${quote.id}`}
            className="font-semibold text-text hover:text-accent hover:underline"
          >
            {quote.idn}
          </Link>
          <span className="text-text-muted">{quote.customer_name ?? "—"}</span>
          <span className="text-text-subtle">{quote.sales_manager_name}</span>
          <span className="text-text-subtle ml-auto">
            {formatDate(quote.created_at)}
          </span>
        </div>
      </div>

      {/* Brand groups */}
      <div className="divide-y divide-border-light">
        {brandGroups.map((bg) => {
          const key = getKey(bg);
          const state = getState(bg);
          const isAssigning = assigningKey === key;

          return (
            <div
              key={key}
              className="px-4 py-3 flex items-center gap-4 flex-wrap"
            >
              {/* Brand + count */}
              <div className="min-w-[140px]">
                <span className="font-medium text-text">
                  {bg.brand ?? "Без бренда"}
                </span>
                <span className="text-text-muted text-sm ml-2">
                  ({bg.itemCount} поз.)
                </span>
              </div>

              {/* User select with search */}
              <div className="w-[200px]">
                <UserSearchSelect
                  users={users}
                  value={state.userId}
                  onValueChange={(val) =>
                    updateState(bg, { userId: val })
                  }
                  disabled={isAssigning}
                />
              </div>

              {/* Pin brand checkbox */}
              {bg.brand && (
                <label className="flex items-center gap-1.5 text-xs cursor-pointer whitespace-nowrap">
                  <Checkbox
                    checked={state.pinBrand}
                    onCheckedChange={(checked) =>
                      updateState(bg, { pinBrand: checked === true })
                    }
                    disabled={isAssigning}
                    className="size-3.5"
                  />
                  <Pin size={12} className="text-text-muted" />
                  <span className="text-text-muted">Закрепить</span>
                  <span className="text-text-subtle text-[10px]" title="Все будущие заявки с этим брендом автоматически пойдут к выбранному закупщику">
                    ?
                  </span>
                </label>
              )}

              {/* Assign button */}
              <Button
                size="sm"
                onClick={() => handleAssign(bg)}
                disabled={!state.userId || isAssigning}
                className="bg-accent text-white hover:bg-accent-hover"
              >
                {isAssigning ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : null}
                Назначить
              </Button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
