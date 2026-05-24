/**
 * Filter-bar primitives (Testing 2 rows 64-66).
 *
 * Composable URL-backed filter triggers used above the logistics, customs, and
 * procurement kanban boards. Sub-components are page-agnostic and free of any
 * business logic — page-level wiring (which filters to expose, which fields to
 * filter on) lives in the consuming feature/widget layer.
 */

export { FilterBar } from "./filter-bar";
export type { FilterBarProps } from "./filter-bar";

export { MultiSelectFilter } from "./multi-select-filter";
export type {
  MultiSelectFilterProps,
  MultiSelectOption,
} from "./multi-select-filter";

export { SingleSelectFilter } from "./single-select-filter";
export type {
  SingleSelectFilterProps,
  SingleSelectOption,
} from "./single-select-filter";

export { DateRangeFilter } from "./date-range-filter";
export type { DateRangeFilterProps } from "./date-range-filter";

export { FilterEmptyState } from "./filter-empty-state";
export type { FilterEmptyStateProps } from "./filter-empty-state";

export {
  useFilterState,
  parseMulti,
  serializeMulti,
} from "./use-filter-state";
export type { FilterStateApi } from "./use-filter-state";

export {
  URGENCY_OPTIONS,
  URGENCY_LABELS,
  isInUrgencyBucket,
} from "./urgency";
export type { UrgencyBucket } from "./urgency";

export {
  STAGE_AGE_OPTIONS,
  STAGE_AGE_LABELS,
  isInStageAgeBucket,
} from "./stage-age";
export type { StageAgeBucket } from "./stage-age";
