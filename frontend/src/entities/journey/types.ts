/**
 * Customer Journey Map — shared TypeScript type contracts.
 *
 * Authoritative type module for the `journey` feature. Every downstream slice
 * (`features/journey`, `widgets/journey`, `app/(app)/journey`, parsers under
 * `frontend/scripts/journey/`, API clients) imports from here.
 *
 * Source of truth: `.kiro/specs/customer-journey-map/design.md` §4.1 (Manifest
 * Types) and §4.2 (Annotation Types).
 *
 * Organisation:
 *   1. Literal-union status types (`ImplStatus`, `QaStatus`, `GhostStatus`,
 *      `PinMode`, `VerifyResult`) — used by DB CHECK constraints and the UI.
 *   2. `RoleSlug` — the 13 active role slugs per `.kiro/steering/access-control.md`
 *      (post-migration 168 cleanup — `sales_manager`/`currency_controller` removed).
 *   3. `JourneyNodeId` — template-literal type enforcing `app:` / `ghost:` prefix.
 *   4. Manifest interfaces (`JourneyNode`, `JourneyEdge`, `JourneyCluster`,
 *      `JourneyStory`, `JourneyManifest`) — generated at build time into
 *      `frontend/public/journey-manifest.json`.
 *   5. Annotation interfaces — one per mutable DB table from the Task 1 migration
 *      (`journey_node_state`, `journey_node_state_history`, `journey_ghost_nodes`,
 *      `journey_pins`, `journey_verifications`, `journey_flows`).
 *   6. Supabase-generated row-type re-exports. These are stubbed until Task 1
 *      lands and `database.types.ts` is regenerated — see TODO markers.
 *
 * Immutability: every field is `readonly`. Manifest and annotation payloads
 * flow through TanStack Query caches and React state; treating them as
 * immutable prevents accidental mutation of cached objects.
 */

// ---------------------------------------------------------------------------
// 1. Literal-union status types
// ---------------------------------------------------------------------------

/** Implementation status of a node (route). Mirrors DB CHECK on `journey_node_state.impl_status`. */
export type ImplStatus = "done" | "partial" | "missing";

/** QA status of a node. Mirrors DB CHECK on `journey_node_state.qa_status`. */
export type QaStatus = "verified" | "broken" | "untested";

/** Lifecycle status of a ghost (planned-but-unshipped) node. */
export type GhostStatus = "proposed" | "approved" | "in_progress" | "shipped";

/** Pin mode — QA assertion vs training-onboarding step. */
export type PinMode = "qa" | "training";

/** Outcome recorded on a single verification run against a pin. */
export type VerifyResult = "verified" | "broken" | "skip";

// ---------------------------------------------------------------------------
// 2. Role slugs
// ---------------------------------------------------------------------------

/**
 * The 13 active role slugs per `.kiro/steering/access-control.md` and
 * migration 168 (2026-02-11 cleanup, 86 → 12 active roles; `admin` counted
 * separately). Legacy slugs (`sales_manager`, `currency_controller`) are
 * intentionally excluded — they were removed in that migration.
 */
export type RoleSlug =
  | "admin"
  | "top_manager"
  | "head_of_sales"
  | "head_of_procurement"
  | "head_of_logistics"
  | "sales"
  | "quote_controller"
  | "spec_controller"
  | "finance"
  | "procurement"
  | "procurement_senior"
  | "logistics"
  | "customs";

// ---------------------------------------------------------------------------
// 3. Node identifier
// ---------------------------------------------------------------------------

/**
 * Stable identifier for every node on the canvas.
 * - `app:<route>` — a node generated from a Next.js route in `frontend/src/app/**`.
 * - `ghost:<slug>` — a planned-but-unshipped node tracked in `journey_ghost_nodes`.
 *
 * Template-literal union disallows bare strings at compile time — the parser
 * and API layers must always emit one of these two prefixes.
 */
export type JourneyNodeId = `app:${string}` | `ghost:${string}`;

// ---------------------------------------------------------------------------
// 4. Manifest types (read-only, build-time output)
// ---------------------------------------------------------------------------

/** One user story extracted from `.kiro/specs/**`, bound to a node. */
export interface JourneyStory {
  readonly ref: string; // e.g. 'phase-5b#3'
  readonly actor: RoleSlug | string; // typically a role; free-form allowed
  readonly goal: string;
  readonly spec_file: string;
}

/** One node on the canvas — either a real route or a ghost. */
export interface JourneyNode {
  readonly node_id: JourneyNodeId;
  readonly route: string; // Next.js path including brackets, e.g. '/quotes/[id]'
  readonly title: string;
  readonly cluster: string;
  readonly source_files: readonly string[];
  readonly roles: readonly RoleSlug[];
  readonly stories: readonly JourneyStory[];
  readonly parent_node_id: JourneyNodeId | null;
  readonly children: readonly JourneyNodeId[];
}

/** Directed edge between two nodes. */
export interface JourneyEdge {
  readonly from: JourneyNodeId;
  readonly to: JourneyNodeId;
  readonly kind: "drill" | "sibling" | "parallel";
}

/** Visual cluster grouping (e.g. "Quotes", "Procurement"). */
export interface JourneyCluster {
  readonly id: string;
  readonly label: string;
  readonly colour: string; // CSS color string
}

/** Top-level manifest — the deterministic build artifact. */
export interface JourneyManifest {
  readonly version: 1;
  readonly generated_at: string; // ISO 8601
  readonly commit: string; // git SHA
  readonly nodes: readonly JourneyNode[];
  readonly edges: readonly JourneyEdge[];
  readonly clusters: readonly JourneyCluster[];
}

// ---------------------------------------------------------------------------
// 5. Annotation types (DB-backed, mutable via Python API or Supabase)
// ---------------------------------------------------------------------------

/**
 * Current impl/qa status for a node.
 * The `version` column enables optimistic-concurrency control
 * (PATCH returns 409 STALE_VERSION when the client's version is stale).
 */
export interface JourneyNodeState {
  readonly node_id: JourneyNodeId;
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly notes: string | null;
  readonly version: number;
  readonly last_tested_at: string | null;
  readonly updated_at: string;
  readonly updated_by: string | null;
}

/**
 * Append-only history row, written by the `trg_journey_node_state_history`
 * trigger on every UPDATE of `journey_node_state`.
 */
export interface JourneyNodeStateHistory {
  readonly id: string;
  readonly node_id: JourneyNodeId;
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly notes: string | null;
  readonly version: number;
  readonly changed_by: string | null;
  readonly changed_at: string;
}

/**
 * Planned-but-unshipped node. Rendered on the canvas with dashed styling until
 * `status === 'shipped'`, at which point the real `app:<route>` supersedes it.
 */
export interface JourneyGhostNode {
  readonly id: string;
  readonly node_id: JourneyNodeId;
  readonly proposed_route: string | null;
  readonly title: string;
  readonly planned_in: string | null;
  readonly assignee: string | null;
  readonly parent_node_id: JourneyNodeId | null;
  readonly cluster: string | null;
  readonly status: GhostStatus;
  readonly created_by: string;
  readonly created_at: string;
}

/**
 * QA or training pin anchored to a DOM selector on a node's screenshot.
 *
 * Position is stored as a relative bbox (`last_rel_*` fields, fractions in
 * 0.0–1.0) so it survives viewport-size changes. All four may be `null` if
 * the nightly Playwright webhook has not yet resolved the selector.
 */
export interface JourneyPin {
  readonly id: string;
  readonly node_id: JourneyNodeId;
  readonly selector: string;
  readonly expected_behavior: string;
  readonly mode: PinMode;
  readonly training_step_order: number | null;
  readonly linked_story_ref: string | null;
  /** Relative bbox: fractions of screenshot viewport (0.0–1.0). */
  readonly last_rel_x: number | null;
  readonly last_rel_y: number | null;
  readonly last_rel_width: number | null;
  readonly last_rel_height: number | null;
  readonly last_position_update: string | null;
  readonly selector_broken: boolean;
  readonly created_by: string;
  readonly created_at: string;
}

/**
 * One verification event recorded against a pin. Append-only
 * (`journey_verifications` DELETE/UPDATE denied by RLS for everyone).
 */
export interface JourneyVerification {
  readonly id: string;
  readonly pin_id: string;
  readonly node_id: JourneyNodeId;
  readonly result: VerifyResult;
  readonly note: string | null;
  /**
   * Supabase Storage object keys (bucket `journey-verification-attachments`).
   * Up to 3 keys per row; resolved to signed URLs at render time.
   */
  readonly attachment_urls: readonly string[] | null;
  readonly tested_by: string;
  readonly tested_at: string;
}

/** One step within a curated flow. */
export interface JourneyFlowStep {
  readonly node_id: JourneyNodeId;
  readonly action: string;
  readonly note: string;
}

/**
 * Curated onboarding / QA / training flow — ordered traversal of nodes for a
 * specific persona. Steps are embedded as JSON on the `journey_flows` row.
 */
export interface JourneyFlow {
  readonly id: string;
  readonly slug: string;
  readonly title: string;
  readonly role: RoleSlug;
  readonly persona: string;
  readonly description: string;
  readonly est_minutes: number;
  readonly steps: readonly JourneyFlowStep[];
  readonly display_order: number;
  readonly is_archived: boolean;
}

// ---------------------------------------------------------------------------
// 6. Supabase-generated row-type re-exports
// ---------------------------------------------------------------------------
//
// TODO(task-1): After migration `NNN_journey_map.sql` lands and
// `cd frontend && npm run db:types` regenerates `database.types.ts`, replace
// the stubs below with real re-exports, e.g.:
//
//   import type { Database } from "@/shared/types/database.types";
//   export type JourneyNodeStateRow =
//     Database["kvota"]["Tables"]["journey_node_state"]["Row"];
//
// The current stubs alias the hand-written interfaces so downstream code that
// imports `JourneyNodeStateRow` keeps compiling. Once the real types land,
// the interfaces in section 5 should be derived from the Supabase row types
// (or deleted if the row types are sufficient on their own).
//
// Aliases intentionally point at the hand-written interfaces — not `unknown` —
// so strict-null-safe consumers get real field completions during the gap.

/** Row type for `kvota.journey_node_state`. TODO: regenerate after Task 1. */
export type JourneyNodeStateRow = JourneyNodeState;

/** Row type for `kvota.journey_node_state_history`. TODO: regenerate after Task 1. */
export type JourneyNodeStateHistoryRow = JourneyNodeStateHistory;

/** Row type for `kvota.journey_ghost_nodes`. TODO: regenerate after Task 1. */
export type JourneyGhostNodeRow = JourneyGhostNode;

/** Row type for `kvota.journey_pins`. TODO: regenerate after Task 1. */
export type JourneyPinRow = JourneyPin;

/** Row type for `kvota.journey_verifications`. TODO: regenerate after Task 1. */
export type JourneyVerificationRow = JourneyVerification;

/** Row type for `kvota.journey_flows`. TODO: regenerate after Task 1. */
export type JourneyFlowRow = JourneyFlow;

// ---------------------------------------------------------------------------
// 7. API response shapes — mirror `api/models/journey.py` Wave 4 DTOs
// ---------------------------------------------------------------------------
//
// These interfaces mirror the Pydantic models in `api/models/journey.py`
// (§4b–§4d). They are returned by the Python API under `/api/journey/*`
// wrapped in the standard `{success, data}` envelope (the entity slice
// unwraps the envelope before handing data to hooks).
//
// Fields are `readonly` everywhere; arrays and records are `readonly` so
// cached objects cannot be mutated by consumers.

/**
 * Canvas-level merged view of a node (manifest + state + counts).
 * Returned by `GET /api/journey/nodes` — one entry per node, with manifest
 * fields, current state, and scalar counts computed server-side.
 *
 * Mirrors `api/models/journey.py::JourneyNodeAggregated`.
 */
export interface JourneyNodeAggregated {
  readonly node_id: JourneyNodeId;
  readonly route: string;
  readonly title: string;
  readonly cluster: string;
  readonly roles: readonly RoleSlug[];
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly version: number;
  readonly stories_count: number;
  readonly feedback_count: number;
  readonly pins_count: number;
  readonly ghost_status: GhostStatus | null;
  readonly proposed_route: string | null;
  readonly updated_at: string | null;
}

/**
 * Compact feedback row for the drawer's top-3 list.
 * Mirrors `api/models/journey.py::JourneyFeedbackSummary`.
 */
export interface JourneyFeedbackSummary {
  readonly id: string;
  readonly short_id: string | null;
  readonly node_id: JourneyNodeId | null;
  readonly user_id: string | null;
  readonly description: string | null;
  readonly feedback_type: string | null;
  readonly status: string | null;
  readonly created_at: string | null;
}

/**
 * Full drawer payload for a single node.
 * Returned by `GET /api/journey/node/{node_id}` — composes manifest, state,
 * pins, latest-verification-per-pin map, and top-3 feedback rows.
 *
 * Mirrors `api/models/journey.py::JourneyNodeDetail`.
 */
export interface JourneyNodeDetail {
  readonly node_id: JourneyNodeId;
  readonly route: string;
  readonly title: string;
  readonly cluster: string;
  readonly roles: readonly RoleSlug[];
  readonly stories_count: number;
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly version: number;
  readonly notes: string | null;
  readonly updated_at: string | null;
  readonly ghost_status: GhostStatus | null;
  readonly proposed_route: string | null;
  readonly pins: readonly JourneyPin[];
  readonly verifications_by_pin: Readonly<Record<string, JourneyVerification>>;
  readonly feedback: readonly JourneyFeedbackSummary[];
}

/**
 * One audit-log entry from `kvota.journey_node_state_history`.
 * Returned by `GET /api/journey/node/{node_id}/history` (most-recent-50).
 *
 * Mirrors `api/models/journey.py::JourneyNodeHistoryEntry`.
 */
export interface JourneyNodeHistoryEntry {
  readonly id: string;
  readonly node_id: JourneyNodeId;
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly notes: string | null;
  readonly version: number;
  readonly changed_by: string | null;
  readonly changed_at: string;
}
