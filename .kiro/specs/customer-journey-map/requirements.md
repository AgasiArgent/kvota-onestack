# Requirements Document — Customer Journey Map (`/journey`)

## Introduction

Customer Journey Map is a new `/journey` page inside onestack that visualises every route × role × user-story intersection as an interactive graph with toggleable annotation layers. Its primary purpose is to close the gap between design intent (specs, ТЗ, access rules) and implementation (actual Next.js code) so that the development team (P1) and the QA team (P2) have a single canonical picture of the system: what screens exist, who sees them, what they are meant to do, whether they are implemented, whether they are verified, and where known gaps live as explicit "ghost" nodes. A secondary goal is to support end-user training (P3) via step-by-step pin-based walkthroughs on real screens; customer-facing demo export (P4) is deferred beyond v1.0.

The architecture is a hybrid: an **immutable `journey-manifest.json`** regenerated from source (Next.js `app/`, `.kiro/specs/`, `.kiro/steering/access-control.md`) on every CI run, combined with **mutable annotations** stored in four new Supabase tables that are joined to the manifest by a stable `node_id` key. Nightly Playwright runs capture per-role screenshots of every route and refresh the bounding-box cache for screen-anchored pins. Pins operate in two modes: QA (expected behaviour + verify log) and Training (ordered steps with markdown explanation).

**Reference documents (authoritative):**
- `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` — full architectural design, single source of truth
- `.kiro/steering/structure.md` — FSD layering, 800-line file limit, Python API boundaries
- `.kiro/steering/tech.md` — Next.js 15, shadcn/ui, Supabase schema `kvota`, role column `r.slug`
- `.kiro/steering/access-control.md` — visibility tiers and edit matrix per role
- `.kiro/steering/api-first.md` — when Python API vs Supabase direct

**Release target:** v1.0 approximately 6 weeks from start. Scope excludes Miro export, session recording, live iframe preview, and mobile layouts.

## Terminology

- **Node** — a single screen on the map. `node_id` is a stable signature such as `app:/quotes/[id]` (for real routes, derived from code) or `ghost:<slug>` (for proposed routes that do not yet exist in code).
- **Manifest** — `frontend/public/journey-manifest.json`, the committed, build-time-generated JSON describing all real nodes, edges, and clusters.
- **Annotation** — mutable data attached to a node: status, ghost metadata, pins, verifications. Stored in Supabase tables keyed by `node_id`.
- **Layer** — a toggleable presentation slice (Roles, Stories, Impl status, QA status, Feedback count, Training, Ghost nodes, Screenshots). Layers combine additively and can be switched on or off independently.
- **Pin** — a selector-anchored annotation on a screenshot. Two modes: `qa` (expected behaviour + verify log) and `training` (ordered step with instruction).
- **Ghost node** — a node that has no corresponding route in code but exists in the annotation DB as a proposed / planned screen; used for gap analysis.
- **Orphan annotation** — an annotation whose `node_id` no longer appears in the current manifest because the route was renamed or removed.
- **`journey-manifest.json`** — authoritative output of the build-time parsers; lives at `frontend/public/journey-manifest.json` and is committed to git.
- **Webhook token** — shared secret `JOURNEY_WEBHOOK_TOKEN` used to authenticate the nightly Playwright action when it posts bbox updates to the Python API.

---

## Requirements

### Requirement 1: Journey Manifest Build & Regeneration

**Objective:** The manifest is a derived artefact of the source tree. It always matches the current code, regenerates on every change to relevant sources, and never drifts silently.

#### Acceptance Criteria

1. THE build-manifest script SHALL produce `frontend/public/journey-manifest.json` by combining outputs of three parsers: `parse-routes.ts` (routes + parent-child tree from `frontend/src/app/**`), `parse-specs.ts` (user stories from `.kiro/specs/**/*.md` frontmatter), `parse-roles.ts` (role × route matrix from `.kiro/steering/access-control.md`).
2. WHEN a developer stages changes to files under `frontend/src/app/**`, `.kiro/specs/**`, or `.kiro/steering/access-control.md`, THE pre-commit hook SHALL run `npm run journey:build` and include the regenerated manifest in the commit.
3. WHEN a pull request is opened or updated, THE CI workflow SHALL regenerate the manifest and compare it against the committed file; IF they differ, THEN CI SHALL fail with a message indicating the committed manifest is stale.
4. THE manifest SHALL include every Next.js `page.tsx` under `frontend/src/app/` (currently 34 routes) and SHALL NOT include pages behind the `(auth)` route group that are not accessible to authenticated users.
5. THE manifest SHALL contain, for every node: `node_id`, `route`, `title`, `cluster`, `source_files`, `roles`, `stories[]`, `parent_node_id`, and `children[]`.
6. THE manifest SHALL be deterministic — two runs over the same source tree produce byte-identical output (snapshot tests guarantee this).
7. THE manifest SHALL be served as static content from `frontend/public/journey-manifest.json` (CDN-cacheable); no API endpoint renders it dynamically.
8. THE manifest file SHALL be small enough to be delivered to the browser in a single request (target ≤ 100 KB for the current route set).

### Requirement 2: Annotation Data Model

**Objective:** Mutable annotations live in four purpose-built Supabase tables in the `kvota` schema, joined to the immutable manifest by `node_id`.

#### Acceptance Criteria

1. THE migration (number assigned at Phase-5d completion, tentatively 284 or later) SHALL create four tables: `kvota.journey_node_state`, `kvota.journey_ghost_nodes`, `kvota.journey_pins`, `kvota.journey_verifications` with the columns, constraints, and foreign keys specified in `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` §3.2.
2. `kvota.journey_node_state` SHALL have `node_id` (text) as PRIMARY KEY, `impl_status` CHECK IN (`done`, `partial`, `missing`), `qa_status` CHECK IN (`verified`, `broken`, `untested`).
3. `kvota.journey_ghost_nodes.node_id` SHALL be UNIQUE and MUST match the pattern `ghost:<slug>`; `status` CHECK IN (`proposed`, `approved`, `in_progress`, `shipped`).
4. `kvota.journey_pins` SHALL have `mode` CHECK IN (`qa`, `training`) and include position-cache columns (`last_x`, `last_y`, `last_width`, `last_height`, `last_position_update`, `selector_broken`).
5. `kvota.journey_verifications` SHALL be append-only; RLS policy SHALL deny UPDATE and DELETE on this table for every role.
6. THE migration SHALL add `node_id` (text) column to `kvota.feedback` with an index, and SHALL populate it via backfill where `page_url` can be mapped to a known route in the initial manifest.
7. THE migration SHALL add a helper function `kvota.user_has_role(slug text) RETURNS boolean` if one does not already exist, reused in all RLS policies for this feature.
8. AFTER the migration is applied to any environment, THE frontend SHALL regenerate `frontend/src/shared/types/database.types.ts` via `npm run db:types` before any frontend code referencing the new tables is deployed.

### Requirement 3: /journey Page — Layout & Navigation

**Objective:** A single page at `/journey` renders the map in a predictable three-pane layout that matches the rest of the onestack visual language.

#### Acceptance Criteria

1. THE route `/journey` SHALL be mounted under the `(app)` route group in `frontend/src/app/(app)/journey/page.tsx`, inheriting the authenticated-user layout and sidebar.
2. THE page SHALL present three panes: left sidebar (~220 px), main canvas (flex), and right drawer (~360 px, slide-in on node click, closed by default).
3. THE left sidebar SHALL contain, in order: eight layer toggles, a role filter dropdown, an impl-status filter, a qa-status filter, a search input, a cluster multi-select.
4. THE main canvas SHALL render the map using React Flow (version pinned during W1) with cluster-level subflows auto-grouped by the `cluster` field in the manifest.
5. WHEN a user clicks a node, THE right drawer SHALL slide in from the right; a subsequent click on the canvas background OR a close button SHALL close it.
6. THE drawer SHALL NOT overlap or dim the canvas — users can see node context and drawer content simultaneously.
7. THE canvas SHALL support pan, zoom, and a minimap for navigation; default viewport SHALL fit all root-cluster nodes into view on first load.
8. THE page SHALL be reachable via the sidebar navigation (to be added to `widgets/sidebar/` under the appropriate section) and SHALL NOT be exposed via deep links until it is ready for internal use.

### Requirement 4: Layer System & Node Rendering

**Objective:** Eight layers combine additively on each node. Layer toggles live in the sidebar and their state persists per user across sessions.

#### Acceptance Criteria

1. THE layer toggles SHALL be: Roles, Stories, Impl status, QA status, Feedback count, Training, Ghost nodes, Screenshots.
2. WHEN the Roles layer is on, THE node SHALL display role chips derived from `manifest.nodes[].roles`.
3. WHEN the Stories layer is on, THE node SHALL display a `📝 N` badge where N is the count of stories attached to the node in the manifest.
4. WHEN the Impl status layer is on, THE node SHALL display a coloured dot sourced from `journey_node_state.impl_status` (green=done, yellow=partial, red=missing, grey=unset).
5. WHEN the QA status layer is on, THE node SHALL display a coloured dot and a `N/M` progress counter sourced from the latest `journey_verifications` row per pin.
6. WHEN the Feedback layer is on, THE node SHALL display a `💬 N` badge where N counts `kvota.feedback` rows with this `node_id` that are visible to the requesting user under existing feedback RLS.
7. WHEN the Ghost nodes layer is off, THE canvas SHALL hide all nodes where `node_id` starts with `ghost:`.
8. WHEN the Screenshots layer is on, THE node SHALL display a small thumbnail of the latest screenshot for the user's primary role when available.
9. THE layer-toggle state SHALL persist per user via localStorage keyed by user ID (not in the database — per-user UI preference only).
10. IF more than four layers are active AND a node would exceed its layout bounds, THEN the node SHALL hide the lowest-priority layers and indicate "…more in drawer" — full information always remains in the drawer.

### Requirement 5: Node Detail Drawer

**Objective:** The drawer exposes every field about the selected node. Editing happens inline in the drawer for permitted roles.

#### Acceptance Criteria

1. THE drawer SHALL display, in order: route path, title, Roles, Stories list (with spec refs), Status (impl + qa with inline-editable controls where permitted), Screenshot (latest) with diff toggle, Feedback list (top 3 + "view all" link), Training steps (collapsed), Pin list with verify buttons (QA mode pins only).
2. WHEN the drawer opens on a ghost node, THE Screenshot and Pin sections SHALL be hidden (screenshots and pins are only meaningful for real routes).
3. THE "view all feedback" link SHALL open `/admin/feedback?node_id=<node_id>` in a new tab and SHALL NOT duplicate feedback-list logic.
4. THE Training steps section SHALL render as ordered markdown blocks when expanded; order SHALL be determined by `journey_pins.training_step_order`.
5. WHEN a status control is edited, THE UI SHALL optimistically update and dispatch a PATCH to the API; on error, THE UI SHALL revert the change and display an inline error.
6. THE drawer SHALL be keyboard-navigable (Tab through sections, Esc to close).

### Requirement 6: Implementation & QA Status Editing

**Objective:** Status writes go through the Python API because the access rule is field-aware; they do NOT go through Supabase direct.

#### Acceptance Criteria

1. THE endpoint `PATCH /api/journey/node/{node_id}/state` SHALL accept a body `{ impl_status?, qa_status?, notes? }` and SHALL upsert a row in `journey_node_state` with `updated_by = auth.uid()` and `updated_at = now()`.
2. WHEN the request sets `impl_status` AND the caller does NOT hold one of roles [`admin`, `head_of_sales`, `head_of_procurement`, `head_of_logistics`], THEN the API SHALL return HTTP 403 with body `{ "success": false, "error": { "code": "FORBIDDEN_FIELD", "message": "Role <slug> cannot write field impl_status" } }`.
3. WHEN the request sets `qa_status` AND the caller does NOT hold one of roles [`admin`, `quote_controller`, `spec_controller`], THEN the API SHALL return HTTP 403 with the same error code.
4. WHEN the request attempts to write both fields AND the caller lacks permission for either one, THEN the API SHALL return 403 without performing a partial write.
5. THE RLS policy on `journey_node_state` SHALL deny all client-direct `INSERT` and `UPDATE`; SELECT is allowed for authenticated users.
6. `top_manager` role SHALL be denied all writes to `journey_node_state` and to the other journey tables (view-only tier per `access-control.md`).

### Requirement 7: Ghost Node Management

**Objective:** `admin` and `top_manager` maintain a list of proposed screens that do not yet exist in code. Ghost nodes surface on the canvas as visually-distinct placeholders so gaps are obvious.

#### Acceptance Criteria

1. `admin` and `top_manager` SHALL be able to create, edit, and delete ghost nodes via Supabase direct with RLS enforcing the role check through `kvota.user_has_role(...)`.
2. WHEN a ghost node is created, `node_id` SHALL be derived as `ghost:<slug>` where slug is URL-safe and unique across the table (UNIQUE constraint enforced).
3. THE canvas SHALL render ghost nodes with: dashed border, a leading 👻 emoji in the route field, and a "planned in <planned_in>" metadata line.
4. WHEN the Ghost nodes layer is off, THE canvas SHALL hide all ghost nodes and their connecting edges; ghost-only edges (ghost→real or ghost→ghost) SHALL not count toward canvas layout.
5. A ghost node SHALL be convertible to a real node only by shipping the corresponding route in code (the manifest regeneration picks it up); THE UI SHALL provide a "mark as shipped" button that sets `status='shipped'` and archives the ghost row without deletion (to preserve audit trail).
6. WHEN a ghost node's `parent_node_id` refers to a node that does not exist in the manifest AND is not another ghost, THEN the UI SHALL surface a warning but the ghost SHALL still render in an unclustered lane.

### Requirement 8: Screen Pins — Dual Mode

**Objective:** Pins anchor expected-behaviour annotations or training steps to specific DOM elements on real screens. Their position is derived from a CSS selector, not from screenshot coordinates, so they survive UI re-layouts.

#### Acceptance Criteria

1. `admin`, `quote_controller`, and `spec_controller` SHALL create pins via Supabase direct with RLS enforcement; a pin row SHALL carry `node_id`, `selector`, `expected_behavior`, `mode` ∈ `{qa, training}`, optional `training_step_order`, optional `linked_story_ref`.
2. WHEN `mode = 'training'`, THE pin SHALL require a non-null `training_step_order`; the UI SHALL enforce this before dispatching the request.
3. WHEN the nightly Playwright run resolves the pin's selector on the captured page, THE action SHALL post the resulting `{x, y, width, height}` bbox and `selector_broken: false` to `POST /api/journey/playwright-webhook`.
4. WHEN the selector does not resolve (element absent or ambiguous), THE action SHALL post `selector_broken: true` with no bbox; the UI SHALL visually flag the pin as broken.
5. THE pin-creation UI SHALL accept the selector either (a) entered manually or (b) via a "Pick element" mode that loads the page in a devtools-like picker and captures the selector automatically (the latter is W5 work, see Requirement 10).
6. THE pin-detail popover SHALL show: selector, expected_behavior, linked_story_ref (if present and resolvable), mode, and in QA mode the verify-buttons (see Requirement 9).
7. Pins of `mode='training'` SHALL NOT display verify buttons; they are pure reading material.
8. IF a pin's selector has been broken for more than 7 consecutive days, THEN the UI SHALL surface it in a "Pins needing attention" list at the top of `/journey` (admin view only).

### Requirement 9: QA Verification Events

**Objective:** Each QA verify click is a permanent event. History is preserved for regression detection and audit.

#### Acceptance Criteria

1. WHEN a user clicks a verify button on a QA pin, THE UI SHALL dispatch an INSERT into `kvota.journey_verifications` with `{pin_id, node_id, result ∈ {verified, broken, skip}, note?}`.
2. THE RLS policy on `journey_verifications` SHALL allow INSERT for `admin`, `quote_controller`, `spec_controller`; UPDATE and DELETE SHALL be denied for every role (append-only).
3. THE node's QA status dot SHALL reflect the **latest** verification per pin, not an aggregate historical view.
4. THE drawer SHALL provide a "history" expander per pin that lists prior verifications with timestamp and actor.
5. WHEN a user records "broken" with a note, THE system SHALL also auto-create a feedback row linked to the same node_id (via existing feedback mechanism) with the verification note as body; this closes the loop between QA and dev.

### Requirement 10: Nightly Screenshots Pipeline

**Objective:** Every night, Playwright captures each route as each role, stores screenshots in Supabase Storage, and refreshes pin bounding boxes.

#### Acceptance Criteria

1. THE GitHub Action `.github/workflows/journey-screenshots.yml` SHALL be triggered on schedule `0 3 * * *` (UTC) and via `workflow_dispatch`.
2. THE action SHALL run: (a) `npm run journey:build`, (b) spin up a staging environment with `docker-compose.ci.yml`, (c) iterate over manifest × roles × pins, (d) post batched bbox updates to the Python webhook.
3. THE action SHALL authenticate as one test user per role via email pattern `qa-{role_slug}@kvotaflow.ru` with credentials from GitHub secret `JOURNEY_TEST_USERS_PASSWORD`.
4. THE seeding step SHALL ensure these 12 test users exist in the staging `auth.users` and `kvota.user_roles` tables (idempotent SQL in a migration or seed script).
5. WHEN a screenshot is captured, THE action SHALL upload the PNG to Supabase Storage bucket `journey-screenshots` at path `{role}/{node_id_safe}/{YYYY-MM-DD}.png`; `node_id_safe` replaces `/` with `_` and escapes brackets.
6. THE action SHALL retain the two most recent screenshots per `(role, node_id)`; older files SHALL be deleted by the same action run to keep storage bounded.
7. THE endpoint `POST /api/journey/playwright-webhook` SHALL require header `X-Journey-Webhook-Token` to match server-side secret `JOURNEY_WEBHOOK_TOKEN`; otherwise return 401.
8. THE webhook body SHALL accept a batch of `{pin_id, x, y, width, height, selector_broken}` objects and SHALL update the corresponding `journey_pins` rows in a single transaction.
9. IF three consecutive nightly runs fail, THEN the action SHALL open a GitHub Issue tagged `journey-ops` for manual inspection.

### Requirement 11: Feedback Integration

**Objective:** Existing `/admin/feedback` flow is not rebuilt. Only the node-id link is added and surfaced.

#### Acceptance Criteria

1. `kvota.feedback.node_id` SHALL be populated: (a) by backfill during the Phase migration for existing rows where `page_url` maps cleanly to a manifest node, (b) by new-feedback creation logic which passes the current route when invoked from within `/journey` or from any app page that already knows its route.
2. THE feedback-count badge on a `/journey` node SHALL respect the requesting user's existing feedback visibility — counts SHALL reflect only rows the user can `SELECT` under existing feedback RLS.
3. WHEN a user opens "view all" on a node's feedback list, THE system SHALL navigate to `/admin/feedback?node_id=<node_id>` and the feedback page SHALL filter to that node.
4. NO changes to `/admin/feedback` UI beyond accepting the `node_id` query parameter and filtering by it.

### Requirement 12: Access Control & Role Enforcement

**Objective:** The journey page respects onestack's existing visibility tiers. Write permissions are enforced at the API (fine-grained) and at RLS (coarse-grained).

#### Acceptance Criteria

1. WHEN an unauthenticated user requests `/journey`, THE app middleware SHALL redirect to the login flow (consistent with other `(app)` routes).
2. WHEN an authenticated user with any role requests `/journey`, THE page SHALL load with READ access to all journey tables; the layer content may vary (e.g., feedback count filtered by existing feedback RLS).
3. THE RLS policies on journey tables SHALL allow SELECT for all authenticated users.
4. THE RLS policies SHALL deny all client-direct INSERT / UPDATE / DELETE on `journey_node_state` (writes only through Python API).
5. THE RLS policies on `journey_ghost_nodes` SHALL allow INSERT/UPDATE/DELETE only when `kvota.user_has_role('admin') OR kvota.user_has_role('top_manager')`; **correction:** per access-control.md `top_manager` is view-only, so effective writers are `admin` only (ghost authoring is admin-only for v1.0 — `top_manager` write was dropped from design).
6. THE RLS policies on `journey_pins` SHALL allow INSERT/UPDATE/DELETE only for `admin`, `quote_controller`, `spec_controller`.
7. THE RLS policies on `journey_verifications` SHALL allow INSERT only for `admin`, `quote_controller`, `spec_controller` and SHALL deny UPDATE/DELETE for every role.
8. Per-field write rules on `journey_node_state` (impl vs qa) SHALL be enforced in Python API handlers (see Requirement 6), not in RLS.
9. THE design-document §6 matrix SHALL be updated to remove `top_manager` from any write row; this is tracked as a design-doc amendment during kiro design-phase review.

### Requirement 13: Orphan Annotations Handling

**Objective:** When a route is renamed or removed, its annotations are preserved and surfaced for manual retargeting.

#### Acceptance Criteria

1. WHEN the manifest regeneration produces a manifest where a previously-present `node_id` is absent, THE system SHALL identify all annotations in the four tables that reference that `node_id` as "orphaned".
2. THE `/journey` page SHALL display an "Orphaned annotations" banner in the sidebar when any orphans exist (with count).
3. WHEN an admin opens the orphan panel, THE UI SHALL list each orphaned `node_id` with: counts per table, preview of top annotations, and a "Retarget to..." action.
4. WHEN an admin selects a target `node_id` for retargeting, THE system SHALL UPDATE all rows in the four tables (and `kvota.feedback.node_id`) from old to new value within a single transaction.
5. THE system SHALL NOT automatically match orphans to new node_ids by path similarity. All retargeting SHALL be explicit admin action.
6. Orphan counts SHALL be visible only to `admin` role.

### Requirement 14: Testing & Quality Gates

**Objective:** Three test tiers ensure correctness: parsers (unit), API and merge logic (integration), and critical user paths (E2E smoke).

#### Acceptance Criteria

1. Unit tests using Vitest SHALL cover each parser (`parse-routes`, `parse-specs`, `parse-roles`, `build-manifest`) with fixture trees; `build-manifest` SHALL have a snapshot test.
2. Integration tests using pytest SHALL cover `/api/journey/nodes`, `/api/journey/node/{node_id}`, `/api/journey/node/{node_id}/state` (including FORBIDDEN_FIELD cases), and `/api/journey/playwright-webhook` (including selector_broken flagging and token rejection).
3. An E2E smoke test using Playwright SHALL exercise the happy-path: open `/journey` as admin → toggle a layer → click a node → open drawer → create a ghost → mark a QA verification → observe the counter increment.
4. RLS policies SHALL be covered by automated tests verifying that each role can/cannot perform each write operation per the matrix in Requirement 12.
5. THE nightly screenshot action SHALL succeed for three consecutive nights without manual retry before v1.0 is declared.

### Requirement 15: Non-Functional Requirements

#### Acceptance Criteria

1. THE `/journey` page SHALL render initial canvas (manifest + basic layers) within 2 seconds on a modern laptop with a warm cache.
2. THE manifest file SHALL be cache-controlled via standard Next.js static asset headers (long-lived cache, busted by content hash).
3. THE API endpoints SHALL return JSON in the standard OneStack envelope `{ success: bool, data?, error? }`.
4. THE page SHALL work on screens ≥ 1280 × 720; smaller viewports are out of scope for v1.0.
5. THE UI text SHALL be in Russian to match the rest of OneStack.
6. THE screenshots pipeline SHALL consume no more than 2 GB of Supabase Storage in steady state (retention of 2 images per (role, node) with ~12 roles × ~34 nodes × ~100 KB/image ≈ 82 MB budget, generous ceiling).

### Requirement 16: Release Criteria for v1.0

**Objective:** Explicit, verifiable gates before declaring v1.0 shipped.

#### Acceptance Criteria

1. All 34 current Next.js routes (per `frontend/src/app/(app)/**`) SHALL be present as nodes in the manifest; a CI check SHALL verify this count and fail if any route is unmapped.
2. Admin SHALL be able to create a ghost node and see it appear on the canvas without a page reload.
3. QA SHALL be able to open any node's drawer, view its screenshot with pin overlay, record a verification, and observe the QA-status dot update.
4. The nightly screenshot action SHALL have completed successfully three consecutive nights.
5. RLS policy tests SHALL all pass; no role SHALL be able to write outside its tier.
6. A junior QA team member SHALL complete a review of one screen (view expected behaviour, click verify on each pin) in under 15 minutes after a 15-minute onboarding session.
7. Internal demo to dev + QA teams SHALL be held and feedback captured before public announcement.
8. `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` §6 matrix SHALL be updated to remove `top_manager` from write rows (amendment tracked in the design-phase review).

---

## Next Step

```
/kiro:spec-design customer-journey-map -y
```

Run gap analysis first if desired:
```
/kiro:validate-gap customer-journey-map
```

`-y` proceeds to design generation after requirements are reviewed here.
