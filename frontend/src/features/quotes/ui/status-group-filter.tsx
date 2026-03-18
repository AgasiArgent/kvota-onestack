"use client";

import { useState } from "react";
import Link from "next/link";
import { STATUS_GROUPS, getStatusesForGroup } from "@/entities/quote/types";
import type { StatusGroup } from "@/entities/quote/types";

interface StatusGroupFilterProps {
  activeGroup: string | null;
  activeStatus: string | null;
}

export function StatusGroupFilter({
  activeGroup,
  activeStatus,
}: StatusGroupFilterProps) {
  const [expandedGroup, setExpandedGroup] = useState<string | null>(
    activeStatus ? activeGroup : null
  );

  function handleGroupClick(group: StatusGroup) {
    if (group.key === activeGroup && !activeStatus) {
      // Clicking active group deselects it — let the form submit with no status
      return;
    }
    if (group.key === activeGroup) {
      // Clicking active group when a sub-status is selected — collapse to group level
      setExpandedGroup(null);
    }
  }

  function toggleExpansion(
    e: React.MouseEvent,
    groupKey: string
  ) {
    e.preventDefault();
    e.stopPropagation();
    setExpandedGroup(expandedGroup === groupKey ? null : groupKey);
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {STATUS_GROUPS.map((group) => {
          const isActive = group.key === activeGroup;
          return (
            <button
              key={group.key}
              type="submit"
              name="status"
              value={isActive && !activeStatus ? "" : group.key}
              onClick={() => handleGroupClick(group)}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                group.color
              } ${
                isActive
                  ? "ring-2 ring-offset-1 ring-current"
                  : "opacity-80 hover:opacity-100"
              }`}
            >
              {group.label}
              <span className="text-xs opacity-70">
                {group.statuses.length}
              </span>
              {isActive && group.statuses.length > 1 && (
                <button
                  type="button"
                  onClick={(e) => toggleExpansion(e, group.key)}
                  className="ml-0.5 text-xs"
                >
                  {expandedGroup === group.key ? "\u25B4" : "\u25BE"}
                </button>
              )}
            </button>
          );
        })}
        {(activeGroup || activeStatus) && (
          <Link
            href="/quotes"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Сбросить
          </Link>
        )}
      </div>

      {/* Expanded individual statuses */}
      {expandedGroup && activeGroup === expandedGroup && (
        <div className="flex flex-wrap gap-1.5 pl-2">
          {getStatusesForGroup(expandedGroup).map((status) => {
            const isActiveStatus = activeStatus === status;
            const parentGroup = STATUS_GROUPS.find(
              (g) => g.key === expandedGroup
            );
            return (
              <button
                key={status}
                type="submit"
                name="status"
                value={isActiveStatus ? expandedGroup : status}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors ${
                  parentGroup?.color ?? "bg-slate-100 text-slate-700"
                } ${
                  isActiveStatus
                    ? "ring-1 ring-offset-1 ring-current"
                    : "opacity-60 hover:opacity-100"
                }`}
              >
                {formatStatusLabel(status)}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "Закупки",
  logistics: "Логистика",
  pending_customs: "Таможня",
  pending_quote_control: "Контроль КП",
  pending_spec_control: "Контроль спец.",
  pending_sales_review: "Ревью продаж",
  pending_approval: "На утверждении",
  approved: "Одобрено",
  sent_to_client: "Отправлено клиенту",
  deal: "Сделка",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

function formatStatusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
