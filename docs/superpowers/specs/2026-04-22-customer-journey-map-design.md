# Customer Journey Map — `/journey` — Design

**Date:** 2026-04-22
**Status:** Draft (awaiting user review)
**Scope:** New `/journey` subpage inside onestack. Interactive map of all screens, roles, user stories, with annotation layers for QA and training. Ghost nodes for gap analysis. Screenshots pipeline. Target v1.0 in ~6 weeks.

---

## 1. Problem & Goals

### Problem
- Gaps in ТЗ and incomplete flows only surface during development — no centralized picture of "what exists × who sees it × what it's supposed to do"
- Junior QA lack concrete "expected behavior" annotations when testing screens
- No reusable artefact for onboarding end users or demoing system state
- `.kiro/specs` and `frontend/src/app/` each hold partial truth; neither shows the joined picture

### Goals
- Single navigable atlas showing every screen, its role visibility, attached stories, implementation/QA status
- Visual gap-analysis via "ghost nodes" (proposed screens not yet in code)
- Screen-level interactive annotations: pins explaining expected behaviour (QA mode) or step-by-step instructions (training mode)
- Living documentation that regenerates from code — never drifts

### Audiences (priority order)
1. **Development team** — see what exists, find ТЗ gaps, understand where features fit
2. **QA team** (esp. juniors) — structured expected-behaviour annotations, verify loop, coverage status
3. **End-user training** — pin-based walkthroughs on real screens
4. **Customer/stakeholder demos** — outside v1.0 scope (Miro export deferred; maybe v1.1)

### Non-Goals (explicit out-of-scope for v1.0)
- Miro/FigJam export — deferred indefinitely
- Session recording / replay — potential v2.0
- Live iframe with DOM overlay — potential v1.1
- Customer-facing public journey view

---

## 2. Architecture

### Two zones, one connector
```
IMMUTABLE (from code, CI)                 MUTABLE (user input, Supabase)
┌──────────────────────────┐              ┌──────────────────────────────┐
│ journey-manifest.json    │   node_id    │ journey_node_state           │
│  ├─ nodes[]              │ ◄──────────► │ journey_ghost_nodes          │
│  ├─ edges[]              │              │ journey_pins                 │
│  └─ clusters[]           │              │ journey_verifications        │
└──────────────────────────┘              └──────────────────────────────┘
          ▲                                         ▲
          │ parsers                                 │ RLS + API
          │                                         │
   ┌──────┴──────┐                           ┌──────┴──────┐
   │ app/**      │                           │ Next.js UI  │
   │ .kiro/specs/│                           │ /journey    │
   │ access-ctl  │                           └─────────────┘
   └─────────────┘
```

### Key decisions
- **Parsers run at build-time** (CI + pre-commit hook), output `journey-manifest.json` committed to git. No runtime parsing, no filesystem access at request time.
- **`node_id` = stable route signature** (e.g., `app:/quotes/[id]` or `ghost:revision-history`). Used as join key across manifest and all 4 annotation tables.
- **Manifest canonical location** — `frontend/public/journey-manifest.json` (committed). Next.js serves it as static `/journey-manifest.json`; FastAPI reads the same file at startup for its aggregation endpoints. One source, two consumers.
- **Annotations are append/merge-safe** — `journey_verifications` is append-only (event-sourcing flavour); other tables are small and key'd by `node_id`.

---

## 3. Data Model

### 3.1 Manifest schema

`frontend/public/journey-manifest.json` (committed, served as static):
```jsonc
{
  "version": 1,
  "generated_at": "ISO8601",
  "commit": "git sha",
  "nodes": [
    {
      "node_id": "app:/quotes/[id]",     // stable key
      "route": "/quotes/[id]",
      "title": "Карточка предложения",   // from <h1>, metadata.title, or @journey-title comment
      "cluster": "quotes",               // first path segment
      "source_files": ["frontend/src/app/(app)/quotes/[id]/page.tsx"],
      "roles": ["sales", "procurement", "admin"],  // from access-control.md × middleware
      "stories": [
        { "ref": "phase-5b#3", "actor": "sales", "goal": "I can see full breakdown",
          "spec_file": ".kiro/specs/phase-5b-quote-composition/stories.md" }
      ],
      "parent_node_id": "app:/quotes",
      "children": ["app:/quotes/[id]/cost-analysis"]
    }
  ],
  "edges": [{"from": "app:/quotes", "to": "app:/quotes/[id]", "kind": "drill"}],
  "clusters": [{"id": "quotes", "label": "Quotes", "colour": "#8fa7ff"}]
}
```

### 3.2 Database tables (migration 284)

All tables in `kvota` schema. RLS enabled.

```sql
-- Status overlay (one row per real route)
CREATE TABLE kvota.journey_node_state (
  node_id text PRIMARY KEY,
  impl_status text CHECK (impl_status IN ('done','partial','missing')),
  qa_status   text CHECK (qa_status   IN ('verified','broken','untested')),
  notes text,
  last_tested_at timestamptz,
  updated_at timestamptz DEFAULT now(),
  updated_by uuid REFERENCES auth.users(id)
);

-- Proposed routes not yet in code
CREATE TABLE kvota.journey_ghost_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id text UNIQUE NOT NULL,          -- 'ghost:<slug>'
  proposed_route text,
  title text NOT NULL,
  planned_in text,                       -- spec/phase reference
  assignee uuid REFERENCES auth.users(id),
  parent_node_id text,                   -- for layout positioning
  cluster text,
  status text CHECK (status IN ('proposed','approved','in_progress','shipped')) DEFAULT 'proposed',
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz DEFAULT now()
);

-- Dual-use pins: QA-expected or Training-step
CREATE TABLE kvota.journey_pins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  node_id text NOT NULL,                 -- real or ghost node
  selector text NOT NULL,                -- stable CSS/data-testid
  expected_behavior text NOT NULL,
  mode text NOT NULL CHECK (mode IN ('qa','training')),
  training_step_order int,               -- NULL when mode='qa'
  linked_story_ref text,
  -- Position cache (refreshed by Playwright):
  last_x int, last_y int, last_width int, last_height int,
  last_position_update timestamptz,
  selector_broken boolean DEFAULT false,
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz DEFAULT now()
);

-- Append-only QA events (event sourcing)
CREATE TABLE kvota.journey_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pin_id uuid REFERENCES kvota.journey_pins(id) ON DELETE CASCADE,
  node_id text NOT NULL,                 -- denormalized for read
  result text NOT NULL CHECK (result IN ('verified','broken','skip')),
  note text,
  tested_by uuid REFERENCES auth.users(id),
  tested_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_journey_pins_node_id ON kvota.journey_pins(node_id);
CREATE INDEX idx_journey_ghost_nodes_status ON kvota.journey_ghost_nodes(status);
CREATE INDEX idx_journey_verifications_node_id ON kvota.journey_verifications(node_id);

-- Feedback integration
ALTER TABLE kvota.user_feedback ADD COLUMN IF NOT EXISTS node_id text;
CREATE INDEX idx_user_feedback_node_id ON kvota.user_feedback(node_id);
```

### 3.3 Frontend type generation
After migration applies, run `cd frontend && npm run db:types` to regenerate `database.types.ts`.

---

## 4. Parsers

Location: `frontend/scripts/journey/`

| File | Reads | Produces |
|---|---|---|
| `parse-routes.ts` | `src/app/**/page.tsx`, `layout.tsx` | routes[], parent-child tree from layout nesting |
| `parse-specs.ts` | `.kiro/specs/**/*.md` with frontmatter | stories[], spec-to-route binding |
| `parse-roles.ts` | `.kiro/steering/access-control.md` | role × route matrix |
| `build-manifest.ts` | output of all three | final `journey-manifest.json` |

### Conventions
- **Spec frontmatter `related_routes:`** — new convention for `.kiro/specs/*/*.md` to explicitly bind stories to routes. Parser also falls back to fuzzy match by spec directory name.
- **Title extraction** — first `<h1>` in page, else `metadata.title`, else `@journey-title` JSDoc comment, else route basename.

### Triggers
- **Pre-commit hook** (husky) — regenerate when `src/app/**`, `.kiro/specs/**`, `access-control.md` change
- **CI check** — fails if committed manifest doesn't match a fresh regeneration (`diff` check, no auto-apply)

### Orphan annotations strategy
On each parser run, diff current manifest against `git show HEAD:frontend/generated/journey-manifest.json`. If a `node_id` vanished, annotations remain in DB but UI surfaces them under "Orphaned annotations" with explicit "Retarget to..." action. No automatic route-matching.

---

## 5. API

### Python FastAPI (aggregations, business logic, field-aware ACL)
Per `api-first.md`: complex reads, side-effectful ops, and rules that RLS can't express cleanly go through Python endpoints.

```
GET   /api/journey/nodes                     # manifest ∪ state ∪ counts (merged) for canvas
GET   /api/journey/node/{node_id}            # full detail: state, pins, training, feedback_count
PATCH /api/journey/node/{node_id}/state      # inline status edit — field-aware ACL (impl vs qa)
POST  /api/journey/playwright-webhook        # batch bbox updates after nightly run
                                             # Auth: shared-secret header JOURNEY_WEBHOOK_TOKEN
```

### Supabase direct (single-table RLS-guarded CRUD)
Per `api-first.md`: simple CRUD where RLS is sufficient.

```
POST   kvota.journey_ghost_nodes             # create ghost
PATCH  kvota.journey_ghost_nodes             # edit ghost
DELETE kvota.journey_ghost_nodes             # remove ghost
POST   kvota.journey_pins                    # create pin
PATCH  kvota.journey_pins                    # edit pin
DELETE kvota.journey_pins                    # remove pin
POST   kvota.journey_verifications           # append-only verify event
```

Status updates routed through Python because their ACL is field-aware (`impl_status` writable by managers, `qa_status` by QA roles) — cleaner as API logic than as per-column RLS policies.

### Endpoint docstrings
Every `/api/journey/*` handler follows the standard format from `api-first.md`:
```python
"""Short description.

Path: METHOD /api/journey/...
Params: ...
Returns: ...
Side Effects: ...
Roles: ...
"""
```

---

## 6. Access Control

### RLS policies (coarse-grained at DB level)
Use helper function `kvota.user_has_role(slug text) RETURNS boolean` (create if absent).

| Operation | Permitted role slugs |
|---|---|
| `SELECT` on all journey tables | authenticated users |
| `UPDATE journey_node_state` via API | `admin`, `top_manager`, `head_of_sales`, `head_of_procurement`, `head_of_logistics`, `quote_controller`, `spec_controller` |
| `INSERT/UPDATE/DELETE journey_ghost_nodes` | `admin`, `top_manager` |
| `INSERT/UPDATE/DELETE journey_pins` | `admin`, `quote_controller`, `spec_controller` |
| `INSERT journey_verifications` | `admin`, `quote_controller`, `spec_controller` |

`journey_node_state` is not writable via Supabase direct — RLS denies UPDATE/INSERT for all roles. Writes only through `/api/journey/node/{node_id}/state`, which enforces field-level ACL.

### Field-level ACL in API
- `impl_status` writable by: `admin`, `top_manager`, `head_of_*`
- `qa_status` writable by: `admin`, `quote_controller`, `spec_controller`

API returns `403 {"code": "FORBIDDEN_FIELD", "message": "Role X cannot write field Y"}` on violation.

### Feedback visibility
Reuses existing RLS on `kvota.user_feedback`. Counter on node honours requester's visibility — some users see fewer.

---

## 7. UI (`/journey` page)

### Layout — three panes
- **Left sidebar (220 px)** — Layer toggles (8 layers), Role filter, Impl/QA filter, Search, Cluster multi-select
- **Main canvas (flex)** — React Flow with cluster-subflows, grouped by path segment
- **Right drawer (360 px)** — full node detail, slides in on node click, does not overlap canvas

### Layer system (8 toggleable)
1. **Roles** — chips with role slugs
2. **Stories** — count badge `📝 N`
3. **Impl status** — coloured dot (green/yellow/red)
4. **QA status** — coloured dot + progress `N/M verified`
5. **Feedback** — count badge `💬 N`
6. **Training** — count badge `📖 N steps`
7. **Ghost nodes** — dashed border nodes
8. **Screenshots** — thumbnail in node (compact) or drawer (full)

Layers combine additively. Overloaded nodes push details to drawer.

### Node anatomy (in canvas)
- Minimum: `route · title · roles-chips · stories-count`
- With all layers: + coloured dots + feedback count + training count + thumbnail

### Drawer sections
1. Route + title
2. Roles
3. Stories (list with spec refs)
4. Status (impl + qa, inline-edit for permitted roles)
5. Screenshot (latest nightly) + diff toggle
6. Feedback list (top 3 + "view all" link)
7. Training steps (collapsed, expand on click)
8. Pin list — for QA mode, shows pin number + selector + expected + verify buttons

### Annotated-screens subsystem
- On screenshot, pins rendered as numbered `🟠` badges at `{last_x, last_y}`
- Click pin → popover card: selector, expected, linked story, verify buttons
- Pin creation mode: admin/QA clicks on screenshot → prompts for selector (autocomplete from DOM) → prompts for expected → saves
- Broken pins (selector no longer resolves) rendered with red border + "needs update" label

### React Flow configuration
- Custom node types: `RouteNode`, `GhostNode`
- Subflows for cluster grouping (native React Flow API)
- Minimap + controls for large maps (34+ nodes)
- Layout: `dagre` auto-layout initially, then manual positions saved to `journey_ghost_nodes.parent_node_id` (for ghosts) or hard-coded cluster positions

---

## 8. Screenshots Pipeline

### GitHub Action
File: `.github/workflows/journey-screenshots.yml`
Cron: nightly 03:00 UTC. Also `workflow_dispatch` for manual trigger.

### Capture script (`frontend/scripts/journey/capture-screenshots.ts`)
```
1. npm run journey:build  → fresh manifest
2. docker compose -f docker-compose.ci.yml up -d (staging DB)
3. For each role R in manifest.roles:
     login as qa-${R}@kvotaflow.ru (password from JOURNEY_TEST_USERS secret)
     For each node in manifest.nodes where R ∈ node.roles:
         await page.goto(baseUrl + route)
         await page.screenshot({ path: ... })
         upload to Supabase Storage: journey-screenshots/{R}/{node_id}/{YYYY-MM-DD}.png
         For each pin in GET /api/journey/node/{node_id}:
             try: bbox = await page.locator(pin.selector).boundingBox()
             if bbox: batch += { pin_id, x, y, width, height, selector_broken: false }
             else: batch += { pin_id, selector_broken: true }
     POST /api/journey/playwright-webhook with batch
         (header: X-Journey-Webhook-Token: ${{ secrets.JOURNEY_WEBHOOK_TOKEN }})
```

### Test users
Need 12 accounts (one per role) in Supabase auth + user_roles:
- Email pattern: `qa-{role_slug}@kvotaflow.ru`
- Password: stored in GitHub secret `JOURNEY_TEST_USERS_PASSWORD` (one shared, simple rotation)
- Seeded via SQL during environment setup

### Diff-view
On drawer open, client-side `pixelmatch` or `@img-comparison-slider` between two most recent screenshots per `(role, node_id)`. Heavy diff done lazily.

---

## 9. Testing Strategy

### Unit (Vitest, TS)
Location: `frontend/scripts/journey/__tests__/`
- `parse-routes.test.ts` — fixture tree with `[id]`, `(group)`, nested layouts
- `parse-specs.test.ts` — frontmatter with and without `related_routes:`
- `parse-roles.test.ts` — various access-control.md patterns
- `build-manifest.test.ts` — snapshot test on full fixture

### Integration (pytest)
Location: `tests/test_api_journey.py`
- `test_get_nodes_merges_state_and_counts` — aggregated response shape
- `test_get_node_returns_pins_and_training` — full detail
- `test_playwright_webhook_updates_bbox` — batch bbox update
- `test_playwright_webhook_marks_selector_broken` — broken selector flag
- `test_patch_impl_rejected_for_qa_role` — 403 on field-level ACL
- `test_feedback_node_id_populated_from_page_url` — mapping layer

### E2E (Playwright, smoke)
Location: `tests/e2e/journey.spec.ts`
- Open /journey as admin → canvas renders
- Toggle layers → nodes visibly change
- Click node → drawer slides in
- Mark QA verified → counter increments
- Create ghost via CRUD → appears on canvas

---

## 10. Rollout (6 weeks)

| Week | Milestone | Deliverables |
|---|---|---|
| **W1** Foundations | Manifest in repo | Migration 284, parsers × 3, `build-manifest.ts`, unit tests, pre-commit hook |
| **W2** Read-only atlas | Showable to team | FastAPI `/nodes` + `/node/:id`, React Flow canvas, Roles + Stories layers |
| **W3** Dev + QA working | QA can start | Impl/QA inline edit, layer toggles, filters, search, ghost CRUD, feedback count |
| **W4** Pins (no screens) | Pins functional | `pins` + `verifications` tables, pin-create UI, QA verify buttons, mock overlay |
| **W5** Screens + training | Picture assembled (RISK) | GH Action nightly, Supabase Storage, real bbox overlay, Training layer UI |
| **W6** Polish + onboarding | v1.0 release | Diff-view, RLS e2e, docs for QA/dev, internal demo |

**W5 risk**: three new integrations simultaneously (Playwright auth, Supabase Storage, bbox webhook). W6 buffers this.

### Release criteria for v1.0
- All 34 current routes present in manifest (automated check)
- Admin creates ghost → appears on canvas without page reload
- QA opens any node → screenshot + pins + verify works → status updates
- Nightly Action succeeds 3 consecutive nights, no manual retry
- RLS policies covered by automated tests — no role writes "someone else's"
- Junior QA can review one screen after 15-minute onboarding

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Selector rot when UI refactors | Pins drift/break on nightly | `selector_broken` flag + UI list "pins to fix"; gentle pressure to add `data-testid` to interactive elements |
| Orphan annotations on route rename | Lost QA work | Diff against prior manifest → explicit "Retarget" UI; never auto-migrate |
| Scope creep on layers | W5-W6 runs long | Layer list locked to 8 for v1.0; feature requests deferred to v1.1 |
| Playwright auth complexity | W5 slips | Prep test users in W3; dry-run Action once in W4 to de-risk |
| React Flow performance at 50+ nodes | UI laggy | Subflows + viewport culling; defer to optimization sprint if needed |
| `related_routes:` convention adoption | Specs incomplete | Fuzzy-match fallback by spec directory name; lint warning when missing |

---

## 12. Open Questions

None after brainstorm. All five design decisions resolved:
- **Audience**: dev (P1) + QA (P2) + users (P3) + customer (P4)
- **Source of truth**: hybrid (code-derived skeleton + mutable annotations)
- **Where it lives**: `/journey` inside onestack
- **Fidelity / MVP scope**: v1.0 rich experience minus Miro export, plus annotated screens
- **Interactivity layer**: selector-anchored pins, dual-mode (QA + training)

---

## 13. Dependencies & Prerequisites

- Phase 6C FastHTML retirement complete (in progress, finishing) — frees capacity for new module
- `kvota.user_has_role(slug)` helper — create if absent (short SQL, one-liner)
- `data-testid` / `data-action` hygiene on interactive elements — ongoing investment, pays back for pins AND future E2E tests
- Supabase Storage bucket `journey-screenshots` — provisioned during W5

---

## 14. Follow-up / Deferred

- **v1.1** — Miro export for customer demos, live iframe preview
- **v1.2** — Cross-linking: pins can reference related pins on other nodes
- **v2.0** — Session recording integrated from main onestack, replay in drawer
- **Claude Design pass** — polished mockups generated between spec approval and `writing-plans`, used as reference for W2 frontend work
