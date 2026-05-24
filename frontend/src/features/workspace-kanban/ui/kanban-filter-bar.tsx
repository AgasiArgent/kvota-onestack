"use client";

import { useMemo } from "react";

import {
  DateRangeFilter,
  FilterBar,
  MultiSelectFilter,
  SingleSelectFilter,
  URGENCY_OPTIONS,
  useFilterState,
  type UrgencyBucket,
} from "@/shared/ui/filter-bar";
import type { UserAvatarChipUser } from "@/entities/user/ui/user-avatar-chip";
import type {
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
} from "@/entities/workspace-invoice";

import {
  hasActiveWorkspaceFilters,
  type WorkspaceFilterState,
} from "../lib/filter-board";

const FILTER_KEYS = {
  customer: "customer",
  assignee: "assignee",
  stageFrom: "stage_from",
  stageTo: "stage_to",
  urgency: "urgency",
} as const;

/** Keys this filter bar manages — used by the «Сбросить все» wipe. */
export const WORKSPACE_FILTER_KEYS: ReadonlyArray<string> = Object.values(
  FILTER_KEYS
);

/**
 * Read the current filter state from URL params. Server pages can call this
 * with `searchParams` (cast through Record) too, but the kanban renders
 * client-side so the hook-based reader below is the canonical path.
 */
export function readFiltersFromParams(
  params: URLSearchParams | Record<string, string | string[] | undefined>
): WorkspaceFilterState {
  function readList(key: string): string[] {
    const raw =
      params instanceof URLSearchParams
        ? params.get(key)
        : Array.isArray(params[key])
          ? (params[key] as string[]).join(",")
          : (params[key] as string | undefined) ?? null;
    if (!raw) return [];
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
  }
  function readScalar(key: string): string | null {
    const raw =
      params instanceof URLSearchParams
        ? params.get(key)
        : Array.isArray(params[key])
          ? (params[key] as string[])[0]
          : (params[key] as string | undefined) ?? null;
    return raw && raw.length > 0 ? raw : null;
  }
  const urgency = readScalar(FILTER_KEYS.urgency);
  const urgencyValid =
    urgency &&
    URGENCY_OPTIONS.some((o) => o.value === urgency)
      ? (urgency as UrgencyBucket)
      : null;
  return {
    customerIds: readList(FILTER_KEYS.customer),
    assigneeIds: readList(FILTER_KEYS.assignee),
    stageFrom: readScalar(FILTER_KEYS.stageFrom),
    stageTo: readScalar(FILTER_KEYS.stageTo),
    urgency: urgencyValid,
  };
}

export interface KanbanFilterBarProps {
  /**
   * Full unfiltered board — used to derive distinct customer / assignee
   * option lists. The page passes the same board it feeds the kanban.
   */
  fullBoard: WorkspaceKanbanBoard;
  /**
   * Show the assignee filter? True only for head views per the product
   * decision (Testing 2 rows 64-65: «Исполнитель» visible to head only).
   */
  showAssigneeFilter: boolean;
  /**
   * Team roster — drives the assignee filter options. Empty for members
   * (assignee filter is also hidden via `showAssigneeFilter=false` in that
   * case, so this list is only consumed in head view).
   */
  teamUsers: UserAvatarChipUser[];
}

/**
 * Top-level filter bar shown above the logistics / customs kanban board.
 *
 * Filter state is URL-backed via `useFilterState` so links and back/forward
 * navigation preserve the picks. The kanban itself reads the same params and
 * re-renders its filtered view via `useWorkspaceFilters`.
 */
export function KanbanFilterBar({
  fullBoard,
  showAssigneeFilter,
  teamUsers,
}: KanbanFilterBarProps) {
  const filters = useFilterState();

  const customerOptions = useMemo(() => {
    const seen = new Map<string, string>();
    function collect(cards: readonly WorkspaceKanbanCard[]) {
      for (const c of cards) {
        if (c.customerId && !seen.has(c.customerId)) {
          seen.set(c.customerId, c.customerName || "—");
        }
      }
    }
    collect(fullBoard.unassigned);
    collect(fullBoard.in_progress);
    collect(fullBoard.completed);
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [fullBoard]);

  const assigneeOptions = useMemo(() => {
    if (!showAssigneeFilter) return [];
    // Source 1: team roster (head's picker uses the same set).
    const merged = new Map<string, string>();
    for (const u of teamUsers) merged.set(u.id, u.name);
    // Source 2: any assignee actually present on the board — covers users
    // who left the team but still own active cards (МВЭД-26 scenario).
    function collect(cards: readonly WorkspaceKanbanCard[]) {
      for (const c of cards) {
        if (
          c.assignedUserId &&
          c.assignedUser &&
          !merged.has(c.assignedUserId)
        ) {
          merged.set(c.assignedUserId, c.assignedUser.name || "—");
        }
      }
    }
    collect(fullBoard.unassigned);
    collect(fullBoard.in_progress);
    collect(fullBoard.completed);
    return Array.from(merged.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [showAssigneeFilter, teamUsers, fullBoard]);

  const current = useMemo<WorkspaceFilterState>(
    () => readFiltersFromParams(new URLSearchParams(filters.params.toString())),
    [filters.params]
  );

  const isActive = hasActiveWorkspaceFilters(current);

  function clearAll() {
    // Preserve any non-filter URL keys (e.g., a future `?tab=...`).
    const next = new URLSearchParams(filters.params.toString());
    for (const key of WORKSPACE_FILTER_KEYS) next.delete(key);
    // Use the hook's setMany to keep behavior consistent with chip updates.
    filters.setMany(
      Object.fromEntries(WORKSPACE_FILTER_KEYS.map((k) => [k, null]))
    );
  }

  return (
    <FilterBar hasActiveFilters={isActive} onClearAll={clearAll}>
      <MultiSelectFilter
        label="Клиент"
        options={customerOptions}
        selected={current.customerIds}
        onChange={(values) => filters.setMulti(FILTER_KEYS.customer, values)}
        emptyMessage="Нет клиентов в выборке"
        searchPlaceholder="Поиск клиента..."
      />
      {showAssigneeFilter && (
        <MultiSelectFilter
          label="Исполнитель"
          options={assigneeOptions}
          selected={current.assigneeIds}
          onChange={(values) => filters.setMulti(FILTER_KEYS.assignee, values)}
          emptyMessage="Нет исполнителей"
          searchPlaceholder="Поиск исполнителя..."
        />
      )}
      <DateRangeFilter
        label="Дата входа в этап"
        from={current.stageFrom}
        to={current.stageTo}
        onChange={(from, to) =>
          filters.setMany({
            [FILTER_KEYS.stageFrom]: from,
            [FILTER_KEYS.stageTo]: to,
          })
        }
      />
      <SingleSelectFilter
        label="Срочность"
        options={URGENCY_OPTIONS as ReadonlyArray<{ value: string; label: string }>}
        value={current.urgency}
        onChange={(value) => filters.setSingle(FILTER_KEYS.urgency, value)}
      />
    </FilterBar>
  );
}

/**
 * Hook used by the consuming KanbanPage to read filters from URL and produce
 * a derived view of the board. Memoizes both reads so re-rendering on
 * unrelated state changes doesn't re-filter the board.
 */
export function useWorkspaceFiltersFromUrl(): WorkspaceFilterState {
  const { params } = useFilterState();
  return useMemo<WorkspaceFilterState>(
    () => readFiltersFromParams(new URLSearchParams(params.toString())),
    [params]
  );
}
