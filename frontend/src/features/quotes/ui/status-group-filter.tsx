"use client";

import { useState } from "react";
import Link from "next/link";
import { STATUS_GROUPS, getStatusesForGroup } from "@/entities/quote/types";
import type { StatusGroup } from "@/entities/quote/types";

interface StatusGroupFilterProps {
  activeGroup: string | null;
  activeStatus: string | null;
  onFilterChange: (status: string | null) => void;
}

export function StatusGroupFilter({
  activeGroup,
  activeStatus,
  onFilterChange,
}: StatusGroupFilterProps) {
  const [expandedGroup, setExpandedGroup] = useState<string | null>(
    activeStatus ? activeGroup : null
  );

  function handleGroupClick(group: StatusGroup) {
    if (group.key === activeGroup && !activeStatus) {
      // Clicking active group deselects it
      onFilterChange(null);
      return;
    }
    // Select this group
    onFilterChange(group.key);
    setExpandedGroup(null);
  }

  function handleStatusClick(status: string) {
    if (status === activeStatus) {
      // Clicking active sub-status goes back to group level
      onFilterChange(activeGroup);
    } else {
      onFilterChange(status);
    }
  }

  function toggleExpansion(e: React.MouseEvent, groupKey: string) {
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
              type="button"
              onClick={() => handleGroupClick(group)}
              title={group.statuses.map((s) => formatStatusLabel(s)).join(", ")}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium transition-colors cursor-pointer ${
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
                  {expandedGroup === group.key ? "▴" : "▾"}
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
                type="button"
                onClick={() => handleStatusClick(status)}
                className={`rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer ${
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
  procurement_complete: "Закупка завершена",
  pending_logistics: "Логистика",
  logistics: "Логистика",
  pending_customs: "Таможня",
  pending_logistics_and_customs: "Логистика и таможня",
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
