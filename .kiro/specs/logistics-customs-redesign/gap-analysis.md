# Gap Analysis — Logistics & Customs Redesign

**Feature:** `logistics-customs-redesign`
**Date:** 2026-04-22
**Phase:** post-requirements / pre-design-approval

## Summary

- **19 requirements reviewed** — 6 are extensions of existing code, 13 require new tables/modules
- **Major reuse opportunities**: existing `route_logistics_assignment_service.py` (1157 LOC), `user_table_views` (migration 261 + entity), `customs-handsontable.tsx` (420 LOC), `api/customs.py`, `workflow_service.assign_logistics_to_invoices`
- **Main architectural call needed**: how to handle old `logistics_stages` rows in in-progress deals (hybrid vs big-bang)
- **Scope-reducing finding**: table-views feature (R10, sub-project S) is ~40% done — schema + entity exist; only handsontable integration + shared-views UI remaining
- **No blockers** — all required primitives are either implementable independently or have clear extension points

---

## What already exists (reusable)

### Backend / DB

| Requirement | Existing artifact | Status |
|-------------|-------------------|--------|
| R3 Auto-assign logistics | `services/route_logistics_assignment_service.py` + `route_logistics_assignments` table (m027) | **Complete** — UI only missing |
| R3 Workflow hook | `workflow_service.assign_logistics_to_invoices(quote_id)` (m197 + m260 backfill) | **Complete** for logistics |
| R3 `assigned_logistics_user` | `invoices.assigned_logistics_user` + `pickup_country` | **Complete** |
| R10 Table views | `kvota.user_table_views` (m261, personal+shared schema-ready) + `entities/table-view/` FSD module | **~40% done** — schema supports shared views, UI currently personal-only |
| R7 Customs handsontable | `frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` (420 LOC) | **Refactor, not rewrite** — Handsontable internals preserved |
| Customs bulk update API | `api/customs.py` → `/api/customs/{quote_id}/items/bulk` with dual-auth | **Complete** pattern for new endpoints |
| R15 Locations | `kvota.locations` + `search_locations()` RPC + `is_hub`/`is_customs_point` booleans (m024) | **Extend with `location_type` enum** |
| R14 `head_of_customs` role | Roles table exists; slug missing | **Add via migration** |
| Dual auth pattern | `api/customs.py::_resolve_dual_auth` | **Reuse** for new handlers |
| API structure | `api/routers/`, `api/{domain}.py` handler modules | **Follow existing pattern** |

### Frontend

| Requirement | Existing artifact | Status |
|-------------|-------------------|--------|
| Next.js `(app)` route group | `frontend/src/app/(app)/` with shared layout | Use as-is for `/workspace/*` |
| `getSessionUser` | `frontend/src/entities/user/get-session-user.ts` | Use as-is in server components |
| `cn()` util | `frontend/src/lib/utils.ts` | Use as-is |
| shadcn primitives | `frontend/src/components/ui/*` (Button, Card, Tabs, Dialog, Sheet, Checkbox, Select, Input, Table, Popover, Dropdown-Menu, Tooltip, Badge, Avatar, Textarea, Toggle) | All needed primitives present |
| Drag-and-drop | `@dnd-kit/core 6.3.1`, `@dnd-kit/sortable 10.0.0` | In deps, no existing usage — ready for Route Constructor |
| Table lib | `@tanstack/react-table 8.21.3` for normal tables; `handsontable 17 + @handsontable/react 16` for customs | Both in deps |
| Toasts | `sonner 2.0.7` | In use across codebase |
| FSD layers | `app/`, `features/`, `entities/`, `shared/`, `widgets/`, `components/ui/` | Established |
| Admin routing page | `frontend/src/app/(app)/admin/routing/page.tsx` + `frontend/src/features/admin-routing/` | **Extend** with Logistics + Customs tabs (currently procurement-only) |

---

## What's missing (needs build)

### New tables (9 new + 2 alters)

| Table | Purpose | Requirement | Depends on |
|-------|---------|-------------|-----------|
| `logistics_route_segments` | Per-invoice pricing segments | R5 | new |
| `logistics_segment_expenses` | Freeform expenses inside segment | R5 | ↑ |
| `logistics_operational_events` | GTD/customs_cleared/delivered events | R6 | new |
| `logistics_route_templates` | Reusable segment chains | R5.5-6 | new |
| `logistics_route_template_segments` | Template segments | R5.5-6 | ↑ |
| `customs_item_expenses` | Per-quote_item customs costs | R9 | new |
| `customs_quote_expenses` | Per-quote customs costs | R9 | new |
| `entity_notes` | Polymorphic notes (MOZ/MOP/logistics/customs/customer-level) | R11 | new |
| ALTER `invoices` | `assigned_customs_user`, `logistics_*_at`, `customs_*_at`, `*_sla_hours`, `*_needs_review_since` | R2, R3, R4, R12 | existing |
| ALTER `locations` | `location_type` VARCHAR+CHECK, backfill | R15 | existing |
| ALTER `quote_items` | Drop `customs_ds_sgr`, drop `customs_marking`, rename `customs_psn_pts`→`customs_psm_pts` | R7 | existing |
| INSERT `roles` | `head_of_customs` slug | R14 | existing |

### New views / triggers

- **View** `v_logistics_plan_fact_items` — adapter for calc engine (reads new segments, returns `plan_fact_items`-shaped rows). R6.3
- **Trigger** `invoice_items_change_trigger` — smart delta flag setter. R12

### New FastAPI handlers (`api/`)

| Module | Endpoints | Requirement |
|--------|-----------|-------------|
| `api/logistics.py` (new) | segments + expenses CRUD, templates CRUD, complete/acknowledge-review | R5, R6 |
| `api/customs.py` (extend existing) | autofill endpoint (LATERAL JOIN), expenses CRUD, complete/ack-review | R8, R9 |
| `api/workflow.py` (extend) | `assign_customs_to_invoices(quote_id)` least-loaded impl | R3 |
| `api/notes.py` (new) | entity_notes CRUD with `visible_to` enforcement | R11 |
| `api/table_views.py` (extend if exists, else new) | ensure customs_items table_key supported, shared-view creation | R10 |
| `api/admin_routing.py` (new or extend) | logistics routing CRUD + coverage | R13 |

### New Next.js pages + features

| Path | Type | Requirement |
|------|------|-------------|
| `app/(app)/workspace/logistics/page.tsx` | New route | R1, R3, R4 |
| `app/(app)/workspace/customs/page.tsx` | New route | R2 |
| `features/workspace-logistics/` | New feature | R1 |
| `features/workspace-customs/` | New feature | R2 |
| `features/route-constructor/` | New feature (uses `@dnd-kit`) | R5 |
| `features/customs-autofill/` | New feature | R8 |
| `features/admin-routing-logistics/` | New feature (siblings to existing `features/admin-routing/`) | R13 |
| Extension of `features/quotes/ui/logistics-step/` | Integrate Route Constructor | R5 |
| Extension of `features/quotes/ui/customs-step/customs-handsontable.tsx` | Column cleanup + autofill + views + expenses wrappers | R7-9 |

### New entities (FSD `entities/`)

| Entity | Purpose | Requirement |
|--------|---------|-------------|
| `entities/location/` (partial may exist via shared/geo/) | LocationChip + queries by type | R15 |
| `entities/route-segment/` | queries, mutations, types | R5 |
| `entities/route-template/` | queries, mutations | R5.5-6 |
| `entities/operational-event/` | queries | R6 |
| `entities/entity-note/` | queries, mutations, NotesPanel | R11 |
| `entities/customs-expense/` | item+quote expense queries | R9 |
| `entities/user/ui/` extension | UserAvatarChip component | R13 |

### New shared/UI components

| Component | Purpose | Used in |
|-----------|---------|---------|
| `shared/ui/sla-timer-badge.tsx` | Green/yellow/red deadline chip | R1, R2, R5 side panel |
| `shared/ui/role-based-tabs.tsx` | Role-conditional tabs rendering | R1.5, R2.1, R13 |
| `shared/ui/autofill-sparkle.tsx` | ✨ icon with source tooltip | R8 |

---

## Implementation approach options

### Option A — Hybrid (recommended)

Keep `logistics_stages` table **read-only** for historical reports. Existing in-progress deals' logistics data remains queryable but new writes go to `logistics_route_segments` + `logistics_operational_events`. Calc engine reads new model via `v_logistics_plan_fact_items`. No data migration — when a stuck deal reaches logistics step, UI prompts logistician to re-enter route in new constructor (justified by user's policy `feedback_oneshot_migrations_when_engine_locked.md`).

**Pros:** minimum breaking, in-progress deals recoverable by re-entering (few in production), view absorbs schema change from calc engine.
**Cons:** historical reports cross two schemas; adapter view complexity.

### Option B — Big-bang migration

Write one-time migration that translates existing `logistics_stages` rows into `logistics_route_segments` (1:1 by `stage_code → from/to locations`) + copies `plan_fact_items.logistics_stage_id` into new expense model.

**Pros:** single source of truth post-migration; reports uniform.
**Cons:** translation is lossy (stage_code enum → location pair mapping requires guessing); data loss risk on edge cases; user policy prefers one-shot over expand-contract but this specific case has no semantic 1:1 mapping.

### Option C — Parallel evolution (dual-write)

New code writes both old and new tables. Read-path picks based on feature flag.

**Pros:** safe rollback.
**Cons:** dual-write bugs; no clear sunset; overcomplicated for our scale.

**Recommendation:** **Option A (hybrid)** — aligns with user policy and project scale. Design phase should ratify this before spec-tasks.

---

## Steering compliance notes

- **api-first.md** (`.kiro/steering/`): every new /api/logistics/*, /api/customs/*, /api/notes/*, /api/workflow/* handler follows "business logic in Python; Next.js Server Actions = thin wrappers." Structured docstrings per endpoint mandatory. ✅ Aligned.
- **access-control.md**: all new tables need RLS with role-based policies. Pattern established by existing `logistics_additional_expenses`, `user_table_views`. ✅ Follow.
- **database.md**: schema `kvota.*`, `r.slug`, sequential numbered migrations via `scripts/apply-migrations.sh`. ✅ Follow.
- **structure.md**: FSD layers, no horizontal feature imports, public API via slice `index.ts`. ✅ Follow.
- **tech.md**: Next.js 16 + FastAPI (uvicorn) + Supabase Postgres, kvota schema. ✅ Aligned.

---

## Items flagged for design-phase resolution

1. **Backfill strategy for `locations.location_type`** — heuristic (is_hub → 'hub', is_customs_point → 'customs', default 'hub') is lossy. Manual review recommended for the org's ~20-50 locations. Who owns this cleanup?

2. **Smart delta trigger semantics for `brand` field change** — if procurement changes `brand` on an invoice_item, logistics segments don't depend on brand, but customs autofill source matching uses `(brand, product_code)`. Should brand change flag customs? Requirements R12 says no — but autofill source invalidation argues yes. Design phase clarifies.

3. **`assign_customs_to_invoices` least-loaded implementation** — pure SQL (GROUP BY + ORDER BY + LIMIT 1) vs RPC function vs application-layer. Trade-offs on consistency under concurrent writes. Design phase ratifies.

4. **Table-views schema reuse** — existing `user_table_views.table_key` convention. What literal key to use for customs items table? Propose `customs_items_v2` (new to avoid conflict if existing views had different schema).

5. **Migration sequencing within Wave 1** — some depend on others (segments → need location_type first, smart-delta trigger → needs completed_at columns). Design phase produces explicit migration order.

6. **Telegram notification debouncing** — R4.2/R4.3 say "once per invoice" for SLA warnings. Need dedupe key table or in-memory counter. Design.

7. **Handsontable column schema change & existing personal views** — when columns drop/rename (R7.1-7.3), existing `user_table_views.visible_columns` array may contain obsolete keys. Requirements R10.6 says "gracefully ignore unknown column keys" — confirmed. One-time cleanup migration needed for `visible_columns` array to also rename `customs_psn_pts → customs_psm_pts`.

---

## Document Status

- ✅ Gap analysis complete per requirements.md
- ✅ Existing codebase surveyed (key files: `route_logistics_assignment_service.py`, `customs-handsontable.tsx`, `entities/table-view/`, `api/customs.py`, m027/m197/m261/m233/m190/m163)
- ✅ Steering files reviewed (all 5 in `.kiro/steering/`)
- ⚠️ 7 items flagged for design phase resolution (see above)
- 🔄 No blockers for design phase

## Next Steps

**Recommended path:**
1. Review this gap analysis — edit `requirements.md` if any finding changes requirements (e.g. if backfill strategy for locations forces a new AC)
2. Approve requirements: set `.kiro/specs/logistics-customs-redesign/spec.json` → `approvals.requirements.approved = true`
3. Run `/kiro:spec-design logistics-customs-redesign -y` to finalize design doc (existing `design.md` already strong — skill may polish)
4. After design approval — `/kiro:spec-tasks logistics-customs-redesign -y`
5. Then `/lean-tdd` picks up tasks per sub-project

Alternative (if confident): approve requirements + design together, jump straight to `/kiro:spec-tasks`.
