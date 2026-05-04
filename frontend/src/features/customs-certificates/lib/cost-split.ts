/**
 * Feature-local re-export of the shared cost-split helpers (REQ-3).
 *
 * Single import point for UI sub-tasks (Wave 3 7a-7f) — keeps the namespace
 * predictable inside the feature and lets us swap out the implementation
 * later without touching every caller.
 *
 * The actual implementation lives in `@/shared/lib/cost-split` (Wave 1
 * Task 3) and is parity-tested against the Python sister
 * (`services/cost_split.py`) via `tests/fixtures/cost_split_fixtures.json`.
 *
 * NOT a wrapper — pure re-export per design.md §4.8 ("это не дубликат, а
 * namespace"). Any drift would break the kopek-exact parity contract.
 */
export {
  roundHalfUp2,
  splitCost,
  splitCostBatch,
} from "@/shared/lib/cost-split";
