# Tasks — Logistics & Customs Redesign

**Workflow:** `/lean-tdd` — каждая sub-task = один RED → GREEN → REFACTOR cycle.
**Parallel markers:** `(P)` — задача может выполняться параллельно с другими `(P)`-tasks в той же волне (нет общих файлов/данных).
**Check-ins:** после каждой завершённой Wave — обзор с пользователем перед следующей.
**Commit hygiene:** `git add <explicit paths>` — никогда `git add .` или `git add -A`. Trailer: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
**Coordination:** sub-project G (suppliers contacts) отдан в `/procurement` branch — здесь не реализуется. Sub-project R (carriers) отложен.

Requirements count mapped: 16 requirements → 17 major tasks → ~70 sub-tasks.

---

# Wave 1 — Foundation (P0, 7 sub-projects)

## Task 1 — Sub-project A: Locations `location_type` enum `(P)`

**Goal:** Add `location_type` VARCHAR(20) column to `kvota.locations` with CHECK constraint, backfill from existing `is_hub` / `is_customs_point` booleans, extend entity + chip component.
**Requirements:** 15.1, 15.2, 15.3, 15.4

### 1.1 Migration: add column + CHECK + backfill

**RED:** `tests/test_migration_284.py` — asserts `locations.location_type` column exists with CHECK, rows backfilled correctly for all 3 heuristic cases (is_hub only → 'hub', is_customs_point → 'customs', neither → default 'hub').

**GREEN:** `migrations/284_add_location_type.sql` — `ALTER TABLE ADD COLUMN location_type VARCHAR(20) NOT NULL DEFAULT 'hub' + CHECK + UPDATE … backfill`. Old booleans preserved.

**Commit:** `git add migrations/284_add_location_type.sql tests/test_migration_284.py` — `feat(logistics-customs): migration 284 — locations.location_type enum`

**Acceptance:** all existing rows get `location_type` set, CHECK blocks invalid values, old booleans untouched.

### 1.2 Manual review helper: list locations needing reclassification

**RED:** n/a (operational helper).

**GREEN:** SQL script `scripts/audit-location-types.sql` prints rows where `location_type = 'hub'` but name hints at 'supplier' / 'own_warehouse' / 'client' (e.g. contains "склад", "фабрика"). Admin reviews output manually, runs UPDATE's in follow-up.

**Commit:** `git add scripts/audit-location-types.sql` — `chore(logistics): audit script for location_type manual review`

### 1.3 Entity + LocationChip component `(P)`

**RED:** `frontend/src/entities/location/__tests__/location-chip.test.tsx` — asserts chip renders correct color class per `location_type` (supplier→success, hub→accent-subtle, customs→warning, etc.), tooltip with full name.

**GREEN:** create `frontend/src/entities/location/` (queries.ts, types.ts, ui/location-chip.tsx, index.ts). Queries filter by `location_type`; LocationChip uses CSS vars from design system (no hex).

**Commit:** `git add frontend/src/entities/location/` — `feat(entities/location): typed chip + queries`

**Acceptance:** chip variants для 5 типов, design-system tokens only.

---

## Task 2 — Sub-project B: Customs columns cleanup

**Goal:** Drop `customs_ds_sgr` + `customs_marking`, rename `customs_psn_pts → customs_psm_pts`, migrate existing data, update handsontable column config + types, add RUB disclaimer in toolbar.
**Requirements:** 7.1, 7.2, 7.3, 7.5, 7.6

### 2.1 Migration 285: data-preserving schema refactor

**RED:** `tests/test_migration_285.py` — verifies `customs_ds_sgr` / `customs_marking` columns gone, `customs_psm_pts` exists (was `customs_psn_pts`), data from old columns best-effort parsed into `license_ds_required`/`_ss_`/`_sgr_` + `customs_honest_mark`.

**GREEN:** `migrations/285_customs_columns_cleanup.sql` — `UPDATE` parsing customs_ds_sgr (regex find "ДС"/"СС"/"СГР") → `license_*_required=true`, then `DROP COLUMN customs_ds_sgr, customs_marking; RENAME customs_psn_pts TO customs_psm_pts`.

**Commit:** `git add migrations/285_customs_columns_cleanup.sql tests/test_migration_285.py` — `feat(customs): migration 285 — drop legacy columns, rename ПСН→ПСМ`

**Acceptance:** no data loss where parsing unambiguous; ambiguous cases logged for manual review.

### 2.2 Regen DB types + frontend refactor

**RED:** handsontable test suite (existing `test_customs_licenses.py` etc.) updated to expect no `customs_ds_sgr`/`customs_marking` in `COLUMN_KEYS`, rename PSN→PSM tolerated.

**GREEN:** `cd frontend && npm run db:types`. Update `customs-handsontable.tsx` — remove 2 column defs, rename 1. Add RUB-disclaimer Badge in toolbar row.

**Commit:** `git add frontend/src/lib/database.types.ts frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx tests/test_customs_licenses.py` — `refactor(customs-handsontable): drop legacy columns, rename PSN→PSM, add RUB disclaimer`

**Acceptance:** Existing HoT tests green; visual: "Все суммы в ₽" visible вverhu.

### 2.3 Composite "Пошлина" column with type chip `(P)`

**RED:** test asserts customs column "Пошлина" renders composite cell (value + `% / ₽/кг / ₽/шт` chip-selector), writing chip toggles storage column (`customs_duty` vs `customs_duty_per_kg`).

**GREEN:** новый `DutyCellRenderer` в `customs-step/cells/`, CellMeta custom editor. On chip change — swap target column, clear the other.

**Commit:** `git add frontend/src/features/quotes/ui/customs-step/cells/ frontend/src/features/quotes/ui/customs-step/customs-handsontable.tsx` — `feat(customs): composite Пошлина column with %/₽-kg/₽-pcs chip`

**Acceptance:** Req 7.4. Storage exclusivity enforced (только одно поле non-null).

---

## Task 3 — Sub-project F: Customs expenses tables + UI `(P)` (independent of Task 2)

**Goal:** Two new tables for per-item and per-quote customs costs, API endpoints, two UI cards below handsontable.
**Requirements:** 9.1, 9.2, 9.3

### 3.1 Migration 286: customs_item_expenses + customs_quote_expenses

**RED:** `tests/test_migration_286.py` — schema + RLS policies (org_members access via quote_items→quote→org, identical pattern для quote expenses).

**GREEN:** `migrations/286_customs_expenses.sql` — two CREATE TABLE + indexes + RLS `org_members_all` policies.

**Commit:** `git add migrations/286_customs_expenses.sql tests/test_migration_286.py` — `feat(customs): migration 286 — item + quote expenses tables`

### 3.2 Regen types + entity/customs-expense

**RED:** `entities/customs-expense/__tests__/queries.test.ts` — CRUD coverage.

**GREEN:** `cd frontend && npm run db:types`. Create `entities/customs-expense/` (queries, mutations, types, index).

**Commit:** `git add frontend/src/entities/customs-expense/ frontend/src/lib/database.types.ts` — `feat(entities/customs-expense): CRUD`

### 3.3 API routes: POST/DELETE item + quote expenses

**RED:** `tests/test_api_customs_expenses.py` — auth check (customs/admin/head_of_customs roles), 200/204 for valid, 403 other roles.

**GREEN:** `api/customs.py` — extend with handlers `/api/customs/items/{id}/expenses` (POST/DELETE) and `/api/customs/quotes/{id}/expenses` (POST/DELETE). Dual-auth (pattern from existing). Structured docstrings.

**Commit:** `git add api/customs.py tests/test_api_customs_expenses.py` — `feat(api/customs): expenses CRUD endpoints`

### 3.4 UI cards under handsontable

**RED:** Vitest — two cards render, "Добавить расход" inline form works, delete action hits API.

**GREEN:** `features/quotes/ui/customs-step/quote-customs-expenses.tsx` + `item-customs-expenses.tsx` (shows for `selectedRowId`). Use shadcn `<Card>`, `<Input>`, sonner toast on mutation.

**Commit:** `git add frontend/src/features/quotes/ui/customs-step/` — `feat(customs-step): per-item + per-quote expenses cards`

**Acceptance:** Req 9.3. Both cards visible, inline add/delete работает.

---

## Task 4 — Sub-project H: Logistics route constructor (largest)

**Goal:** New per-invoice route model (segments + expenses + operational_events + templates) + drag&drop timeline UI + details panel + view adapter to calc engine. Replaces old `logistics_stages` for new deals (hybrid — see design §9.5).
**Requirements:** 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3

### 4.1 Migration 287: route_segments + segment_expenses tables

**RED:** `tests/test_migration_287.py` — schema, indexes, RLS, FK cascades, UNIQUE(invoice_id, sequence_order).

**GREEN:** `migrations/287_logistics_route_segments.sql` — two tables per design §5.1.

**Commit:** `git add migrations/287_logistics_route_segments.sql tests/test_migration_287.py` — `feat(logistics): migration 287 — route_segments + segment_expenses`

### 4.2 Migration 288: operational_events + templates tables

**RED:** `tests/test_migration_288.py` — three tables (operational_events, route_templates, route_template_segments).

**GREEN:** `migrations/288_logistics_operational_events_and_templates.sql`.

**Commit:** `git add migrations/288_*.sql tests/test_migration_288.py` — `feat(logistics): migration 288 — operational_events + route_templates`

### 4.3 Migration 289: v_logistics_plan_fact_items view

**RED:** `tests/test_v_logistics_plan_fact_items.py` — 3 sample deals: create route_segments matching their existing logistics_stages + plan_fact_items; view returns **bit-identical** rows (category_id, planned_amount, deal_id) to legacy model. Also: view is READ-ONLY (INSERT/UPDATE fails).

**GREEN:** `migrations/289_v_logistics_plan_fact_items.sql` — exact SQL from design §5.4 (includes category mapping CTE).

**Commit:** `git add migrations/289_*.sql tests/test_v_logistics_plan_fact_items.py` — `feat(logistics): migration 289 — calc engine adapter view`

**Acceptance:** Req 6.3. Bit-identical test for 3 deals pass.

### 4.4 Calc engine adapter service

**RED:** `tests/test_calc_engine_logistics_adapter.py` — `fetch_logistics_plan_fact_for_deal(deal_id)` merges legacy `plan_fact_items.logistics_stage_id IS NOT NULL` rows + view rows; for deals with only new data returns only view rows, для deals с только legacy — только legacy.

**GREEN:** `services/calc_engine_logistics_adapter.py` — single function merging two sources via UNION-query. Imported by calc engine consumer code (not by calc_engine.py itself — calc engine unchanged).

**Commit:** `git add services/calc_engine_logistics_adapter.py tests/test_calc_engine_logistics_adapter.py` — `feat(services): calc engine logistics adapter (hybrid bridge)`

### 4.5 API: segments + expenses + templates CRUD

**RED:** `tests/test_api_logistics.py` — 12 endpoint tests (segments CRUD, expenses CRUD, templates CRUD, complete, acknowledge-review).

**GREEN:** `api/logistics.py` (new) — routes per design §6.1. Dual-auth. Reorder endpoint updates all segments in one transaction.

**Commit:** `git add api/logistics.py tests/test_api_logistics.py` — `feat(api/logistics): segments + expenses + templates + complete/review`

### 4.6 Entity: route-segment + route-template + operational-event

**RED:** Vitest suite для queries + mutations.

**GREEN:** three entities in `frontend/src/entities/`: `route-segment/`, `route-template/`, `operational-event/`.

**Commit:** `git add frontend/src/entities/route-segment/ frontend/src/entities/route-template/ frontend/src/entities/operational-event/ frontend/src/lib/database.types.ts` — `feat(entities): route segment/template/operational-event`

### 4.7 Feature: route-constructor — timeline with drag&drop

**RED:** Vitest — timeline renders N nodes + N-1 edges; drag reorders via `@dnd-kit/sortable`; click on edge opens details panel.

**GREEN:** `frontend/src/features/route-constructor/` — SortableContext wrapper, Node + Edge components using LocationChip, details panel с inline-edit полей. "Шаблон" dropdown materializes segments from selected template.

**Commit:** `git add frontend/src/features/route-constructor/` — `feat(route-constructor): timeline with drag&drop + details panel`

### 4.8 Integration into logistics-step

**RED:** Vitest — opening logistics step of existing quote renders route-constructor, InvoiceTabs switches active invoice.

**GREEN:** replace `features/quotes/ui/logistics-step/` content with route-constructor composition + new InvoiceTabs (shared, создан в Task 5.3 — ждём).

**Commit:** `git add frontend/src/features/quotes/ui/logistics-step/` — `feat(logistics-step): integrate route-constructor`

**Acceptance:** Req 5.1-5.7 complete. Old logistics_stages data not written to for new deals.

---

## Task 5 — Sub-project I: Logistics client-info + `entity_notes` (cross-cutting)

**Goal:** Polymorphic notes table + RBAC + panel component + client-info fields (страна, responsible) + label rewording + InvoiceTabs shared component.
**Requirements:** 11.1, 11.2, 11.3, 11.4, 11.5

### 5.1 Migration 290: entity_notes table + RLS

**RED:** `tests/test_migration_290.py` — schema, indexes, GIN index on visible_to[], RLS policies (user must have one of visible_to[] roles OR '*').

**GREEN:** `migrations/290_entity_notes.sql` — full table + 4 policies (select/insert/update/delete).

**Commit:** `git add migrations/290_entity_notes.sql tests/test_migration_290.py` — `feat(notes): migration 290 — entity_notes polymorphic table`

### 5.2 API: /api/notes CRUD with visibility enforcement

**RED:** `tests/test_api_notes.py` — user with role X sees only notes where 'X' ∈ visible_to OR '*' ∈ visible_to.

**GREEN:** `api/notes.py` (new) — CRUD с dual-auth. PATCH allowed only for author + admin.

**Commit:** `git add api/notes.py tests/test_api_notes.py` — `feat(api/notes): entity-notes CRUD`

### 5.3 Entity: entity-note + InvoiceTabs shared `(P)`

**RED:** Vitest: EntityNotesPanel renders ordered list, compose-form works; InvoiceTabs highlights active.

**GREEN:** `frontend/src/entities/entity-note/` — queries, mutations, `<EntityNotesPanel entity_type entity_id />`. Shared `frontend/src/features/quotes/ui/invoice-tabs.tsx`.

**Commit:** `git add frontend/src/entities/entity-note/ frontend/src/features/quotes/ui/invoice-tabs.tsx frontend/src/lib/database.types.ts` — `feat(entity-note + invoice-tabs): shared UI primitives`

### 5.4 Client-info + label rewording in logistics-step

**RED:** test — logistics-step renders client страна/address/responsible fields, currency label reads "Валюта КП для клиента", delivery split into basis + wishes, priority default "обычно".

**GREEN:** edit `features/quotes/ui/logistics-step/` — forms for renamed / new fields. No schema change (fields already on quote).

**Commit:** `git add frontend/src/features/quotes/ui/logistics-step/` — `feat(logistics-step): client-info fields + relabeled UI`

**Acceptance:** Req 11.2 (3 note groups visible), Req 1 (ТЗ лог пункт 1,2).

---

## Task 6 — Sub-project J: RBAC hardening + `head_of_customs` role

**Goal:** Hide Финансы tab from logistics/customs roles, add head_of_customs role, extend permission checks to symmetrically include head_of_customs wherever head_of_logistics is used.
**Requirements:** 14.1, 14.2, 14.3, 16.1, 16.2, 16.3

### 6.1 Migration 291: insert head_of_customs role

**RED:** `tests/test_migration_291.py` — role inserted for every org, idempotent on re-run.

**GREEN:** `migrations/291_insert_head_of_customs.sql` — per design §5.2.

**Commit:** `git add migrations/291_insert_head_of_customs.sql tests/test_migration_291.py` — `feat(roles): migration 291 — head_of_customs role`

### 6.2 Backend RBAC extensions

**RED:** `tests/test_rbac_head_of_customs.py` — endpoints that check head_of_logistics for logistics domain now also accept head_of_customs for customs domain; API 403 for logistics/customs-only role on finance endpoints.

**GREEN:** grep "head_of_logistics" → add symmetric `head_of_customs` checks где scope = customs. `api/plan_fact.py` etc. — reject logistics/customs-only roles via 403.

**Commit:** `git add <edited py files> tests/test_rbac_head_of_customs.py` — `feat(rbac): head_of_customs symmetry + finance lock-out for log/customs`

### 6.3 Frontend tabs hiding

**RED:** Vitest — quote detail with user role `logistics` → no "Финансы" / "Валютные инвойсы" tabs.

**GREEN:** `shared/lib/roles.ts` — `canSeeFinanceTabs(roles)`. Wire into quote-detail-shell.tsx.

**Commit:** `git add frontend/src/shared/lib/roles.ts frontend/src/features/quotes/ui/quote-detail-shell.tsx` — `feat(rbac): hide finance tabs from logistics/customs`

**Acceptance:** Req 14.1-14.3, 16.1-16.3.

---

## Task 7 — Sub-project N: Workspace pages (`/workspace/logistics` + `/workspace/customs`)

**Goal:** Assignment-based workspace with SLA timers, head-only tabs (Неназначенные / Все), role switcher if both head-roles. Depends on SLA column migrations from prereq step.
**Requirements:** 1.1-1.6, 2.1, 2.2, 3.1-3.4, 4.1-4.4

### 7.1 Migration 292: invoices SLA + assignment timers + customs assignment

**RED:** `tests/test_migration_292.py` — columns added: `assigned_customs_user`, `logistics_assigned_at`, `logistics_deadline_at`, `logistics_completed_at`, `logistics_sla_hours` (DEFAULT 72), `customs_*` symmetric, `logistics_needs_review_since`, `customs_needs_review_since`. Indexes.

**GREEN:** `migrations/292_invoices_sla_and_customs_assignment.sql`.

**Commit:** `git add migrations/292_*.sql tests/test_migration_292.py` — `feat(invoices): migration 292 — SLA timers + customs assignment`

### 7.2 `assign_customs_to_invoices` with advisory lock

**RED:** `tests/test_assign_customs_invoices.py` — least-loaded picked; concurrent txn test — two workflow transitions не назначают одного user'а одновременно (advisory lock works).

**GREEN:** `services/workflow_service.py` — new `assign_customs_to_invoices(quote_id)` per design §3.4 (advisory lock + least-loaded SELECT + batch UPDATE).

**Commit:** `git add services/workflow_service.py tests/test_assign_customs_invoices.py` — `feat(workflow): customs assignment with advisory lock`

### 7.3 Extend workflow step: call both assign_* on pending_logistics_and_customs transition

**RED:** `tests/test_workflow_pending_logistics_and_customs.py` — transition fires both logistics + customs assignment; timestamps + deadline_at set correctly; Telegram notified (mock).

**GREEN:** patch `workflow_service.transition_quote_status()` to call `assign_customs_to_invoices` after `assign_logistics_to_invoices`.

**Commit:** `git add services/workflow_service.py` — `feat(workflow): wire customs assignment into transition`

### 7.4 Workspace page /workspace/logistics

**RED:** Vitest + Playwright — page loads, shows only current user's assigned invoices, SLA dot color correct, head sees extra tabs.

**GREEN:** `frontend/src/app/(app)/workspace/logistics/page.tsx` + `frontend/src/features/workspace-logistics/`. Server component: `getSessionUser → redirect if no orgId → fetchMyInvoices/fetchUnassigned/fetchAll via Promise.all → pass props`. Client feature uses `@tanstack/react-table`.

**Commit:** `git add frontend/src/app/(app)/workspace/logistics/ frontend/src/features/workspace-logistics/ frontend/src/shared/ui/sla-timer-badge.tsx frontend/src/shared/ui/role-based-tabs.tsx` — `feat(workspace): /workspace/logistics assignment-based`

### 7.5 Workspace page /workspace/customs (parallel/symmetric) `(P)`

**RED:** analogous.

**GREEN:** `frontend/src/app/(app)/workspace/customs/page.tsx` + `frontend/src/features/workspace-customs/`. Same RoleBasedTabs + SlaTimerBadge shared.

**Commit:** `git add frontend/src/app/(app)/workspace/customs/ frontend/src/features/workspace-customs/` — `feat(workspace): /workspace/customs`

### 7.6 Role switcher (for users with both head-roles)

**RED:** Vitest — user with both `head_of_logistics` + `head_of_customs` sees switcher; single-head user — не видит.

**GREEN:** `RoleSwitcher` component in `features/workspace-logistics/ui/` (shared via hoisted import).

**Commit:** `git add frontend/src/features/workspace-*/ui/role-switcher.tsx` — `feat(workspace): dual-head role switcher`

**Acceptance:** Req 2.2.

---

### ✅ Wave 1 Check-in

После Task 7 — demo user'у: full workspace + quote detail logistics+customs работает end-to-end для нового deal. Пользователь apporves перед Wave 2.

---

# Wave 2 — UX improvements (P1, 6 sub-projects)

## Task 8 — Sub-project C: Customs row "expand" modal `(P)`

**Goal:** Per-row `↗` icon button opens `<Dialog>` с полным набором полей + item-level expenses.
**Requirements:** 9.4

**Sub-tasks:**
- 8.1 RED: Vitest — click on `↗` opens Dialog; all fields editable; save persists to quote_items + customs_item_expenses. GREEN: `features/quotes/ui/customs-step/customs-item-dialog.tsx` using shadcn Dialog. Commit: `feat(customs): row expand modal`

---

## Task 9 — Sub-project D: Customs autofill + bulk-accept

**Goal:** `/api/customs/autofill` LATERAL JOIN endpoint + highlight autofilled cells + banner with bulk-accept + mandatory certificates checkbox.
**Requirements:** 8.1-8.6

### 9.1 Index for autofill perf + API endpoint

**RED:** `tests/test_api_customs_autofill.py` — POST array of {brand, product_code}, returns suggestions by newest hs_code match; partial suggestions for unique-brand-only matches.

**GREEN:** `migrations/293_autofill_index.sql` (CREATE INDEX partial on quote_items.brand + product_code WHERE hs_code IS NOT NULL). `api/customs.py` — new `/api/customs/autofill` endpoint with LATERAL JOIN query per design §3.9.

**Commit:** `feat(customs): migration 293 autofill index + /api/customs/autofill endpoint`

### 9.2 UI: AutofillBanner + AutofillSparkle

**RED:** Vitest — banner counts suggestions; Accept-all disabled until checkbox checked; on accept — bulk-updates via API, clears suggestions.

**GREEN:** `features/customs-autofill/ui/autofill-banner.tsx` + `features/customs-autofill/ui/autofill-sparkle.tsx` (sparkle renders in row № cell tooltip). Integrate into `customs-handsontable.tsx` customFormatter for sparkle column.

**Commit:** `feat(customs-autofill): banner + sparkle + bulk-accept flow`

**Acceptance:** Req 8.1-8.6.

---

## Task 10 — Sub-project K: Logistics cargo items readability + numbering + currency `(P)`

**Goal:** Make cargo-places block readable (bigger fonts, contrast), add position numbers, show currency of КП.
**Requirements:** ТЗ логистики п.5 (частично покрывается R1.2/5.4, UX-only)

- 10.1 Patch `features/quotes/ui/logistics-step/cargo-places.tsx` — typography scale, number badge, currency chip. RED: Vitest snapshot / visual regression. Commit: `refactor(logistics-step): cargo-places readability + numbering + currency`

---

## Task 11 — Sub-project L: Logistics → КП supplier comment `(P)`

**Goal:** `EntityNotesPanel entity_type="invoice"` card in logistics-step визуально отдельная, visible_to=['procurement','head_of_procurement'].
**Requirements:** 11.4

- 11.1 Create `InvoiceCommentCard` wrapping EntityNotesPanel with pre-set visible_to. Commit: `feat(logistics-step): invoice comment for procurement`

---

## Task 12 — Sub-project O: SLA timers + Telegram pings `(P)`

**Goal:** Scheduled job sending reminder at (deadline-24h) and overdue-notification at deadline to head.
**Requirements:** 4.2, 4.3

### 12.1 Cron job endpoint + dedupe table

**RED:** `tests/test_sla_pings.py` — at T=deadline-24h reminder sent once (dedupe via `invoice_sla_notifications_sent (invoice_id, kind)` row); overdue after deadline also once.

**GREEN:** `migrations/294_sla_notifications_dedupe.sql` — small dedupe table. `api/cron.py` — extend with `/api/cron/sla-check` handler (called externally every 10 min). Uses existing `telegram_service.send_message`.

**Commit:** `feat(sla): migration 294 + /api/cron/sla-check with dedupe`

---

## Task 13 — Sub-project S: Table views for customs handsontable

**Goal:** Activate existing `user_table_views` schema (m261) in UI for customs. Support shared (org-wide) views via `is_shared=true`.
**Requirements:** 10.1-10.6

### 13.1 Extend entity table-view — enable shared views

**RED:** `entities/table-view/__tests__/queries.test.ts` — `fetchAllAvailable(orgId, tableKey)` returns personal OF user + all shared OF org; `createShared` requires head_of_customs role.

**GREEN:** extend `queries.ts` / `mutations.ts` — filter by `is_shared=true OR user_id=self`; mutations check role before `is_shared=true`.

**Commit:** `feat(table-view): enable org-wide shared views`

### 13.2 UI: TableViewsDropdown + Settings Dialog

**RED:** Vitest — dropdown lists personal + shared; "Настроить колонки" opens modal with checkbox list + drag-reorder; save creates/updates.

**GREEN:** `features/table-views/ui/table-views-dropdown.tsx` + `table-views-settings-dialog.tsx`. Integration in `customs-handsontable.tsx` — visible_columns filter drives column config.

**Commit:** `feat(table-views): dropdown + settings UI for customs`

### 13.3 Rename migration update for existing visible_columns

**RED:** after m285 renamed `customs_psn_pts → customs_psm_pts`, existing `user_table_views.visible_columns` containing old name should be auto-updated.

**GREEN:** part of m285 (or separate m295) — `UPDATE user_table_views SET visible_columns = array_replace(visible_columns, 'customs_psn_pts', 'customs_psm_pts')`.

**Commit:** `chore(table-view): migrate visible_columns array with column rename`

**Acceptance:** Req 10.1-10.6.

---

### ✅ Wave 2 Check-in

---

# Wave 3 — Coordinated + Analytics (P2, 4 sub-projects: E, M, P, Q — G skipped, in procurement branch)

## Task 14 — Sub-project E: Smart delta trigger + review banner

**Goal:** DB trigger + `invoices.*_needs_review_since` flags, yellow review banner in UI that blocks "Завершить расценку" until acknowledged.
**Requirements:** 12.1-12.5
**Coord:** trigger name `trg_zz_invoice_items_smart_delta` (see design §10) — sync с procurement branch owner перед merge.

### 14.1 Migration 296: trigger `trg_zz_invoice_items_smart_delta`

**RED:** `tests/test_trigger_smart_delta.py` — matrix coverage (quantity change → logistics flag; supplier_id → both; brand → neither).

**GREEN:** `migrations/296_smart_delta_trigger.sql` per design §5.3 naming convention.

**Commit:** `feat(logistics-customs): migration 296 — smart delta trigger`

### 14.2 Review banner in logistics-step + customs-step

**RED:** Vitest — banner visible when `logistics_needs_review_since IS NOT NULL`; "Завершить" button disabled; "Подтвердить без изменений" clears flag.

**GREEN:** `shared/ui/review-banner.tsx` — reusable. Integrate в logistics-step + customs-step with respective flag + `POST /api/*/acknowledge-review`.

**Commit:** `feat(review-banner): yellow smart-delta review with acknowledge flow`

**Acceptance:** Req 12.1-12.5.

---

## Task 15 — Sub-project M: Admin routing UI — Logistics tab

**Goal:** Add "Логистика" tab to `/admin/routing` (existing procurement tabs intact) + unassigned inbox + patterns table + create side panel.
**Requirements:** 13.1-13.5
**Coord:** `frontend/src/app/(app)/admin/routing/page.tsx` также редактируется в procurement branch — договориться о merge order (this branch adds tab, procurement branch doesn't touch file).

### 15.1 API: routing endpoints for logistics patterns + coverage

**RED:** `tests/test_api_admin_routing_logistics.py` — list/create/update/delete + coverage endpoint returns uncovered countries.

**GREEN:** `api/admin_routing.py` (new or extend existing) — wraps `route_logistics_assignment_service`. Auth: admin + head_of_logistics.

**Commit:** `feat(api/admin-routing): logistics patterns CRUD + coverage`

### 15.2 Tab + patterns table feature

**RED:** Vitest — tab renders; stats strip; patterns table sorted exact-first; row actions work.

**GREEN:** extend `features/admin-routing/` with `logistics-tab.tsx` + `patterns-table.tsx` + `unassigned-inbox.tsx` + `new-pattern-sheet.tsx` (shadcn Sheet from side). Stats queries via `fetchRoutingStats`.

**Commit:** `feat(admin-routing): logistics tab — patterns + unassigned + stats + create`

**Acceptance:** Req 13.1-13.5.

---

## Task 16 — Sub-project P: Analytics dashboard for heads `(P)`

**Goal:** "Кто сколько отработал" — table of users with completed invoices count + median time-to-complete.
**Requirements:** ТЗ (user hint в wireframe 04), derived from SLA columns.

- 16.1 RED: Vitest + query test. GREEN: `features/workspace-*/ui/analytics-panel.tsx` + backend query `/api/workspace/{domain}/analytics`. Visible только для head_of_*. Commit: `feat(workspace): analytics panel for heads`

---

## Task 17 — Sub-project Q: Hub/warehouse registry UI `(P)`

**Goal:** Extend locations listing UI with location_type filter + chip colors.
**Requirements:** 15.4

- 17.1 RED: Vitest — filter chip toggles; LocationChip visible in rows. GREEN: extend `app/(app)/locations/page.tsx` + feature. Commit: `feat(locations): typed filter + chip display`

---

### ✅ Wave 3 Check-in — готовы к PR/merge по всему спецификации.

---

# Deferred

- **Sub-project R: Carriers registry** — user explicit "сейчас можно пропустить". Future spec.
- **External / Internal МОЛ split** — deferred to execution phase (beyond pricing scope).

---

## Summary

- **17 major tasks, ~60 sub-tasks**
- **Wave 1 (7 tasks):** foundation — migrations 284-292 + core features
- **Wave 2 (6 tasks):** UX polish — autofill, table views, SLA pings
- **Wave 3 (4 tasks):** coordinated — smart delta trigger, admin routing UI, analytics, location registry
- **All 16 requirements** mapped; additional operational helper scripts included
- **`(P)` markers** on 10 tasks safe for parallel execution в той же волне
- **Check-ins** после каждой волны — review с user

**Commit tasks.md when ready:**
```bash
git add .kiro/specs/logistics-customs-redesign/tasks.md .kiro/specs/logistics-customs-redesign/spec.json
git commit -m "spec(logistics-customs): generate implementation tasks (17 major, ~60 sub)"
```

**Next (after user approves tasks):**
- Execute via `/lean-tdd` starting with Task 1 (Locations `location_type`).
- Run `/kiro:spec-impl logistics-customs-redesign -y 1.1` for first sub-task.
- Clear conversation context между major tasks (kiro convention).
