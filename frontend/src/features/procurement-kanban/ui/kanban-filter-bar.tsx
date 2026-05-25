"use client";

import { useMemo } from "react";

import {
  FilterBar,
  MultiSelectFilter,
  SearchInputFilter,
  SingleSelectFilter,
  STAGE_AGE_OPTIONS,
  useFilterState,
  type StageAgeBucket,
} from "@/shared/ui/filter-bar";
import type { ProcurementUserWorkload } from "@/shared/types/procurement-user";

import {
  hasActiveProcurementFilters,
  type ProcurementFilterState,
} from "../lib/filter-board";
import type { KanbanBrandCard, KanbanColumns } from "../model/types";

const FILTER_KEYS = {
  customer: "customer",
  brand: "brand",
  manager: "manager",
  procurement: "procurement",
  stageAge: "stage_age",
  idnSearch: "q",
} as const;

export const PROCUREMENT_FILTER_KEYS: ReadonlyArray<string> =
  Object.values(FILTER_KEYS);

function readList(params: URLSearchParams, key: string): string[] {
  const raw = params.get(key);
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

function readScalar(params: URLSearchParams, key: string): string | null {
  const raw = params.get(key);
  return raw && raw.length > 0 ? raw : null;
}

export function readProcurementFiltersFromParams(
  params: URLSearchParams
): ProcurementFilterState {
  const stage = readScalar(params, FILTER_KEYS.stageAge);
  const stageValid =
    stage && STAGE_AGE_OPTIONS.some((o) => o.value === stage)
      ? (stage as StageAgeBucket)
      : null;
  return {
    customerIds: readList(params, FILTER_KEYS.customer),
    brands: readList(params, FILTER_KEYS.brand),
    managerIds: readList(params, FILTER_KEYS.manager),
    procurementUserIds: readList(params, FILTER_KEYS.procurement),
    stageAge: stageValid,
    idnSearch: readScalar(params, FILTER_KEYS.idnSearch),
  };
}

export interface KanbanFilterBarProps {
  /** Full unfiltered columns — drives the picker option lists. */
  fullColumns: KanbanColumns;
  /**
   * Procurement team workload — used to populate the МОЗ picker so the head
   * sees ALL team members, not just those who already own cards on the board.
   * Members (МОЗ) don't need this — the picker is hidden for them.
   */
  workload?: ProcurementUserWorkload[];
  /**
   * Show МОЗ (Исполнитель) picker? Hidden for regular МОЗ users since they
   * only see their own cards.
   */
  showProcurementUserFilter: boolean;
}

/**
 * Filter bar for the procurement kanban (Testing 2 row 66).
 *
 * Filters: Клиент, Бренд, МОП, МОЗ (head-only), На этапе > N дней.
 * State is URL-backed via `useFilterState` so back/forward and deep links
 * survive page reloads.
 */
export function KanbanFilterBar({
  fullColumns,
  workload,
  showProcurementUserFilter,
}: KanbanFilterBarProps) {
  const { params, setMulti, setSingle, setMany } = useFilterState();

  const allCards = useMemo<KanbanBrandCard[]>(() => {
    return [
      ...fullColumns.distributing,
      ...fullColumns.searching_supplier,
      ...fullColumns.waiting_prices,
      ...fullColumns.prices_ready,
    ];
  }, [fullColumns]);

  const customerOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of allCards) {
      if (c.customer_id && !seen.has(c.customer_id)) {
        seen.set(c.customer_id, c.customer_name || "—");
      }
    }
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [allCards]);

  const brandOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of allCards) {
      const value = c.brand;
      if (!seen.has(value)) {
        seen.set(value, value === "" ? "Без бренда" : value);
      }
    }
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [allCards]);

  const managerOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of allCards) {
      if (c.manager_id && !seen.has(c.manager_id)) {
        seen.set(c.manager_id, c.manager_name || "—");
      }
    }
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [allCards]);

  const procurementUserOptions = useMemo(() => {
    if (!showProcurementUserFilter) return [];
    const seen = new Map<string, string>();
    // Source 1: full team roster (head wants ALL МОЗ in the picker, even
    // those with no current cards).
    for (const w of workload ?? []) {
      seen.set(w.user_id, w.full_name || "—");
    }
    // Source 2: any МОЗ actually present on the board — covers users who
    // have left the team / org but still own active cards.
    for (const c of allCards) {
      const ids = c.procurement_user_ids ?? [];
      const names = c.procurement_user_names ?? [];
      for (let i = 0; i < ids.length; i++) {
        if (!seen.has(ids[i])) seen.set(ids[i], names[i] || "—");
      }
    }
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [showProcurementUserFilter, workload, allCards]);

  const current = useMemo<ProcurementFilterState>(
    () => readProcurementFiltersFromParams(new URLSearchParams(params.toString())),
    [params]
  );
  const isActive = hasActiveProcurementFilters(current);

  function clearAll() {
    setMany(Object.fromEntries(PROCUREMENT_FILTER_KEYS.map((k) => [k, null])));
  }

  return (
    <FilterBar hasActiveFilters={isActive} onClearAll={clearAll}>
      <SearchInputFilter
        value={current.idnSearch}
        onChange={(next) => setSingle(FILTER_KEYS.idnSearch, next)}
        placeholder="Поиск по IDN КП…"
        ariaLabel="Поиск по IDN КП"
      />
      <MultiSelectFilter
        label="Клиент"
        options={customerOptions}
        selected={current.customerIds}
        onChange={(values) => setMulti(FILTER_KEYS.customer, values)}
        emptyMessage="Нет клиентов в выборке"
        searchPlaceholder="Поиск клиента..."
      />
      <MultiSelectFilter
        label="Бренд"
        options={brandOptions}
        selected={current.brands}
        onChange={(values) => setMulti(FILTER_KEYS.brand, values)}
        emptyMessage="Нет брендов"
        searchPlaceholder="Поиск бренда..."
      />
      <MultiSelectFilter
        label="МОП"
        options={managerOptions}
        selected={current.managerIds}
        onChange={(values) => setMulti(FILTER_KEYS.manager, values)}
        emptyMessage="Нет менеджеров"
        searchPlaceholder="Поиск МОП..."
      />
      {showProcurementUserFilter && (
        <MultiSelectFilter
          label="МОЗ"
          options={procurementUserOptions}
          selected={current.procurementUserIds}
          onChange={(values) => setMulti(FILTER_KEYS.procurement, values)}
          emptyMessage="Нет исполнителей"
          searchPlaceholder="Поиск МОЗ..."
        />
      )}
      <SingleSelectFilter
        label="На этапе > N дней"
        options={STAGE_AGE_OPTIONS as ReadonlyArray<{ value: string; label: string }>}
        value={current.stageAge}
        onChange={(value) => setSingle(FILTER_KEYS.stageAge, value)}
      />
    </FilterBar>
  );
}

export function useProcurementFiltersFromUrl(): ProcurementFilterState {
  const { params } = useFilterState();
  return useMemo<ProcurementFilterState>(
    () => readProcurementFiltersFromParams(new URLSearchParams(params.toString())),
    [params]
  );
}
