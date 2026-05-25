/**
 * Pure filter helpers for the procurement kanban board (Testing 2 row 66).
 *
 * Pulled out of the React component so the matching logic is unit-testable
 * without a DOM environment.
 */

import {
  isInStageAgeBucket,
  type StageAgeBucket,
} from "@/shared/ui/filter-bar";
import { PROCUREMENT_SUBSTATUSES } from "@/shared/lib/workflow-substates";

import type { KanbanBrandCard, KanbanColumns } from "../model/types";

export interface ProcurementFilterState {
  /** Selected customer ids — empty means «all clients». */
  customerIds: readonly string[];
  /** Selected brand labels — empty means «all brands». Includes "" for «Без бренда». */
  brands: readonly string[];
  /** Selected МОП (creator) user-ids — empty means «all МОП». */
  managerIds: readonly string[];
  /** Selected МОЗ (procurement user) ids — empty means «all МОЗ». */
  procurementUserIds: readonly string[];
  /** «На этапе > N дней» bucket. */
  stageAge: StageAgeBucket | null;
  /** «Поиск по IDN КП» — substring match against `idn_quote`. Null when unset. */
  idnSearch: string | null;
}

export function emptyProcurementFilters(): ProcurementFilterState {
  return {
    customerIds: [],
    brands: [],
    managerIds: [],
    procurementUserIds: [],
    stageAge: null,
    idnSearch: null,
  };
}

export function hasActiveProcurementFilters(
  filters: ProcurementFilterState
): boolean {
  return (
    filters.customerIds.length > 0 ||
    filters.brands.length > 0 ||
    filters.managerIds.length > 0 ||
    filters.procurementUserIds.length > 0 ||
    filters.stageAge !== null ||
    (filters.idnSearch !== null && filters.idnSearch.trim().length > 0)
  );
}

export function cardPassesProcurementFilters(
  card: KanbanBrandCard,
  filters: ProcurementFilterState
): boolean {
  // Customer
  if (filters.customerIds.length > 0) {
    if (!card.customer_id || !filters.customerIds.includes(card.customer_id))
      return false;
  }

  // Brand — empty string "" represents «Без бренда»; allow filtering for it.
  if (filters.brands.length > 0) {
    if (!filters.brands.includes(card.brand)) return false;
  }

  // МОП (creator)
  if (filters.managerIds.length > 0) {
    if (!card.manager_id || !filters.managerIds.includes(card.manager_id))
      return false;
  }

  // МОЗ — card carries any number of procurement users; pass when at least
  // one matches a picked id.
  if (filters.procurementUserIds.length > 0) {
    const cardIds = card.procurement_user_ids ?? [];
    if (cardIds.length === 0) return false;
    const hit = cardIds.some((id) => filters.procurementUserIds.includes(id));
    if (!hit) return false;
  }

  // Stage age (days_in_state)
  if (filters.stageAge) {
    if (!isInStageAgeBucket(card.days_in_state, filters.stageAge)) return false;
  }

  // IDN substring search (Testing 2 row 66). Case-insensitive against
  // `idn_quote` ("Q-202604-0001"). Whitespace-only filters are no-ops; the
  // caller is expected to send `null` for empty queries but we defend in
  // depth.
  if (filters.idnSearch && filters.idnSearch.trim().length > 0) {
    const needle = filters.idnSearch.trim().toLowerCase();
    const haystack = (card.idn_quote ?? "").toLowerCase();
    if (!haystack.includes(needle)) return false;
  }

  return true;
}

export function filterProcurementColumns(
  columns: KanbanColumns,
  filters: ProcurementFilterState
): KanbanColumns {
  return Object.fromEntries(
    PROCUREMENT_SUBSTATUSES.map((sub) => [
      sub,
      columns[sub].filter((c) => cardPassesProcurementFilters(c, filters)),
    ])
  ) as KanbanColumns;
}

export function totalProcurementCardCount(columns: KanbanColumns): number {
  return PROCUREMENT_SUBSTATUSES.reduce(
    (acc, sub) => acc + columns[sub].length,
    0
  );
}
