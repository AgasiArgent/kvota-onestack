# Requirements Document — Customer Journey Map (`/journey`)

## Introduction

Customer Journey Map is a new `/journey` page inside onestack that visualises every route × role × user-story intersection as an interactive graph with toggleable annotation layers. Its primary purpose is to close the gap between design intent (specs, ТЗ, access rules) and implementation (actual Next.js code) so that the development team (P1) and the QA team (P2) have a single canonical picture of the system: what screens exist, who sees them, what they are meant to do, whether they are implemented, whether they are verified, and where known gaps live as explicit "ghost" nodes. A secondary goal is to support end-user training (P3) via step-by-step pin-based walkthroughs on real screens; customer-facing demo export (P4) is deferred beyond v1.0.

The architecture is a hybrid: an **immutable `journey-manifest.json`** regenerated from source (Next.js `app/`, `.kiro/specs/`, `.kiro/steering/access-control.md`) on every CI run, combined with **mutable annotations** stored in five new Supabase tables that are joined to the manifest by a stable `node_id` key. Nightly Playwright runs capture per-role screenshots of every route and refresh the bounding-box cache for screen-anchored pins. Pins operate in two modes: QA (expected behaviour + verify log) and Training (ordered steps with markdown explanation).

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
- **Annotation** — mutable data attached to a node: status, ghost metadata, pins, verifications, status history. Stored in Supabase tables keyed by `node_id`.
- **Layer** — a toggleable presentation slice (Roles, Stories, Impl status, QA status, Feedback count, Training, Ghost nodes, Screenshots). Layers combine additively and can be switched on or off independently.
- **Pin** — a selector-anchored annotation on a screenshot. Two modes: `qa` (expected behaviour + verify log) and `training` (ordered step with instruction).
- **Ghost node** — a node that has no corresponding route in code but exists in the annotation DB as a proposed / planned screen; used for gap analysis.
- **Orphan annotation** — an annotation whose `node_id` no longer appears in the current manifest because the route was renamed or removed.
- **Webhook token** — shared secret `JOURNEY_WEBHOOK_TOKEN` used to authenticate the nightly Playwright action when it posts bbox updates to the Python API.
- **View-as-role** — a sidebar filter that restricts the canvas to nodes visible to a selected role, letting any user (typically QA) inspect the UX from another role's perspective.

---

## Requirements

### Requirement 1: Journey Manifest Build & Regeneration

**Objective:** The manifest is a derived artefact of the source tree. It always matches the current code, regenerates on every change to relevant sources, and never drifts silently.

#### Acceptance Criteria

1. THE build-manifest script SHALL produce `frontend/public/journey-manifest.json` by combining outputs of three parsers: `parse-routes.ts` (routes + parent-child tree from `frontend/src/app/**`), `parse-specs.ts` (user stories from `.kiro/specs/**/*.md` frontmatter), `parse-roles.ts` (role × route matrix from `.kiro/steering/access-control.md`).
2. WHEN a developer stages changes to files under `frontend/src/app/**`, `.kiro/specs/**`, or `.kiro/steering/access-control.md`, THE pre-commit hook SHALL run `npm run journey:build` and include the regenerated manifest in the commit.
3. WHEN a pull request is opened or updated, THE CI workflow SHALL regenerate the manifest and compare it against the committed file; IF they differ, THEN CI SHALL fail with a message indicating the committed manifest is stale.
4. THE manifest SHALL include every Next.js `page.tsx` under `frontend/src/app/` that is reachable by authenticated users (currently 34 routes under `(app)/`). THE manifest SHALL NOT include `page.tsx` files behind the `(auth)` route group (login, register) because those are pre-authentication.
5. `parse-routes.ts` SHALL correctly handle Next.js 15 special conventions: `(folder)` route groups strip the parenthesised segment from the public route path; `[slug]` dynamic segments preserve the bracket notation in `node_id`; `[[catchAll]]` optional-catch-all segments expand into their own node with a flag; parallel routes (`@folder`) generate one node per named slot; interceptor routes `(.)folder` and `(..)folder` are treated as separate nodes distinct from their targets. Snapshot tests SHALL cover at least one example of each.
6. `parse-specs.ts` SHALL bind each user story to routes via, in order of priority: (a) explicit `related_routes:` array in the spec's frontmatter, (b) fuzzy match by spec directory name against route segments (e.g., directory `phase-5b-quote-composition` → candidate routes `/quotes/[id]`), (c) an "unbound" bucket surfaced in the UI for manual triage.
7. A one-time migration script `scripts/journey/backfill-related-routes.ts` SHALL scan the 32 existing `.kiro/specs/**/*.md` files, detect URL-like strings in the text, propose a `related_routes:` frontmatter addition per spec, and output a human-review patch file. No frontmatter SHALL be written automatically; the admin reviews and applies the patch manually.
8. THE manifest SHALL contain, for every node: `node_id`, `route`, `title`, `cluster`, `source_files`, `roles`, `stories[]`, `parent_node_id`, `children[]`.
9. THE `title` field SHALL be extracted by priority: (1) `export const metadata = { title: ... }` from `page.tsx`, (2) first `/** @journey-title "..." */` JSDoc comment in `page.tsx`, (3) first `<h1>` literal text in the page component, (4) route basename (e.g., `quotes` → "Quotes"). The parser records which source level produced the title for debugging.
10. THE manifest SHALL be deterministic — two runs over the same source tree produce byte-identical output (snapshot tests guarantee this).
11. THE manifest SHALL be served as static content from `frontend/public/journey-manifest.json` (CDN-cacheable); no API endpoint renders it dynamically.
12. THE manifest file SHALL be small enough to be delivered to the browser in a single request (target ≤ 100 KB for the current route set).

### Requirement 2: Annotation Data Model

**Objective:** Mutable annotations live in five purpose-built Supabase tables in the `kvota` schema, joined to the immutable manifest by `node_id`.

#### Acceptance Criteria

1. THE migration (number assigned at Phase-5d completion, tentatively 284 or later) SHALL create five tables: `kvota.journey_node_state`, `kvota.journey_node_state_history`, `kvota.journey_ghost_nodes`, `kvota.journey_pins`, `kvota.journey_verifications` with the columns, constraints, and foreign keys specified in the referenced design document §3.2 as amended by this requirements document.
2. `kvota.journey_node_state` SHALL have `node_id` (text) as PRIMARY KEY, `impl_status` CHECK IN (`done`, `partial`, `missing`), `qa_status` CHECK IN (`verified`, `broken`, `untested`), `notes` text, `version` int NOT NULL DEFAULT 1, `last_tested_at` timestamptz, `updated_at` timestamptz, `updated_by` uuid REFERENCES auth.users(id).
3. `kvota.journey_node_state_history` SHALL capture a before-image on every UPDATE of `journey_node_state` via AFTER UPDATE trigger. Columns: `id` uuid PK, `node_id`, `impl_status`, `qa_status`, `notes`, `version`, `changed_by` uuid, `changed_at` timestamptz DEFAULT now(). Append-only: UPDATE and DELETE denied by RLS for every role. THE drawer SHALL be able to render this history lazily via a dedicated API endpoint.
4. `kvota.journey_ghost_nodes.node_id` SHALL be UNIQUE and MUST match the pattern `ghost:<slug>`; `status` CHECK IN (`proposed`, `approved`, `in_progress`, `shipped`).
5. `kvota.journey_pins` SHALL have `mode` CHECK IN (`qa`, `training`) and include position-cache columns storing **relative** coordinates (fractions of screenshot dimensions, range 0.0–1.0, `numeric(6,4)`): `last_rel_x`, `last_rel_y`, `last_rel_width`, `last_rel_height`, plus `last_position_update` and `selector_broken`. Relative coordinates survive screenshot-size changes (viewport resize, DPR differences) without repositioning.
6. `kvota.journey_verifications` SHALL be append-only. Columns: `id`, `pin_id`, `node_id`, `result` CHECK IN (`verified`, `broken`, `skip`), `note` text, `attachment_urls` text[] (nullable; each element is a Supabase Storage object key pointing to an uploaded screenshot), `tested_by`, `tested_at`. RLS policy SHALL deny UPDATE and DELETE for every role.
7. THE migration SHALL add `node_id` (text) column to `kvota.user_feedback` with an index, and SHALL populate it via backfill where `page_url` can be mapped to a known route in the initial manifest.
8. THE migration SHALL add a helper function `kvota.user_has_role(slug text) RETURNS boolean` if one does not already exist, reused in all RLS policies for this feature.
9. AFTER the migration is applied to any environment, THE frontend SHALL regenerate `frontend/src/shared/types/database.types.ts` via `npm run db:types` before any frontend code referencing the new tables is deployed.

### Requirement 3: /journey Page — Layout, Navigation, Filtering, Deep-Linking

**Objective:** A single page at `/journey` renders the map in a predictable three-pane layout; user selection state is shareable via URL.

#### Acceptance Criteria

1. THE route `/journey` SHALL be mounted under the `(app)` route group in `frontend/src/app/(app)/journey/page.tsx`, inheriting the authenticated-user layout and sidebar.
2. THE page SHALL present three panes: left sidebar (~220 px), main canvas (flex), and right drawer (~360 px, slide-in on node click, closed by default).
3. THE left sidebar SHALL contain, in order: eight layer toggles, a role filter dropdown ("View as role"), an impl-status filter, a qa-status filter, a search input, a cluster multi-select.
4. THE "View as role" filter SHALL have two states: (a) "All roles (admin view)" — every node visible, (b) "Role = X" — canvas shows only nodes where `X` is present in `manifest.nodes[].roles`; hidden nodes are not counted in badge totals.
5. THE search input SHALL match case-insensitively across: `route`, `title`, story actor and goal text (`manifest.nodes[].stories[]`), ghost `proposed_route` and `title`, pin `expected_behavior` text. Matched nodes SHALL be visually highlighted; non-matched nodes SHALL fade to low opacity but remain on canvas for context.
6. THE main canvas SHALL render the map using React Flow (version pinned during W1) with cluster-level subflows auto-grouped by the `cluster` field in the manifest; initial node positions SHALL be computed via `dagre` auto-layout.
7. WHEN a user clicks a node, THE right drawer SHALL slide in from the right; a subsequent click on the canvas background OR a close button SHALL close it.
8. THE drawer SHALL NOT overlap or dim the canvas — users can see node context and drawer content simultaneously.
9. THE canvas SHALL support pan, zoom, and a minimap for navigation; default viewport SHALL fit all root-cluster nodes into view on first load.
10. THE URL SHALL reflect user selection state: query parameters `?node=<node_id>` for selected node, `?layers=<comma-separated-slugs>` for active layers, `?viewas=<role_slug>` for view-as-role filter. Changes in state SHALL update the URL via `router.replace` (not `push`) to avoid polluting history. On page load with these params present, THE page SHALL restore state.
11. THE page SHALL be reachable via the sidebar navigation (to be added to `widgets/sidebar/` under the appropriate section) and SHALL NOT be exposed via deep links until it is ready for internal use.

### Requirement 4: Layer System & Node Rendering

**Objective:** Eight layers combine additively on each node. Layer toggles live in the sidebar and their state persists per user across sessions.

#### Acceptance Criteria

1. THE layer toggles SHALL be: Roles, Stories, Impl status, QA status, Feedback count, Training, Ghost nodes, Screenshots.
2. WHEN the Roles layer is on, THE node SHALL display role chips derived from `manifest.nodes[].roles`.
3. WHEN the Stories layer is on, THE node SHALL display a `📝 N` badge where N is the count of stories attached to the node in the manifest.
4. WHEN the Impl status layer is on, THE node SHALL display a coloured dot sourced from `journey_node_state.impl_status` (green=done, yellow=partial, red=missing, grey=unset).
5. WHEN the QA status layer is on, THE node SHALL display a coloured dot and a `N/M` progress counter sourced from the latest `journey_verifications` row per pin.
6. WHEN the Feedback layer is on, THE node SHALL display a `💬 N` badge where N counts `kvota.user_feedback` rows with this `node_id` that are visible to the requesting user under existing feedback RLS.
7. WHEN the Ghost nodes layer is off, THE canvas SHALL hide all nodes where `node_id` starts with `ghost:`.
8. WHEN the Screenshots layer is on, THE node SHALL display a small thumbnail of the latest screenshot for the user's primary role when available; for users without a primary role or without a screenshot, the placeholder is a neutral grey box.
9. THE layer-toggle state SHALL persist per user via localStorage keyed by user ID, AND SHALL be overridable by URL `layers=` parameter (URL takes precedence on page load per Req 3.10).
10. IF more than four layers are active AND a node would exceed its layout bounds, THEN the node SHALL hide the lowest-priority layers and indicate "…more in drawer" — full information always remains in the drawer.

### Requirement 5: Node Detail Drawer

**Objective:** The drawer exposes every field about the selected node. Editing happens inline in the drawer for permitted roles.

#### Acceptance Criteria

1. THE drawer SHALL display, in order: route path, title, Roles, Stories list (with spec refs), Status (impl + qa with inline-editable controls where permitted, plus "history" expander), Screenshot (latest) with diff toggle, Feedback list (top 3 + "view all" link), Training steps (collapsed), Pin list with verify buttons (QA mode pins only).
2. WHEN the drawer opens on a ghost node, THE Screenshot and Pin sections SHALL be hidden (screenshots and pins are only meaningful for real routes).
3. THE "view all feedback" link SHALL open `/admin/feedback?node_id=<node_id>` in a new tab and SHALL NOT duplicate feedback-list logic.
4. THE Training steps section SHALL render as ordered markdown blocks when expanded; order SHALL be determined by `journey_pins.training_step_order`.
5. WHEN a status control is edited, THE UI SHALL optimistically update and dispatch a PATCH to the API; on error, THE UI SHALL revert the change and display an inline error.
6. THE drawer SHALL be keyboard-navigable (Tab through sections, Esc to close).
7. THE "history" expander in the Status section SHALL fetch and render `journey_node_state_history` rows for the node in reverse chronological order (`changed_at`, `changed_by`, old→new value).

### Requirement 6: Implementation & QA Status Editing (with Concurrency Guard)

**Objective:** Status writes go through the Python API because the access rule is field-aware; they are protected against concurrent-update races.

#### Acceptance Criteria

1. THE endpoint `PATCH /api/journey/node/{node_id}/state` SHALL accept a body `{ impl_status?, qa_status?, notes?, version }` where `version` is the last version the client saw, and SHALL upsert a row in `journey_node_state` only if the stored `version` equals the submitted `version`.
2. WHEN the submitted `version` does not match the stored `version`, THEN the API SHALL return HTTP 409 CONFLICT with body `{ "success": false, "error": { "code": "STALE_VERSION", "message": "Record was updated by another user" }, "data": { "current": {…full state…} } }`. THE UI SHALL display the conflict to the user with a "refresh" action.
3. WHEN the write succeeds, THE API SHALL increment `version` by 1 and return the new state; the UPDATE trigger SHALL copy the previous row to `journey_node_state_history`.
4. WHEN the request sets `impl_status` AND the caller does NOT hold one of roles [`admin`, `head_of_sales`, `head_of_procurement`, `head_of_logistics`], THEN the API SHALL return HTTP 403 with body `{ "success": false, "error": { "code": "FORBIDDEN_FIELD", "message": "Role <slug> cannot write field impl_status" } }`.
5. WHEN the request sets `qa_status` AND the caller does NOT hold one of roles [`admin`, `quote_controller`, `spec_controller`], THEN the API SHALL return HTTP 403 with the same error code.
6. WHEN the request attempts to write both fields AND the caller lacks permission for either one, THEN the API SHALL return 403 without performing a partial write.
7. THE RLS policy on `journey_node_state` SHALL deny all client-direct `INSERT` and `UPDATE`; SELECT is allowed for authenticated users.
8. `top_manager` role SHALL be denied all writes to `journey_node_state` and to the other journey tables (view-only tier per `access-control.md`).
9. THE endpoint `GET /api/journey/node/{node_id}/history` SHALL return the `journey_node_state_history` rows for the node (most recent 50), permitted for any authenticated user.

### Requirement 7: Ghost Node Management

**Objective:** `admin` maintains a list of proposed screens that do not yet exist in code. Ghost nodes surface on the canvas as visually-distinct placeholders so gaps are obvious.

#### Acceptance Criteria

1. `admin` SHALL be able to create, edit, and delete ghost nodes via Supabase direct with RLS enforcing the role check through `kvota.user_has_role('admin')`. Per `access-control.md`, `top_manager` is view-only and is NOT permitted to write ghost nodes.
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
3. WHEN the nightly Playwright run resolves the pin's selector on the captured page, THE action SHALL compute relative coordinates by dividing the resulting `boundingBox()` `{x, y, width, height}` by the page's `viewportSize()` width/height, and SHALL post the 4-tuple `{rel_x, rel_y, rel_width, rel_height}` (all in 0.0–1.0) plus `selector_broken: false` to `POST /api/journey/playwright-webhook`.
4. WHEN the selector does not resolve (element absent or ambiguous), THE action SHALL post `selector_broken: true` with no bbox; the UI SHALL visually flag the pin as broken.
5. THE pin-creation UI SHALL accept the selector either (a) entered manually or (b) via a "Pick element" mode that loads the page in a devtools-like picker and captures the selector automatically (the latter is W5 work, see Requirement 10).
6. THE pin-detail popover SHALL show: selector, expected_behavior, linked_story_ref (if present and resolvable), mode, and in QA mode the verify-buttons (see Requirement 9).
7. Pins of `mode='training'` SHALL NOT display verify buttons; they are pure reading material.
8. IF a pin's selector has been broken for more than 7 consecutive days, THEN the UI SHALL surface it in a "Pins needing attention" list at the top of `/journey` (admin view only).

### Requirement 9: QA Verification Events (with Screenshot Attachments)

**Objective:** Each QA verify click is a permanent event with optional evidence. History is preserved for regression detection and audit.

#### Acceptance Criteria

1. WHEN a user clicks a verify button on a QA pin, THE UI SHALL dispatch an INSERT into `kvota.journey_verifications` with `{pin_id, node_id, result ∈ {verified, broken, skip}, note?, attachment_urls?}`.
2. THE RLS policy on `journey_verifications` SHALL allow INSERT for `admin`, `quote_controller`, `spec_controller`; UPDATE and DELETE SHALL be denied for every role (append-only).
3. THE node's QA status dot SHALL reflect the **latest** verification per pin, not an aggregate historical view.
4. THE drawer SHALL provide a "history" expander per pin that lists prior verifications with timestamp, actor, note, and thumbnails of any attached screenshots.
5. WHEN a user records "broken" with a note, THE system SHALL also auto-create a feedback row linked to the same node_id (via existing feedback mechanism) with the verification note as body and the first attachment (if any) as the feedback's attached image.
6. THE UI SHALL allow a user to attach up to 3 screenshots per verification before dispatching the INSERT. Screenshots SHALL be uploaded to Supabase Storage bucket `journey-verification-attachments` at path `{node_id_safe}/{verification_id_placeholder}/{index}.{ext}`; object keys SHALL be stored in `attachment_urls` text[] after upload completes. Upload failures SHALL block the INSERT; partial attachment is not permitted.
7. THE Supabase Storage bucket `journey-verification-attachments` SHALL be private; read access SHALL be granted only via signed URLs (1-hour TTL) issued to authenticated users; no anonymous access.
8. Attachment files SHALL be images only (MIME types `image/png`, `image/jpeg`, `image/webp`), max 2 MB each, max 3 per verification. Client-side validation enforces these limits before upload; server-side rejects oversized uploads at the storage policy.

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
8. THE webhook body SHALL accept a batch of `{pin_id, rel_x, rel_y, rel_width, rel_height, selector_broken}` objects (coordinates in 0.0–1.0) and SHALL update the corresponding `journey_pins` rows in a single transaction.
9. IF three consecutive nightly runs fail, THEN the action SHALL open a GitHub Issue tagged `journey-ops` for manual inspection.

### Requirement 11: Feedback Integration

**Objective:** Existing `/admin/feedback` flow is not rebuilt. Only the node-id link is added and surfaced.

#### Acceptance Criteria

1. `kvota.user_feedback.node_id` SHALL be populated: (a) by backfill during the Phase migration for existing rows where `page_url` maps cleanly to a manifest node, (b) by new-feedback creation logic which passes the current route when invoked from within `/journey` or from any app page that already knows its route.
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
5. THE RLS policies on `journey_ghost_nodes` SHALL allow INSERT/UPDATE/DELETE only when `kvota.user_has_role('admin')`. Note: earlier design draft included `top_manager` here; this is corrected — `top_manager` is view-only per `access-control.md`.
6. THE RLS policies on `journey_pins` SHALL allow INSERT/UPDATE/DELETE only for `admin`, `quote_controller`, `spec_controller`.
7. THE RLS policies on `journey_verifications` SHALL allow INSERT only for `admin`, `quote_controller`, `spec_controller` and SHALL deny UPDATE/DELETE for every role.
8. THE RLS policy on `journey_node_state_history` SHALL allow SELECT for authenticated users; INSERT happens via trigger (SECURITY DEFINER); UPDATE/DELETE denied for every role.
9. Per-field write rules on `journey_node_state` (impl vs qa) SHALL be enforced in Python API handlers (see Requirement 6), not in RLS.
10. THE design-document §6 matrix SHALL be updated to remove `top_manager` from all write rows; this is tracked as a design-doc amendment during kiro design-phase review.

### Requirement 13: Orphan Annotations Handling

**Objective:** When a route is renamed or removed, its annotations are preserved and surfaced for manual retargeting.

#### Acceptance Criteria

1. WHEN the manifest regeneration produces a manifest where a previously-present `node_id` is absent, THE system SHALL identify all annotations in the five tables that reference that `node_id` as "orphaned".
2. THE `/journey` page SHALL display an "Orphaned annotations" banner in the sidebar when any orphans exist (with count).
3. WHEN an admin opens the orphan panel, THE UI SHALL list each orphaned `node_id` with: counts per table, preview of top annotations, and a "Retarget to..." action.
4. WHEN an admin selects a target `node_id` for retargeting, THE system SHALL UPDATE all rows in the five tables (and `kvota.user_feedback.node_id`) from old to new value within a single transaction.
5. THE system SHALL NOT automatically match orphans to new node_ids by path similarity. All retargeting SHALL be explicit admin action.
6. Orphan counts SHALL be visible only to `admin` role.

### Requirement 14: Error & Loading States

**Objective:** The `/journey` page degrades gracefully when dependencies are slow, missing, or broken.

#### Acceptance Criteria

1. WHEN `journey-manifest.json` fails to load (network error, 404, parse error), THE page SHALL display an error state with a retry button and a link to the operations channel; the canvas SHALL not render in partial state.
2. WHEN the `/api/journey/nodes` endpoint returns HTTP 5xx, THE UI SHALL retry up to 3 times with exponential backoff (1s, 2s, 4s); on persistent failure, THE UI SHALL display a toast with the error code and keep prior data (if any) visible.
3. WHEN the database is fresh and no rows exist in `journey_node_state`, THE canvas SHALL render all nodes with `impl_status='unset'` (grey dot) and `qa_status='untested'`; NO error message SHALL be shown.
4. WHEN a pin exists in `journey_pins` but has `last_rel_x IS NULL` (never resolved by Playwright), THE drawer SHALL render the pin in a list WITHOUT the screen overlay, with a note "Position pending next nightly run".
5. WHEN a screenshot is missing for the user's primary role on a given node (not yet captured, or retention rotated it out), THE drawer SHALL display a "No screenshot available" placeholder and a button "Request capture" that triggers an on-demand workflow_dispatch of the nightly action for that single node (admin only).
6. WHEN a verification attachment fails to load (signed URL expired, file missing), THE history row SHALL display a broken-image icon and the verification metadata SHALL still render.
7. WHEN an optimistic status edit (Req 6) is rolled back due to a 409, 403, or 5xx, THE UI SHALL display a non-blocking toast with the reason and revert the inline control to its stored value within 300 ms.
8. ALL empty states, loading skeletons, and retry UIs SHALL follow the onestack design system: `design-system.md` tokens, Inter font, no `transition: all`, no `translateY` hover, constrained spacing.

### Requirement 15: Testing & Quality Gates

**Objective:** Three test tiers ensure correctness: parsers (unit), API and merge logic (integration), and critical user paths (E2E smoke).

#### Acceptance Criteria

1. Unit tests using Vitest SHALL cover each parser (`parse-routes`, `parse-specs`, `parse-roles`, `build-manifest`) with fixture trees that include `(group)` route groups, `[id]` dynamic segments, `[[catchAll]]` optional-catch-all, and `@parallel` parallel routes; `build-manifest` SHALL have a snapshot test.
2. Integration tests using pytest SHALL cover `/api/journey/nodes`, `/api/journey/node/{node_id}`, `/api/journey/node/{node_id}/state` (including FORBIDDEN_FIELD and STALE_VERSION cases), `/api/journey/node/{node_id}/history`, and `/api/journey/playwright-webhook` (including selector_broken flagging and token rejection).
3. An E2E smoke test using Playwright SHALL exercise the happy-path: open `/journey` as admin → toggle a layer → click a node → open drawer → create a ghost → mark a QA verification with a screenshot attachment → observe the counter increment and attachment visible in history.
4. RLS policies SHALL be covered by automated tests verifying that each role can/cannot perform each write operation per the matrix in Requirement 12; `top_manager` is explicitly exercised to confirm read-only.
5. THE nightly screenshot action SHALL succeed for three consecutive nights without manual retry before v1.0 is declared.
6. A concurrent-edit test SHALL verify that two simultaneous PATCH requests with the same `version` result in exactly one success and one 409 CONFLICT (not two successes, not two failures).

### Requirement 16: Non-Functional Requirements

#### Acceptance Criteria

1. THE `/journey` page SHALL render initial canvas (manifest + basic layers) within 2 seconds on a modern laptop with a warm cache.
2. Canvas interactions (pan, zoom, node drag) SHALL sustain at least 45 fps on 50 or fewer visible nodes.
3. THE manifest file SHALL be cache-controlled via standard Next.js static asset headers (long-lived cache, busted by content hash of the deployment).
4. THE API endpoints SHALL return JSON in the standard OneStack envelope `{ success: bool, data?, error? }`.
5. THE page SHALL work on screens ≥ 1280 × 720; smaller viewports are out of scope for v1.0.
6. THE UI text SHALL be in Russian to match the rest of OneStack; error codes (`STALE_VERSION`, `FORBIDDEN_FIELD`) remain in English for machine-readable consistency.
7. THE screenshots pipeline SHALL consume no more than 2 GB of Supabase Storage in steady state (retention of 2 images per (role, node) with ~12 roles × ~34 nodes × ~100 KB/image ≈ 82 MB budget, generous ceiling); verification attachments add at most 3 × 2 MB × verifications-per-node averaging 2 ≈ ~800 MB at saturation for 34 nodes.

### Requirement 17: Release Criteria for v1.0

**Objective:** Explicit, verifiable gates before declaring v1.0 shipped.

#### Acceptance Criteria

1. All 34 current Next.js routes (per `frontend/src/app/(app)/**`) SHALL be present as nodes in the manifest; a CI check SHALL verify this count and fail if any route is unmapped.
2. All four Next.js route-convention types (plain path, `[id]` dynamic, `(group)` route group, `[[catchAll]]` or `@parallel`) SHALL be exercised at least once in the production manifest, confirming parser coverage.
3. Admin SHALL be able to create a ghost node and see it appear on the canvas without a page reload.
4. QA SHALL be able to open any node's drawer, view its screenshot with pin overlay, record a verification with an attached screenshot, and observe the QA-status dot update and attachment appear in history.
5. The nightly screenshot action SHALL have completed successfully three consecutive nights.
6. Concurrent edit simulation SHALL demonstrate STALE_VERSION handling end-to-end (UI toast + re-fetch).
7. RLS policy tests SHALL all pass; no role SHALL be able to write outside its tier; `top_manager` is verified read-only.
8. A junior QA team member SHALL complete a review of one screen (view expected behaviour, click verify on each pin, attach a screenshot to at least one "broken" verdict) in under 15 minutes after a 15-minute onboarding session.
9. Internal demo to dev + QA teams SHALL be held and feedback captured before public announcement.
10. `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` §6 matrix SHALL be updated to remove `top_manager` from write rows (amendment tracked in the design-phase review).
11. Error/loading states (Requirement 14) SHALL be manually QA-tested by simulating: manifest 404, API 500, empty DB, pin with no bbox, missing screenshot, expired attachment signed URL.
12. Requirement 18 (Journey Flows) SHALL ship with at least 4 pre-seeded flows covering P1 (sales full cycle), P2 (QA onboarding), procurement, and finance personas, as demonstrated in the Claude Design mockup.

### Requirement 18: Journey Flows (Persona-Guided Walkthroughs)

**Objective:** Beyond the free-form canvas exploration, onboarding-oriented users (P2 QA juniors, P3 end users) need prescribed step-by-step paths through a persona's daily work. Flows are curated sequences of existing nodes + per-step context notes, read from a new small data model and rendered as a dedicated `/journey/flows/:flow_id` view.

#### Acceptance Criteria

1. THE migration SHALL add one table: `kvota.journey_flows` with columns: `id` uuid PK, `slug` text UNIQUE, `title` text, `role` role-slug text, `persona` text (free-form display name and description), `description` text, `est_minutes` int, `steps` jsonb (array of `{node_id, action, note}`), `is_archived` boolean default false, `display_order` int, `created_by` uuid, `created_at` timestamptz, `updated_at` timestamptz.
2. THE RLS policy on `journey_flows` SHALL allow SELECT for all authenticated users; INSERT/UPDATE/DELETE for `admin` only (flows are curriculum content, not user-generated).
3. THE `/journey` page SHALL expose an entry point "Пути" (Flows) in the left sidebar with a count badge; clicking opens a panel listing all non-archived flows grouped by persona role.
4. WHEN a user selects a flow, THE system SHALL navigate to `/journey/flows/:slug`; this view SHALL render the flow in a three-pane layout: left = step list (numbered 1–N, current step highlighted), centre = node focus area (same node card as canvas, larger, with drawer details inline), right = optional annotated screen if step's node has pins.
5. Each step SHALL display its `action` (short imperative verb phrase) and `note` (context sentence) above the node card.
6. Navigation between steps SHALL support keyboard (← →, Esc to exit flow back to canvas) and explicit "Next step" / "Previous step" buttons.
7. The flows view SHALL surface overall flow progress (e.g., "Step 3 / 8") and estimated remaining time.
8. THE seed data migration SHALL create four flows matching the Claude Design mockup personas: `sales-full` (12 min, sales), `procurement-flow` (8 min, procurement), `qa-onboarding` (15 min, spec_controller), `finance-monthly` (6 min, finance).
9. Flow creation and editing UI SHALL be admin-only and is OUT OF SCOPE for v1.0 — admins edit flows directly by running SQL or via Supabase Studio. An in-app editor is a v1.1 item.
10. WHEN a flow references a `node_id` that is not present in the manifest (including ghost nodes), THE step SHALL render with a warning badge "Узел недоступен" and SHALL still show action/note text; user can skip to next step.
11. Flow views SHALL count toward the Requirement 17.8 "15-minute junior QA" release criterion — a Junior QA completing the `qa-onboarding` flow end-to-end within 15 minutes is the acceptance test.

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
