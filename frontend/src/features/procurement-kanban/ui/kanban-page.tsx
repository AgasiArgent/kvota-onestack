"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

import { AppToaster } from "@/shared/ui/app-toaster";
import { FilterEmptyState, useFilterState } from "@/shared/ui/filter-bar";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";

import {
  filterProcurementColumns,
  hasActiveProcurementFilters,
  totalProcurementCardCount,
} from "../lib/filter-board";
import {
  KanbanFilterBar,
  PROCUREMENT_FILTER_KEYS,
  useProcurementFiltersFromUrl,
} from "./kanban-filter-bar";
import type { KanbanResponse } from "../model/types";

// Board is interactive only (dnd-kit). Rendering it on the server produces
// hydration mismatches (React error #418) because @dnd-kit/core injects
// attributes (aria-describedby, data-*) whose generated values differ between
// server and client. There's no SEO value in pre-rendering a drag-and-drop
// surface, so skip SSR entirely — the enclosing page.tsx still fetches data
// on the server and passes it down as a prop.
const KanbanBoard = dynamic(
  () => import("./kanban-board").then((m) => ({ default: m.KanbanBoard })),
  {
    ssr: false,
    loading: () => (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="min-h-[300px] rounded-lg border bg-muted/40 p-3"
          />
        ))}
      </div>
    ),
  }
);

export interface KanbanPageProps {
  data: KanbanResponse;
  workload: ProcurementUserWorkload[];
  orgId: string;
  /**
   * When false, the «Распределение» column is hidden (МОЗ-45). Only roles
   * with actual distribution authority — admin, head_of_procurement,
   * procurement_senior — should see that column.
   */
  canDistribute: boolean;
  /**
   * Testing 2 row 75 v2 — whether the user is allowed to reroute an
   * already-distributed brand-slice via the «Переназначить» button on the
   * card. Decoupled from `canDistribute` so regular МОЗ (which cannot
   * distribute, see МОЗ-45) can still reassign their own slices.
   */
  canReassign: boolean;
}

/**
 * Top-level kanban screen. Server component fetches state once; subsequent
 * board mutations happen client-side with optimistic updates.
 *
 * Filters (Testing 2 row 66) live in the URL via `useFilterState`. The МОЗ
 * picker reuses `canDistribute` as the head-vs-member discriminator: only
 * admin / head_of_procurement / procurement_senior can distribute, and only
 * those roles need to slice the board by other people's assignments.
 */
export function KanbanPage({
  data,
  workload,
  orgId,
  canDistribute,
  canReassign,
}: KanbanPageProps) {
  const filters = useProcurementFiltersFromUrl();
  const { setMany } = useFilterState();

  const filteredColumns = useMemo(
    () => filterProcurementColumns(data.columns, filters),
    [data.columns, filters]
  );

  const totalCards = totalProcurementCardCount(filteredColumns);
  const filtersActive = hasActiveProcurementFilters(filters);
  const showEmptyState =
    filtersActive &&
    totalCards === 0 &&
    totalProcurementCardCount(data.columns) > 0;

  function handleClearAll() {
    setMany(Object.fromEntries(PROCUREMENT_FILTER_KEYS.map((k) => [k, null])));
  }

  return (
    <>
      <div className="space-y-6">
        <header>
          <h1 className="text-xl font-semibold text-foreground">
            Канбан закупок
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {totalCards === 0
              ? "Нет карточек в работе"
              : `${totalCards} ${pluralizeCards(totalCards)} в работе`}
          </p>
        </header>

        <KanbanFilterBar
          fullColumns={data.columns}
          workload={workload}
          showProcurementUserFilter={canDistribute}
        />

        {showEmptyState ? (
          <FilterEmptyState onClearAll={handleClearAll} />
        ) : (
          <KanbanBoard
            initialColumns={filteredColumns}
            workload={workload}
            orgId={orgId}
            canDistribute={canDistribute}
            canReassign={canReassign}
          />
        )}
      </div>
      <AppToaster />
    </>
  );
}

function pluralizeCards(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "карточка";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20))
    return "карточки";
  return "карточек";
}
