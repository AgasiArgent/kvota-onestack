# Research Log — Customer Journey Map

## Summary

Discovery scope: **Extension (light)**. The feature builds on an established onestack stack (Next.js 15, Supabase Postgres, Python FastAPI, shadcn/ui) and lives inside the existing `(app)` route group. No net-new infrastructure required. The majority of architectural choices were worked through an extended pair-brainstorm session with the product lead (transcript summarised in `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md`). Outstanding research focused on three concrete questions: (1) which canvas library to use, (2) how to anchor pins durably to DOM elements across UI refactors, (3) how to propagate Next.js 15 route conventions into the manifest.

## Research Log

### Topic 1 — Canvas library for node-graph UIs

- **Candidates considered:** `@xyflow/react` (formerly `reactflow`), `d3-force`, `reaflow`, `react-archer`.
- **Decision:** `@xyflow/react` v12. It is the de-facto standard for node-based UIs in React; supports custom nodes, subflows, minimap, and dagre auto-layout out of the box. Its v12 release renamed from `reactflow` and stabilised the API. Approximately 28 k stars on GitHub, active maintenance, MIT license.
- **Sources:** npm listing, its official docs at `reactflow.dev` (redirects to `@xyflow/react`), GitHub release notes.
- **Implication for design:** use React Flow's subflow feature for cluster grouping (native; no custom clipping layer); rely on dagre adapter for initial auto-layout; memoize custom node types to keep pan/zoom smooth at 50+ nodes.

### Topic 2 — Selector-anchored pins (durability across UI refactors)

- **Pattern surveyed:** Pendo, Walnut, Storylane all anchor in-app walkthroughs to CSS selectors or `data-testid` attributes, refreshing positional metadata on their own page-capture pipeline.
- **Decision:** store `(selector, expected_behavior, mode)` as source of truth, compute `(x, y, width, height)` via Playwright `page.locator(selector).boundingBox()` during the nightly run, and cache the result in `journey_pins.last_*` columns. If `selector` fails to resolve, set `selector_broken=true` and surface in an admin list.
- **Trade-off rejected:** hardcoded pixel coordinates — they drift every UI refactor and require manual repositioning.
- **Implication for design:** onestack components must have stable interactive-element selectors; recommend `data-testid` or `data-action` on buttons and form controls. This pays double — the same discipline helps future E2E Playwright tests.

### Topic 3 — Next.js 15 App Router route conventions

- **Scope:** `(group)` route groups, `[slug]` dynamic, `[[catchAll]]` optional catch-all, `@slot` parallel routes, `(.)folder` interceptor routes.
- **Reference:** Next.js App Router routing documentation (routing conventions section, v15 stable).
- **Decision:** `parse-routes.ts` must:
  - Strip parenthesised segments (`(app)`, `(auth)`) from the public path when building `route` but preserve them in `source_files`
  - Preserve bracket notation (`[id]`, `[[catchAll]]`) in the `node_id`
  - Emit one node per `@slot` parallel route
  - Treat interceptor routes as distinct nodes
- **Implication for design:** snapshot tests cover one example of each convention type. Release criterion Req 17.2 requires production manifest exercise at least one example of each type present in the codebase.

### Topic 4 — Concurrency on single-row state (impl/qa)

- **Problem:** two admins simultaneously edit the same node's impl/qa state.
- **Decision:** version column + If-Match semantics at API level. API rejects stale writes with 409 and returns current state for client refresh.
- **Alternative rejected:** row-level lock / advisory lock — overkill for small UI edits, adds latency.
- **Alternative rejected:** last-write-wins — silent data loss; fails UX expectations for an audit-heavy surface.

### Topic 5 — Event-sourced audit vs mutable row history

- **Surfaces:** `journey_verifications` (append-only by design; represents discrete user actions) and `journey_node_state` (single mutable row).
- **Decision:** `journey_verifications` stays append-only (no history table needed; the table IS the history). `journey_node_state` uses a trigger-based history: AFTER UPDATE copies OLD row to `journey_node_state_history`. Read path is lazy via a dedicated endpoint.
- **Implication:** the history table grows ~1 row per status edit — small; no rotation needed within v1.0 horizon.

### Topic 6 — Screenshot attachments storage & security

- **Options:** S3 via Supabase Storage (private + signed URLs) vs CDN with public URLs.
- **Decision:** private bucket `journey-verification-attachments` with 1-hour signed URLs issued to authenticated users. Reduces the blast radius if a URL leaks. Storage policy enforces server-side file-size limit (2 MB per image).
- **Implication:** drawer must request signed URLs on render; caching strategy relies on React Query cache + 1-hour expiry window; expired images gracefully fall back to placeholder.

## Architecture Pattern Evaluation

| Pattern considered | Verdict | Rationale |
|---|---|---|
| Derived state only (no mutable annotations) | Rejected | Cannot represent impl/qa status, ghost nodes, or QA verifications |
| Mutable state only (no derived manifest) | Rejected | Would drift silently from code; canonical "is this route still alive?" impossible |
| Hybrid: derived manifest + mutable annotations keyed by node_id | **Selected** | Best of both; enforces strong immutability boundary |
| Event-sourced everything (also node state) | Rejected | Overkill for a single-row state; current-state reads would need materialised view; add complexity for no v1.0 gain |

## Design Decisions

1. **`node_id` as stable key** (`app:/route` / `ghost:slug`) — bright-line separator between derived and mutable zones.
2. **Parsers at CI build time** (not runtime) — zero runtime cost, git-tracked history of structural changes, serverless-safe.
3. **Supabase direct for single-table CRUD, Python API for aggregates and field-aware ACL** — aligns with `api-first.md`.
4. **Selector-based pins** — survives UI refactors; Playwright refreshes positions; broken selectors flagged explicitly.
5. **Append-only verifications, trigger-based history for state** — two different audit strategies, each fit for purpose.
6. **Orphan annotations manual retarget** — no fuzzy route-path matching; admin reviews explicitly.
7. **Manifest served as static file, not via API** — CDN-cacheable, no Python on the read path for the big payload.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Selector rot breaks pins on refactor | Medium (per release) | Low (self-healing: broken flag + list) | `selector_broken` + admin list; encourage `data-testid` |
| W5 integration burst slips schedule | Medium | Medium (pushes v1.0 1 week) | W6 buffer; Playwright auth dry-run in W4 |
| 32 existing specs lack `related_routes:` | High (current state) | Low-Medium (fuzzy fallback works) | Backfill script + human review; lint warning on new specs without frontmatter |
| React Flow performance at 50+ nodes | Low (we have ~40 real + ~10 ghost) | Medium (laggy canvas) | Viewport culling, memoized nodes; loadtest W2 |
| Storage cost growth | Low | Low (<1 GB) | Retention = 2 images per (role, node); attachment size cap |
| Parser handles wrong Next.js convention silently | Medium | High (missing nodes; no alert) | Snapshot tests on fixture covering all conventions; CI diff-check |
| `top_manager` write slips through early code | Low (tests catch) | Medium (unauthorized edits) | Explicit RLS test + API denial test; design-doc amendment tracked |

## Parallelization Considerations (for `/kiro:spec-tasks`)

- **Highly parallel:** all parser implementations (each a separate file, no shared state).
- **Sequential:** migration 286 must land before any runtime code; manifest generator must produce a valid file before any page code renders.
- **Parallel once migration is in:** frontend entity slice (`entities/journey/**`), frontend feature slices (`features/journey/ui/canvas`, `features/journey/ui/drawer`, etc.), Python API routes, RLS policies are all independent files.
- **Cross-cutting hold:** types in `entities/journey/types.ts` must exist first — every other slice imports from here.
- **Last-mile sequential:** E2E test must wait for W6 polish; nightly GitHub Action can land as early as W5 but needs test users seeded.

## Open Follow-ups

- `docs/superpowers/specs/2026-04-22-customer-journey-map-design.md` needs amendment (tracked in design.md §11).
- Decision on sidebar-nav exact location (which section?) deferred to `widgets/sidebar` implementation sub-task.
- Feature flag / gradual rollout strategy (admin → QA → everyone) — decide at task-planning phase.
