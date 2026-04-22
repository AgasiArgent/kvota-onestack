# Tasks — Customer Journey Map (`/journey`)

**Workflow:** `/lean-tdd` per task (RED → GREEN → Commit).
**Branch:** `feat/customer-journey-map-spec` (spec already landed; implementation commits stack on top).
**Ship rule:** incremental — demoable milestones at W2, W3, W4, W5, v1.0 release at W6. Early PRs acceptable after W2 if team has bandwidth to review.
**Design amendments in progress:** `top_manager` write removal and `related_routes:` backfill are tracked via dedicated tasks below; both back-port into `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` on W6.
**Parallel markers:** `(P)` = safe to run in parallel with other `(P)` tasks at the same depth once their declared dependencies are met. Omit for dependency-bottleneck tasks.

---

## Group A — Week 1 · Foundations

### Task 1 — Database migration: journey tables + helper + trigger

**Goal:** Introduce the 6 Supabase tables that back every mutable annotation, plus the `kvota.user_has_role(slug)` helper function and the node-state history trigger.

**RED:**
- Add `tests/test_migrations.py::test_journey_tables_migration` verifying post-migration state: 6 tables exist in `kvota` schema with expected columns and CHECK constraints; `kvota.user_has_role` function exists and returns bool; trigger `trg_journey_node_state_history` exists; RLS is enabled on all 6 tables; `kvota.feedback.node_id` column and index exist.
- Add `tests/test_migrations.py::test_history_trigger_fires` — insert into journey_node_state, update it, assert a row appears in journey_node_state_history with old values.
- Add `tests/test_migrations.py::test_user_has_role_helper` — SET auth.uid() via test fixture, call helper for known and unknown role slugs.

**GREEN:**
- Create `migrations/<next>_journey_map.sql` with: `journey_node_state`, `journey_node_state_history`, `journey_ghost_nodes`, `journey_pins`, `journey_verifications`, `journey_flows` tables per design.md §3; `ALTER TABLE kvota.feedback ADD COLUMN node_id text` + index; `kvota.user_has_role(slug text) RETURNS boolean` helper (if absent); `kvota.copy_journey_node_state_to_history()` function + `AFTER UPDATE` trigger; RLS enabled on all 6 tables (no policies yet — those are Task 3).
- Apply against staging via `scripts/apply-migrations.sh`.
- Regenerate `frontend/src/shared/types/database.types.ts` via `npm run db:types`.
- Commit generated types.

**Commit:** `feat(journey): migration for 6 annotation tables + helper + trigger`

**Reqs:** 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 11.1, 18.1

---

### Task 2 — Shared TypeScript type contracts

**Goal:** Create the `frontend/src/entities/journey/types.ts` module — single source of truth for Manifest and annotation types across the feature.

**RED:**
- Add `frontend/src/entities/journey/__tests__/types.test-d.ts` with `expectTypeOf` assertions (via `tsd` or `expectTypeOf` helper): `JourneyNodeId` rejects strings not starting with `app:` or `ghost:`; `JourneyPin.last_rel_x` accepts number in 0..1 or null; `JourneyFlow.steps` is readonly.

**GREEN:**
- Write `types.ts` exporting: `RoleSlug`, `JourneyNodeId`, `JourneyStory`, `JourneyNode`, `JourneyEdge`, `JourneyCluster`, `JourneyManifest`, `JourneyNodeState`, `JourneyGhostNode`, `JourneyPin` (with `last_rel_*` fields), `JourneyVerification` (with `attachment_urls`), `JourneyNodeStateHistory`, `JourneyFlow`, `JourneyFlowStep`, plus literal unions `ImplStatus`, `QaStatus`, `GhostStatus`, `PinMode`, `VerifyResult`.
- Re-export Supabase-generated row types with short aliases where useful.

**Commit:** `feat(journey): add shared TypeScript type contracts`

**Reqs:** 1.8, 2.2, 2.3, 2.4, 2.5, 2.6, 4.2, 18.1

---

### Task 3 — RLS policies + `/journey` read grant

**Goal:** Write RLS so authenticated users can SELECT all 6 tables; writes are gated per role matrix.

**Dependency:** Task 1.

**RED:**
- `tests/test_rls_journey.py`: matrix test — for each role `r` × each table `t` × each operation `(SELECT, INSERT, UPDATE, DELETE)`, assert the outcome matches the design matrix (authenticated SELECT always allowed; writes restricted; `top_manager` explicitly denied all writes; `journey_verifications` DELETE denied for everyone; `journey_node_state` direct write denied for everyone — Python API is the only writer).

**GREEN:**
- Append RLS policies to the migration created in Task 1 (or a follow-up migration if Task 1 already applied): policies per design.md §6. Use `kvota.user_has_role(...)` helper.
- Re-apply migration.

**Commit:** `feat(journey): RLS policies for 6 annotation tables`

**Reqs:** 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 12.9

---

### Task 4 — Parser `parse-routes.ts` (P after Task 2)

**Goal:** Walk `frontend/src/app/**` and produce typed routes[] that preserve Next.js 15 route conventions correctly.

**RED:**
- `frontend/scripts/journey/__tests__/parse-routes.test.ts` with fixture dirs under `__tests__/fixtures/routes/`:
  - `(app)/quotes/page.tsx` → route `/quotes`
  - `(app)/quotes/[id]/page.tsx` → route `/quotes/[id]`
  - `(app)/quotes/[id]/cost-analysis/page.tsx` → route `/quotes/[id]/cost-analysis`
  - `(app)/shop/[[...slug]]/page.tsx` → catch-all route
  - `(app)/dashboard/@feed/page.tsx` → parallel route
  - `(app)/(.)modal/page.tsx` → interceptor route
  - `(auth)/login/page.tsx` → skipped (auth group excluded)
- Assert output preserves `[id]`, strips `(group)`, emits separate entries for parallel and interceptor routes, skips `(auth)`.

**GREEN:**
- Implement `parse-routes.ts` with no runtime `any`, using `fs/promises` walk. Title extraction: try `export const metadata.title` → `@journey-title` JSDoc → first `<h1>` text → route basename.
- Build parent-child tree from layout nesting.

**Commit:** `feat(journey): parse-routes.ts with Next.js 15 convention support`

**Reqs:** 1.1, 1.4, 1.5, 1.8, 1.9

---

### Task 5 — Parser `parse-specs.ts` (P after Task 2)

**Goal:** Read `.kiro/specs/**/*.md`, extract user stories, bind them to routes via frontmatter or fuzzy match.

**RED:**
- `frontend/scripts/journey/__tests__/parse-specs.test.ts` with fixtures:
  - Spec with `related_routes: ['/quotes/[id]']` frontmatter → story bound to that route
  - Spec without frontmatter, directory name `phase-5b-quote-composition` → fuzzy match to `/quotes/[id]` route
  - Spec with `As sales, I can ...` heading → extracted story `actor='sales'`, `goal='I can ...'`
  - Spec that doesn't match any route → story goes to "unbound" bucket

**GREEN:**
- Use `gray-matter` for frontmatter; custom regex for story extraction (`/^As (\w[\w_]*),\s*I\s+(.+)$/m`).
- Fuzzy match: take spec directory slug words, match against route path segments (case-insensitive, stemming-free word overlap).
- Emit stories attached to node_ids.

**Commit:** `feat(journey): parse-specs.ts with frontmatter + fuzzy matching`

**Reqs:** 1.1, 1.6

---

### Task 6 — Parser `parse-roles.ts` (P after Task 2)

**Goal:** Build the role × route visibility matrix from `.kiro/steering/access-control.md` tables.

**RED:**
- `parse-roles.test.ts` with a fixture access-control.md containing: visibility-tier table, entity-level rules (Customers / Quotes / Specifications / etc.), edit-permissions table.
- Assert output: for each (role, route-cluster) pair, emit a `visible: boolean`; normalise cluster names to match manifest clusters.

**GREEN:**
- Parse markdown tables with a minimal table parser (avoid pulling `remark` to keep script deps small); map role → tier → visibility per cluster.

**Commit:** `feat(journey): parse-roles.ts extracts role × route matrix`

**Reqs:** 1.1

---

### Task 7 — `build-manifest.ts` orchestrator + CI gate

**Goal:** Stitch the three parsers into `frontend/public/journey-manifest.json`, hook to pre-commit, add CI stale-check.

**Dependency:** Tasks 4, 5, 6.

**RED:**
- `build-manifest.test.ts` — snapshot test: given fixture source tree (3 clusters, 8 routes, 2 specs, 1 access-control.md), assert deterministic JSON output matches stored snapshot. Run 2× in a row, assert byte-identical.
- `test_ci_stale_check.sh` (shell): regenerate manifest, then modify one fixture, regenerate again, assert output changed.

**GREEN:**
- Implement `build-manifest.ts` invoking parsers concurrently, sorting outputs for determinism, writing `frontend/public/journey-manifest.json`.
- Add `npm run journey:build` in `frontend/package.json`.
- Husky pre-commit hook: if any of `frontend/src/app/**`, `.kiro/specs/**`, `.kiro/steering/access-control.md` is staged, run `journey:build` and `git add` the manifest.
- GitHub Action step in existing CI: `npm run journey:build` then `git diff --exit-code frontend/public/journey-manifest.json` — fail if the committed manifest is stale.

**Commit:** `feat(journey): build-manifest orchestrator + pre-commit + CI check`

**Reqs:** 1.1, 1.2, 1.3, 1.10, 1.11, 1.12

---

### Task 8 — One-time `backfill-related-routes.ts` (P after Task 7)

**Goal:** Help existing 32 specs gain `related_routes:` frontmatter via a review-patch workflow.

**RED:**
- `backfill-related-routes.test.ts` with fixture specs containing path-like strings (`/quotes/[id]`, `/customers`) embedded in body. Assert script emits a patch file suggesting `related_routes:` addition with matched paths.

**GREEN:**
- Implement script. Output: `docs/superpowers/backfill-related-routes-<date>.patch` that an admin applies manually with `git apply`.
- Document in script header: "This script does NOT write files; it outputs a review patch."

**Commit:** `chore(journey): one-time backfill-related-routes script`

**Reqs:** 1.7

---

## Group B — Week 2 · Read-only atlas (API + page shell)

### Task 9 — Python API scaffold: router, models, envelope

**Dependency:** Tasks 1, 2.

**Goal:** Create the `api/routes/journey.py` router + Pydantic models + shared JSON envelope.

**RED:**
- `tests/test_api_journey.py::test_router_mounted_under_api_journey` — assert FastAPI app exposes `/api/journey/*` routes.
- `test_envelope_shape` — any endpoint returns `{success, data}` or `{success: false, error}`.

**GREEN:**
- Create `api/models/journey.py` with Pydantic v2 models per design.md §4.4.
- Create `api/routes/journey.py` with router `APIRouter(prefix="/api/journey")`, mount in `api/__init__.py`.
- Reuse existing envelope helper; create one if absent.

**Commit:** `feat(journey-api): scaffold router + models + envelope`

**Reqs:** 16.4

---

### Task 10 — API: `GET /api/journey/nodes` aggregate (P after Task 9)

**Goal:** Return the canvas-level merged view (manifest + state + counts).

**RED:**
- `test_get_nodes_returns_merged_manifest_state_counts` — seed manifest file + state rows + pins + feedback; assert response contains each node's `impl_status`, `qa_status`, `stories_count`, `feedback_count`, `pins_count`.
- `test_get_nodes_feedback_count_respects_rls` — as non-admin user, feedback_count reflects RLS-filtered count.

**GREEN:**
- `services/journey_service.py::get_nodes_aggregated(user_id)` — load manifest, LEFT JOIN state, COUNT subqueries via Supabase with RLS context.
- Wire into `GET /api/journey/nodes`.

**Commit:** `feat(journey-api): GET /nodes returns merged skeleton + state + counts`

**Reqs:** 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 11.2

---

### Task 11 — API: `GET /api/journey/node/{node_id}` detail (P after Task 9)

**Goal:** Full-detail drawer payload.

**RED:**
- `test_get_node_returns_state_pins_training_feedback` — seed a node with state, 3 pins (2 qa, 1 training), 2 feedback rows; assert shape.
- `test_get_node_404_when_unknown_node_id`.

**GREEN:**
- `services/journey_service.py::get_node_detail(node_id, user_id)` — composition of state row + pins + latest verifications per pin + feedback top-3 (RLS-filtered) + node from manifest.
- Wire into `GET /api/journey/node/{node_id}`.

**Commit:** `feat(journey-api): GET /node/{id} returns full detail`

**Reqs:** 5.1

---

### Task 12 — API: `PATCH /api/journey/node/{id}/state` with concurrency

**Dependency:** Tasks 9, 11.

**Goal:** Field-aware state writes with optimistic-concurrency `version` guard.

**RED:**
- `test_patch_state_happy_path_increments_version` — version 1 → submit with version=1 → stored becomes version=2.
- `test_patch_state_stale_version_returns_409_with_current` — version mismatch → 409 `STALE_VERSION` + current-state payload.
- `test_patch_impl_rejected_for_qa_role_with_403_forbidden_field`.
- `test_patch_qa_rejected_for_head_of_sales`.
- `test_patch_mixed_rejects_without_partial_write` — single PATCH trying to write both impl and qa, role lacks permission for one → full rollback.
- `test_top_manager_cannot_patch_state` — even for fields it's "aligned with".

**GREEN:**
- Implement handler with: load row (or create with version=0) → validate `version` match → check caller's roles against field permissions → apply update → return updated row.
- Respond with standard envelope; STALE_VERSION returns 409 but with `success: false` and current state in `data`.

**Commit:** `feat(journey-api): PATCH /node/{id}/state with concurrency + field ACL`

**Reqs:** 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8

---

### Task 13 — API: history + webhook endpoints (P after Task 9)

**Goal:** GET history endpoint + secret-authenticated Playwright webhook.

**RED:**
- `test_get_node_history_returns_reverse_chronological_50`.
- `test_playwright_webhook_without_token_returns_401`.
- `test_playwright_webhook_batch_updates_all_pins_in_transaction`.
- `test_playwright_webhook_selector_broken_flag_set_when_no_bbox`.

**GREEN:**
- `GET /api/journey/node/{id}/history` — read from `journey_node_state_history` reverse chrono, limit 50.
- `POST /api/journey/playwright-webhook` — header `X-Journey-Webhook-Token` compared against env `JOURNEY_WEBHOOK_TOKEN`; body is `PlaywrightWebhookRequest`; single-transaction update loop.

**Commit:** `feat(journey-api): history endpoint + Playwright webhook with token auth`

**Reqs:** 6.9, 10.7, 10.8

---

### Task 14 — FSD entity slice `entities/journey/`

**Dependency:** Task 2.

**Goal:** Create the shared frontend client — TanStack Query hooks + Supabase direct queries + access helpers.

**RED:**
- `entities/journey/__tests__/access.test.ts` — pure-function tests on `canEditImpl(roles)`, `canEditQa(roles)`, `canCreateGhost(roles)`, `canCreatePin(roles)`, `canRecordVerification(roles)` matching the matrix in design.md §6.
- `entities/journey/__tests__/api.test.ts` — mock fetch, assert `useNodes()` hits `/api/journey/nodes` and normalizes envelope.

**GREEN:**
- `entities/journey/access.ts` — helpers.
- `entities/journey/api.ts` — TanStack Query hooks for FastAPI endpoints.
- `entities/journey/queries.ts` — Supabase direct queries for ghost/pins/verifications/training/flows CRUD.
- `entities/journey/mutations.ts` — optimistic update hook with 409 reconciliation.

**Commit:** `feat(journey-fe): entity slice — access helpers + API + queries + mutations`

**Reqs:** 6.1, 7.1, 8.1, 9.1, 12.4, 12.5, 12.6, 12.7, 18.2

---

### Task 15 — `/journey` page shell + URL state (P after Task 14)

**Goal:** Create `frontend/src/app/(app)/journey/page.tsx` with three-pane layout, auth guard inherited from `(app)`, URL-query-param state sync.

**RED:**
- `frontend/e2e/journey-shell.spec.ts` — Playwright: open `/journey` as admin, assert three panes render; reload with `?node=app:/quotes&layers=impl,qa&viewas=sales` → state restored.
- Unit test `use-journey-url-state.test.ts` — hook serialises/deserialises selected node, layers, viewas to/from URL.

**GREEN:**
- `app/(app)/journey/page.tsx` server component — fetch manifest, parse URL params, pass to client component.
- `widgets/sidebar/` — add "Карта путей" entry to `Главное` section, `NEW` badge for 2 weeks post-launch.
- `useJourneyUrlState()` hook in `features/journey/lib/`.

**Commit:** `feat(journey-fe): /journey shell + URL state + sidebar nav`

**Reqs:** 3.1, 3.2, 3.10, 3.11

---

## Group C — Week 3 · Dev+QA working (canvas, layers, status, ghost)

### Task 16 — Canvas with React Flow + dagre auto-layout

**Dependency:** Task 15.

**Goal:** Render the canvas with custom `RouteNode`, `GhostNode`, cluster subflows, dagre initial layout.

**RED:**
- `features/journey/__tests__/journey-canvas.test.tsx` — render with 8 fixture nodes + 2 ghosts → assert DOM shows 10 node wrappers, cluster subflows wrap correctly, edges render.
- Snapshot test on dagre-computed positions for the fixture.

**GREEN:**
- Install `@xyflow/react@^12`, `@dagrejs/dagre@^1`.
- `features/journey/ui/canvas/journey-canvas.tsx`, `route-node.tsx`, `ghost-node.tsx`, `cluster-subflow.tsx`, `auto-layout.ts`.

**Commit:** `feat(journey-fe): canvas with custom nodes + subflows + dagre layout`

**Reqs:** 3.6, 3.7, 3.9, 4.2, 7.3

---

### Task 17 — Sidebar: layer toggles + filters + search (P after Task 15)

**Goal:** Left sidebar with 8 layer toggles (localStorage + URL), View-as-role, impl/qa filters, cluster multi-select, search.

**RED:**
- `features/journey/__tests__/sidebar-layer-toggles.test.tsx` — toggle a layer → localStorage updated, URL query param updated, hidden nodes re-rendered.
- `sidebar-search.test.tsx` — search matches route, title, story text, ghost, pin `expected_behavior` (case-insensitive); non-matches fade but stay on canvas.
- `sidebar-viewas-role.test.tsx` — selecting role filters visible nodes accurately.

**GREEN:**
- `features/journey/ui/sidebar/` — `sidebar.tsx`, `layer-toggles.tsx`, `view-as-role.tsx`, `search.tsx`, `cluster-multiselect.tsx`.
- Persist layer state via `useLocalStorage` keyed by user ID; URL overrides localStorage on page load.

**Commit:** `feat(journey-fe): sidebar — layers + filters + search`

**Reqs:** 3.3, 3.4, 3.5, 4.1, 4.9, 4.10

---

### Task 18 — Drawer: base + all sections (read-only) (P after Task 15)

**Goal:** Render the right drawer with all data sections; editing comes in Task 19.

**RED:**
- `features/journey/__tests__/node-drawer.test.tsx` — click node → drawer slides in; ghost node hides Screenshot and Pin sections; Esc closes.

**GREEN:**
- `features/journey/ui/drawer/node-drawer.tsx` (root with slide-in animation via CSS transitions, no `translateY`), `drawer-header.tsx`, `roles-section.tsx`, `stories-section.tsx`, `status-section.tsx` (read-only for this task), `screenshot-section.tsx`, `feedback-section.tsx`, `training-section.tsx`, `pin-list-section.tsx`, `history-expander.tsx` (lazy-fetch history on expand).

**Commit:** `feat(journey-fe): drawer base + all sections (read-only)`

**Reqs:** 5.1, 5.2, 5.3, 5.4, 5.6, 5.7

---

### Task 19 — Drawer status editing: inline + optimistic + 409

**Dependency:** Tasks 12, 18.

**Goal:** Make status-section interactive with inline editing, optimistic updates, and clean 409 rollback.

**RED:**
- `status-section.test.tsx` — change status → optimistic UI flip → API 200 → stays.
- Mock 409 → toast shown → control reverts to stored value within 300ms.
- Mock 403 → toast "no permission" → rollback.

**GREEN:**
- `status-section.tsx` — inputs wired to `useUpdateNodeState()` mutation from `entities/journey/mutations.ts`.
- 409 handler: show `AppToaster` with "Updated by another user — refreshing", replace local state from `error.data`.

**Commit:** `feat(journey-fe): status inline-edit with optimistic + 409 rollback`

**Reqs:** 5.5, 6.1, 6.2, 6.3

---

### Task 20 — Ghost nodes CRUD (P after Task 17)

**Goal:** Admin can create, edit, delete ghost nodes; canvas renders them with dashed styling and "planned in" meta.

**RED:**
- `ghost-create-dialog.test.tsx` — form submits → `journey_ghost_nodes` INSERT → RLS allows for admin → canvas re-renders with new ghost.
- `ghost-edit-dialog.test.tsx` — open existing ghost → change title → save → UPDATE → canvas reflects.
- `ghost-delete.test.tsx` — delete with confirmation → DELETE → ghost disappears.
- RLS assertion: non-admin role cannot INSERT/UPDATE/DELETE (already covered in Task 3, re-verify here through UI layer).

**GREEN:**
- `features/journey/ui/ghost/ghost-create-dialog.tsx`, `ghost-edit-dialog.tsx`, `ghost-delete-confirm.tsx`.
- Slug generation client-side (validated against UNIQUE constraint; 409 on collision handled gracefully).
- "Mark as shipped" action sets `status='shipped'`.

**Commit:** `feat(journey-fe): ghost nodes CRUD + mark-shipped`

**Reqs:** 7.1, 7.2, 7.3, 7.4, 7.5, 7.6

---

## Group D — Week 4 · Pins + verifications

### Task 21 — Pin creation UI + selector picker

**Dependency:** Tasks 18, 19.

**Goal:** Admin / quote_controller / spec_controller can create QA or training pins by either entering a selector or using a DOM-picker in a preview iframe.

**RED:**
- `pin-creator.test.tsx` — manual mode: type selector, fill expected → INSERT, pin visible in list.
- DOM-picker mode: click a highlighted element in preview → selector auto-filled with `data-testid` if present, else auto-generated stable CSS.
- Training-mode pin requires non-null `training_step_order`; UI blocks submit until set.

**GREEN:**
- `features/journey/ui/pin-overlay/pin-creator.tsx` with both modes.
- `features/journey/lib/selector-from-element.ts` — prefers `data-testid` > `data-action` > aria-label path > short CSS.

**Commit:** `feat(journey-fe): pin creation with DOM picker + training mode guard`

**Reqs:** 8.1, 8.2, 8.5

---

### Task 22 — Pin overlay on screenshots + broken-selector flagging

**Dependency:** Task 21.

**Goal:** Render pins on a screenshot using relative `last_rel_*` coordinates; visually flag broken selectors.

**RED:**
- `annotated-screen.test.tsx` — screenshot with 4 pins at various rel positions → assert DOM placement matches `rel * container_size`.
- Pin with `selector_broken=true` → red border + "needs update" label.
- Pin with `last_rel_x IS NULL` → absent from overlay, present in pin list with "Position pending".

**GREEN:**
- `features/journey/ui/pin-overlay/annotated-screen.tsx`, `pin-badge.tsx`, `pin-popover.tsx`.
- Resize observer recomputes absolute positions on container resize.

**Commit:** `feat(journey-fe): pin overlay with relative coords + broken flagging`

**Reqs:** 8.3, 8.4, 8.6, 8.7, 14.4

---

### Task 23 — QA verify buttons + event log

**Dependency:** Task 22.

**Goal:** User clicks ✓/✗/skip on a pin → INSERT to `journey_verifications` → node's QA dot updates.

**RED:**
- `verify-buttons.test.tsx` — click ✓ → INSERT verification → dot turns green.
- Click ✗ with note → INSERT with note → dot turns red.
- Append-only: UPDATE attempts on verifications rejected by RLS (covered in Task 3 matrix; re-assert via UI).
- Training-mode pins show no verify buttons.

**GREEN:**
- `features/journey/ui/pin-overlay/verify-buttons.tsx`.
- Dot color derived from latest verification per pin in `GET /node/{id}`.

**Commit:** `feat(journey-fe): QA verify buttons + append-only event log`

**Reqs:** 9.1, 9.2, 9.3, 9.4

---

### Task 24 — Verification screenshot attachments

**Dependency:** Task 23.

**Goal:** User attaches up to 3 screenshots to a "broken" verification; stored in private Supabase Storage bucket with signed-URL read access.

**RED:**
- `verify-attachments.test.tsx`: upload 4 files → UI rejects 4th; upload non-image → UI rejects; oversized (>2 MB) → rejected; 3 valid images → all uploaded, INSERT with `attachment_urls` containing 3 storage keys.
- Partial-failure cleanup: mock one upload failure → already-uploaded files deleted, INSERT aborted.
- History expander shows thumbnails via signed URL; expired URL shows broken-image icon without crashing row.

**GREEN:**
- Create Supabase Storage bucket `journey-verification-attachments` with private read/write policies + MIME + size constraints (storage policy SQL).
- `features/journey/lib/attachment-upload.ts` — validate → upload → on any failure, delete all uploaded objects.
- `features/journey/ui/pin-overlay/verify-buttons.tsx` — wire attachment picker.
- `features/journey/lib/signed-url.ts` — fetch signed URL with 1-hour TTL for drawer rendering.

**Commit:** `feat(journey-fe): verification screenshot attachments + signed URLs`

**Reqs:** 9.5, 9.6, 9.7, 9.8, 14.6

---

## Group E — Week 5 · Screens, training, flows

### Task 25 — Playwright GitHub Action — structure + test-user seeding

**Goal:** Nightly workflow skeleton and reliable per-role login.

**RED:**
- `tests/integration/test_journey_test_users_seeded.py` — SQL assertion: 12 (or current active role count) `qa-{slug}@kvotaflow.ru` users exist in `auth.users` with the corresponding `user_roles` row.
- Dry-run CI job on PR — runs the capture script against staging with `--dry-run=1` flag (skips Storage upload and webhook POST); passes if no errors.

**GREEN:**
- Write `scripts/seed-journey-test-users.sql` — idempotent seed, uses `JOURNEY_TEST_USERS_PASSWORD` GH secret.
- Create `.github/workflows/journey-screenshots.yml` with schedule `0 3 * * *` + `workflow_dispatch` + `pull_request` (dry-run).
- Placeholder `frontend/scripts/journey/capture-screenshots.ts` with `--dry-run` support.

**Commit:** `feat(journey-ops): Playwright action skeleton + test-user seed`

**Reqs:** 10.1, 10.3, 10.4

---

### Task 26 — Screenshot capture + bbox resolution + webhook POST

**Dependency:** Task 25, Task 13.

**Goal:** Loop over role × node, capture PNG, resolve pin selectors, post batch to webhook.

**RED:**
- `capture-screenshots.test.ts` — fake manifest + fake pins → capture script produces N × M screenshots, M × K bboxes, one webhook POST with the expected payload shape.

**GREEN:**
- Implement the loop. Log in via Supabase `signInWithPassword`. Upload to bucket `journey-screenshots/{role}/{node_id_safe}/{YYYY-MM-DD}.png`. Compute `rel_*` via `locator.boundingBox() / viewportSize()`. POST with `X-Journey-Webhook-Token`.
- Retention: delete files older than the 2 most recent per `(role, node)`.

**Commit:** `feat(journey-ops): nightly capture + bbox resolution + webhook integration`

**Reqs:** 10.2, 10.5, 10.6, 10.8, 10.9

---

### Task 27 — Training layer UI + editor

**Dependency:** Task 18.

**Goal:** Drawer renders training pins as ordered markdown blocks; admin / head_of_* edit steps via a dedicated UI.

**RED:**
- `training-section.test.tsx` — steps render in `training_step_order` as markdown; collapsed by default; expand shows all.
- `training-editor.test.tsx` — admin creates step → INSERT `journey_pins` with `mode='training'` + `training_step_order`. Reorder via drag → UPDATE ordering in a transaction.

**GREEN:**
- `features/journey/ui/drawer/training-section.tsx` with `react-markdown`.
- `features/journey/ui/drawer/training-editor.tsx` for admin.
- Drag-and-drop reorder using `@dnd-kit/core` (lightweight).

**Commit:** `feat(journey-fe): training layer — view + admin editor`

**Reqs:** 5.4, 8.2, 12.10

---

### Task 28 — Journey Flows — seed data + list view

**Dependency:** Task 1 (journey_flows table exists), Task 17.

**Goal:** 4 seed flows live in DB; sidebar "Пути" panel lists them.

**RED:**
- `tests/integration/test_journey_flows_seed.py` — assert 4 flows exist post-seed with expected slugs.
- `flow-list.test.tsx` — "Пути" panel opens → shows 4 flows grouped by role, persona subtitle, est-minutes badge.

**GREEN:**
- `scripts/seed-journey-flows.sql` — inserts the 4 flows from `docs/superpowers/mockups/journey/flows.js` (transliterate JS data into SQL INSERTs with the step JSON literal).
- `features/journey/ui/flows/flow-list.tsx` in sidebar.

**Commit:** `feat(journey-fe): flows seed + sidebar list`

**Reqs:** 18.1, 18.2, 18.3, 18.8

---

### Task 29 — Journey Flows — runner view (P after Task 28)

**Goal:** `/journey/flows/[slug]/page.tsx` renders the three-pane flow runner with keyboard nav.

**RED:**
- `e2e/journey-flow.spec.ts` — open `qa-onboarding` → step counter shows "1 / 5" → press `→` → advances → reach final → Esc returns to canvas with last node pre-selected.
- `flow-step-missing-node.test.tsx` — flow references a ghost node not in current manifest → step renders with "Узел недоступен" badge, skippable.

**GREEN:**
- `app/(app)/journey/flows/[slug]/page.tsx` fetches flow.
- `features/journey/ui/flows/` — `flow-view.tsx`, `flow-step-list.tsx`, `flow-focus-node.tsx`, `flow-navigation.tsx`.

**Commit:** `feat(journey-fe): flow runner view with keyboard nav`

**Reqs:** 18.3, 18.4, 18.5, 18.6, 18.7, 18.9, 18.10, 18.11

---

### Task 30 — Feedback integration (P after Task 1)

**Goal:** `kvota.feedback.node_id` populated for existing rows; new feedback created from `/journey` context carries node_id.

**RED:**
- `tests/integration/test_feedback_node_id_backfill.py` — after backfill migration, rows with known URL mapping have node_id filled; rows with unknown URL stay NULL.
- `feedback-from-journey.test.tsx` — "Report issue" click in drawer → opens feedback creation with `?node_id=<id>` prefilled.

**GREEN:**
- Write backfill migration (part of Task 1 migration or a follow-up) that maps existing `page_url` to manifest routes.
- Update `/admin/feedback` query to honour `?node_id=<id>` filter (no UI changes otherwise).
- Wire drawer "Report issue" button.

**Commit:** `feat(journey-fe): feedback node_id backfill + drawer integration`

**Reqs:** 11.1, 11.2, 11.3, 11.4

---

## Group F — Week 6 · Polish, robustness, release

### Task 31 — Error & loading states

**Dependency:** Tasks 15, 16, 18, 22.

**Goal:** Dedicated components for every failure mode listed in Req 14.

**RED:**
- `manifest-error.test.tsx` — mock fetch failure → component renders with retry button; click retry → refetch.
- `api-error.test.tsx` — `useNodes()` returns persistent error after 3 retries → stale data kept + toast shown.
- `empty-db.test.tsx` — no state rows → every node rendered with grey unset dot, no error.
- `no-screenshot.test.tsx` — drawer screenshot section handles 404 → placeholder + "Request capture" (admin only) triggers `workflow_dispatch`.

**GREEN:**
- `features/journey/ui/empty-states/` — all 4 components.
- TanStack Query config: 3 retries with exponential backoff.
- "Request capture" button calls GitHub Actions API with `workflow_dispatch` + `inputs.route_filter=<node_id>` (admin uses a PAT stored server-side; endpoint is `POST /api/journey/request-capture` — tiny Python handler).

**Commit:** `feat(journey-fe): error and loading states — all failure modes`

**Reqs:** 14.1, 14.2, 14.3, 14.5, 14.7, 14.8

---

### Task 32 — Diff-view on screenshots

**Dependency:** Task 26.

**Goal:** Drawer shows a diff between two most recent screenshots per `(role, node)`.

**RED:**
- `diff-view.test.tsx` — two fixture PNGs → `pixelmatch` runs → `data-testid="diff-mask"` rendered with N red pixels matching fixture.
- `diff-view-empty.test.tsx` — only one screenshot exists → diff control disabled with tooltip.

**GREEN:**
- Install `pixelmatch` + `pngjs`.
- `features/journey/ui/drawer/screenshot-section.tsx` — diff toggle; load two URLs; lazy pixelmatch on demand.

**Commit:** `feat(journey-fe): diff-view with pixelmatch`

**Reqs:** (extends Req 5.1, 17.11)

---

### Task 33 — Orphan annotations panel + retarget

**Dependency:** Task 7 (manifest build), Task 14 (entity slice).

**Goal:** Detect orphan annotations when manifest changes; admin can retarget them to another node.

**RED:**
- `orphans-panel.test.tsx` — fixture where previous manifest had `app:/quotes/old` + 3 annotations, current manifest lacks it → panel shows count 3; click "Retarget to app:/quotes/new" → single transaction updates all 3 refs + feedback.node_id.
- Visibility: non-admin user sees no panel.

**GREEN:**
- Manifest build step writes a diff file `frontend/public/journey-orphans.json` listing missing node_ids + affected annotation counts.
- `features/journey/ui/orphans/orphans-panel.tsx` (admin only).
- `POST /api/journey/retarget` — Python endpoint wrapping a transaction.

**Commit:** `feat(journey): orphan annotations panel + retarget action`

**Reqs:** 13.1, 13.2, 13.3, 13.4, 13.5, 13.6

---

### Task 34 — E2E smoke + concurrency test

**Goal:** Single Playwright spec exercising the critical user path end-to-end; dedicated concurrency test.

**RED:** (tests ARE the deliverable here)

**GREEN:**
- `tests/e2e/journey.spec.ts` — admin user: open `/journey` → toggle Impl layer → click node → open drawer → mark QA verify with attached screenshot → create ghost → assert canvas reflects → open flow `qa-onboarding` → traverse all 5 steps → exit.
- `tests/test_concurrency.py` — spawn 2 async PATCH requests with same version → assert exactly one 200 + one 409 with STALE_VERSION.
- Ensure these run on every PR.

**Commit:** `test(journey): E2E smoke + concurrency guard test`

**Reqs:** 15.3, 15.6

---

### Task 35 — Performance + non-functional gates

**Goal:** Validate the non-functional requirements hold up under realistic load.

**RED:**
- `tests/perf/journey-load.spec.ts` — inject a 50-node manifest → page loads in < 2s on CI runner (cold).
- `tests/perf/canvas-fps.spec.ts` — pan/zoom with 50 nodes → average fps ≥ 45 over 2s.
- `tests/perf/storage-budget.py` — after a week of screenshots + 10 verifications per node, assert bucket size < 1 GB.

**GREEN:**
- Add `cache-control: public, max-age=31536000, immutable` for `public/journey-manifest.json` via Next.js config.
- Canvas uses `React.memo` + `useMemo` on node / edge arrays.
- Retention job tuned to 2 snapshots per `(role, node)`.

**Commit:** `perf(journey): hit 2s initial load + 45fps canvas budget`

**Reqs:** 16.1, 16.2, 16.3, 16.5, 16.7

---

### Task 36 — Release readiness + design-doc amendments

**Goal:** Ship v1.0 cleanly — checklist items, junior-QA onboarding validation, superpowers-doc back-port.

**RED:**
- `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` is updated with all 9 amendments listed in `design.md §11` (removed `top_manager` writes; added `version`; added `journey_node_state_history`; added `attachment_urls`; clarified Next.js route parsing; title fallback chain; URL deep-link; search semantics; error/loading states section).
- Junior QA onboarding dry-run: a junior QA team member completes the `qa-onboarding` flow within 15 minutes; timer recorded.

**GREEN:**
- Amend the superpowers doc.
- Run internal demo. Capture feedback, open ClickUp tasks for post-v1.0 items.
- Tag release `v1.0-journey`.
- Update sidebar badge from `NEW` → (remove) 2 weeks after release.

**Commit:** `docs(journey): back-port v1.0 amendments + release notes`

**Reqs:** 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8, 17.9, 17.10, 17.11, 17.12

---

## Coverage matrix (sanity check)

Each requirement maps to at least one task; refer to per-task `Reqs:` lines for the full traceability. Summary rows:

- **Req 1** (manifest) — Tasks 4, 5, 6, 7, 8
- **Req 2** (data model) — Task 1
- **Req 3** (page/layout/URL) — Tasks 15, 16, 17
- **Req 4** (layers) — Tasks 16, 17, 18
- **Req 5** (drawer) — Tasks 18, 19, 27, 32
- **Req 6** (state editing) — Tasks 12, 19
- **Req 7** (ghost) — Task 20
- **Req 8** (pins) — Tasks 21, 22
- **Req 9** (verifications) — Tasks 23, 24
- **Req 10** (screenshots pipeline) — Tasks 25, 26
- **Req 11** (feedback) — Task 30
- **Req 12** (ACL + RLS) — Tasks 3, 14, 19
- **Req 13** (orphans) — Task 33
- **Req 14** (error states) — Tasks 22, 24, 31
- **Req 15** (testing) — Distributed — tests in each task; E2E + concurrency in Task 34
- **Req 16** (non-functional) — Task 35
- **Req 17** (release) — Task 36
- **Req 18** (flows) — Tasks 1, 28, 29

## Parallel-execution notes

- **Fully independent after Task 1–2 land:** Tasks 4, 5, 6, 8 (parsers), Task 3 (RLS).
- **Fully independent after Task 9:** Tasks 10, 11, 13 (three API endpoints).
- **Fully independent after Task 14 + 15:** Tasks 16, 17, 18, 20, 30.
- **Sequential choke points:** Task 1 → Task 3; Task 7 → (anyone using manifest); Task 12 → Task 19; Task 22 → Task 23 → Task 24; Task 26 → Task 32.
- **Week-level grouping** is a guideline, not a hard schedule — if parallel capacity allows, W3 tasks can start in W2 once their prerequisites land.

---

## Next Step

Before starting implementation:

1. Review this `tasks.md` and either approve (run `/kiro:spec-impl customer-journey-map 1`) or return with edits.
2. Clear conversation context between major tasks for a clean implementation run.
3. `/lean-tdd` is the preferred workflow — each task here is already structured RED → GREEN → Commit and maps 1:1 to a lean-tdd iteration.

Recommended execution order:
```
/kiro:spec-impl customer-journey-map 1       # DB migration
/kiro:spec-impl customer-journey-map 2       # types
/kiro:spec-impl customer-journey-map 3       # RLS (after 1)
# Week 1 parallel after 2:
/kiro:spec-impl customer-journey-map 4,5,6,8 # parsers + backfill script
/kiro:spec-impl customer-journey-map 7       # orchestrator (after 4,5,6)
# Or via lean-tdd:
/lean-tdd                                    # pick up task 1 from tasks.md
```
