# Requirements Document — Logistics & Customs Redesign

## Introduction

Redesign of the "Логистика" and "Таможня" stages of the quote → deal pipeline. Covers four user-visible surfaces: assignment-based Workspace, per-invoice Route Constructor, Customs handsontable with autofill-from-history, and Admin Routing UI for logistics patterns.

**Parent design spec:** `docs/superpowers/specs/2026-04-22-logistics-customs-redesign-design.md` — full architectural rationale, data model, API, 19-subproject breakdown.
**Wireframes:** `docs/superpowers/wireframes/2026-04-22-logistics-customs/` — 4 HTML reference screens.
**Sources:** FB-260415-190332-ee01 (logistics TZ), WhatsApp 2026-04-16 10:45-11:32 (customs TZ).

## Terminology

- **Route Segment** — row in `kvota.logistics_route_segments`; pricing unit per-invoice (one supplier's path from supplier→hub→…→client).
- **Segment Expense** — row in `kvota.logistics_segment_expenses`; freeform cost line inside a segment (СВХ, insurance, re-paperwork).
- **Operational Event** — row in `kvota.logistics_operational_events`; status marker per-deal (`gtd_uploaded`, `customs_cleared`, …), separate from pricing.
- **Route Template** — reusable segment chain (location types, not concrete locations) that a logistician can apply to prefill a new quote's route.
- **Entity Note** — row in `kvota.entity_notes`; polymorphic comment attached to a quote / customer / invoice / supplier with role-based visibility (`visible_to[]`).
- **Table View** — saved column visibility + ordering preset, org-wide or personal, per `table_key`.
- **Review Flag** — `invoices.logistics_needs_review_since` / `customs_needs_review_since`; raised by DB trigger when procurement changes invoice items in a way that may invalidate the already-completed logistics or customs pricing (smart delta).
- **Auto-assignment** — existing backend service (`route_logistics_assignment_service.py`) that matches `invoice.pickup_country → logistics_user` via wildcard patterns; fallback inbox for unmatched goes to `head_of_logistics`.
- **Head-only Views** — workspace tabs (Неназначенные, Все заявки, Маршруты) visible only to `head_of_logistics` / `head_of_customs` roles.

---

## Requirements

### Requirement 1: Assigned-based Workspace for logistics

**Objective:** As a logistician, I want a workspace page that shows only the invoices assigned to me with visual SLA timers, so that I immediately see what's on my plate without combing through the full quote list.

#### Acceptance Criteria

1.1 WHEN a user with role `logistics` visits `/workspace/logistics`, THEN the system SHALL display a table of invoices where `assigned_logistics_user = current user AND logistics_completed_at IS NULL`, sorted by `logistics_deadline_at ASC`.

1.2 WHEN the workspace page loads, THEN the table SHALL display columns: IDN, customer name + delivery city, route (pickup country → delivery city), cargo summary (items count + total weight + volume), `logistics_assigned_at` timestamp, SLA indicator, status badge, "Open" action button.

1.3 WHEN an invoice's `logistics_deadline_at` is more than 24 hours in the future, THEN its SLA indicator SHALL be displayed green; WHEN less than 24 hours, yellow ("Горит"); WHEN past deadline, red ("Просрочено") with the row background tinted warm-red.

1.4 WHEN an invoice's `logistics_needs_review_since IS NOT NULL`, THEN its status SHALL display the copper badge "Требует проверки" and the cargo column SHALL show inline diff pills (e.g. `950 → 1 150 кг`).

1.5 WHEN a user with role `head_of_logistics` visits `/workspace/logistics`, THEN the page SHALL additionally show tabs "Неназначенные" (invoices where `assigned_logistics_user IS NULL`), "Все заявки", and "Маршруты" (link to routing admin).

1.6 WHEN a regular `logistics` role user visits `/workspace/logistics`, THEN head-only tabs SHALL NOT be rendered and the server SHALL NOT return data for them (RLS enforced).

### Requirement 2: Assigned-based Workspace for customs

**Objective:** Symmetric to logistics workspace, for the customs team.

#### Acceptance Criteria

2.1 Identical to 1.1 — 1.6 with `customs` / `head_of_customs` roles and `assigned_customs_user` / `customs_*` timestamp fields.

2.2 WHEN a user has both `head_of_logistics` and `head_of_customs` roles, THEN a top-right role switcher SHALL appear that toggles the page content between the two workspaces without full navigation.

### Requirement 3: Auto-assignment on workflow entry

**Objective:** Ensure no invoice sits "nobody's" when it reaches the logistics + customs stage.

#### Acceptance Criteria

3.1 WHEN a quote transitions to `pending_logistics_and_customs`, THEN the system SHALL invoke `assign_logistics_to_invoices(quote_id)` synchronously, writing `assigned_logistics_user`, `logistics_assigned_at=NOW()`, `logistics_deadline_at=NOW() + logistics_sla_hours * interval '1 hour'` on every invoice.

3.2 WHEN the same quote transitions, THEN the system SHALL also invoke `assign_customs_to_invoices(quote_id)` which uses a **least-loaded** strategy (SELECT customs user with fewest open `assigned_customs_user = user AND customs_completed_at IS NULL`, deterministic tiebreak on user_id).

3.3 WHEN `assign_logistics_to_invoices` fails to match an invoice (no routing pattern or pickup_country is NULL), THEN `assigned_logistics_user` SHALL remain NULL and the invoice SHALL appear in `head_of_logistics`'s "Неназначенные" inbox.

3.4 WHEN an invoice is assigned, THEN the assignee SHALL receive a Telegram notification via the existing `telegram_service`.

### Requirement 4: SLA timers and escalation

**Objective:** Transparent, single-phase timers; no hidden "limbo" states.

#### Acceptance Criteria

4.1 WHEN an invoice is assigned, THEN `logistics_assigned_at` SHALL be set and the SLA timer SHALL start immediately. There SHALL NOT be a separate "Начать работу" action.

4.2 WHEN `NOW() > (logistics_deadline_at - interval '24 hours') AND logistics_completed_at IS NULL`, THEN the system SHALL send a reminder notification to the assignee (once per invoice).

4.3 WHEN `NOW() > logistics_deadline_at AND logistics_completed_at IS NULL`, THEN the system SHALL notify `head_of_logistics` (once per invoice).

4.4 WHEN SLA hours need to be changed, THEN the value SHALL be editable per-invoice (`logistics_sla_hours` column, default 72) without requiring deployment.

### Requirement 5: Logistics Route Constructor — per-invoice visual timeline

**Objective:** Replace the old 7-stage fixed model with a flexible per-invoice route builder.

#### Acceptance Criteria

5.1 WHEN a logistician opens the logistics step of a quote, THEN the page SHALL display a horizontal timeline of `logistics_route_segments` for the selected invoice, with draggable nodes (locations) and edges (segments) labeled with cost + days.

5.2 WHEN the quote has multiple invoices, THEN invoice tabs SHALL be displayed above the timeline, each showing per-invoice status (`● working` / `● completed`), and only the active invoice's route SHALL be editable.

5.3 WHEN the user drags a node between positions OR clicks a "+" between segments, THEN `sequence_order` SHALL be updated and a new `logistics_route_segments` row inserted, using 1-based sequential ordering per invoice.

5.4 WHEN the user clicks a segment (edge), THEN a details panel SHALL open below the timeline with inline-editable fields: `transit_days`, `main_cost_rub` (RUB), `carrier`, `notes`, and a list of `logistics_segment_expenses` with "Добавить расход" action (label + cost_rub + days).

5.5 WHEN the user selects a route template from the "Шаблон" dropdown, THEN the system SHALL create segments matching the template's location types (with placeholder locations to be chosen by the user), replacing any existing draft segments.

5.6 WHEN the user clicks "Сохранить как шаблон", THEN a new `logistics_route_templates` row SHALL be created with the current segments' from/to location types. Users with role `logistics` SHALL be able to CRUD their own templates; `head_of_logistics` / `admin` SHALL CRUD all org templates.

5.7 WHEN all invoices of a deal have `logistics_completed_at IS NOT NULL`, THEN the quote SHALL be eligible to advance to the next workflow state.

### Requirement 6: Operational events separated from pricing

**Objective:** Don't mix "gtd_uploaded" status with "first_mile cost" in one table.

#### Acceptance Criteria

6.1 The system SHALL expose `kvota.logistics_operational_events` as a separate table with per-deal scope, recording events like `gtd_uploaded`, `customs_cleared`, `delivered` with `status`, `event_date`, `notes`.

6.2 The old `logistics_stages` table SHALL NOT be written to by new code. Existing data is read-only for historical reports.

6.3 The calc engine SHALL read logistics pricing via the view `v_logistics_plan_fact_items` which aggregates new `logistics_route_segments` + `logistics_segment_expenses` into the legacy `plan_fact_items`-shaped rows the engine expects.

### Requirement 7: Customs handsontable — column consolidation

**Objective:** Fix the dual-schema problem (`customs_ds_sgr` text column vs structured `license_*` columns) and remove duplicated columns.

#### Acceptance Criteria

7.1 WHEN migration runs, THEN column `quote_items.customs_ds_sgr` SHALL be dropped (data migrated into `license_ds_required` / `license_ss_required` / `license_sgr_required` + `*_cost` columns by best-effort parser).

7.2 WHEN migration runs, THEN column `quote_items.customs_marking` SHALL be dropped (its data is duplicated by `customs_honest_mark`).

7.3 WHEN migration runs, THEN column `quote_items.customs_psn_pts` SHALL be renamed to `customs_psm_pts` (ПСН → ПСМ typo fix).

7.4 The customs handsontable UI SHALL display a single "Пошлина" column with a composite cell: numeric value + inline chip selector (`%` | `₽/кг` | `₽/шт`). The chip selects which storage column receives the value (`customs_duty` for %, `customs_duty_per_kg` for ₽/кг).

7.5 The customs page SHALL display a persistent disclaimer "Все суммы в таблице — в рублях ₽" in the toolbar.

7.6 The customs handsontable's internal mechanics (`hotRef`, `afterChange`, `cellsCallback`, `pendingOps` lock) SHALL be preserved; only column configuration and external wrapping change.

### Requirement 8: Customs autofill from history

**Objective:** Eliminate repetitive re-entry of HS codes and duty rates for items that have been cleared before.

#### Acceptance Criteria

8.1 WHEN the customs page loads, THEN the system SHALL POST `/api/customs/autofill` with the invoice's items (`brand + product_code`) and receive suggestion records (hs_code, customs_duty, license_*_required + _cost, etc.) from the most recent `quote_items` matching `(brand, product_code) WHERE hs_code IS NOT NULL` via LATERAL JOIN.

8.2 WHEN suggestions exist, THEN a banner SHALL be displayed above the handsontable showing the count ("N из M позиций автозаполнены") and source Q-numbers, with a primary CTA "Принять все предложения и завершить".

8.3 The "Принять все" CTA SHALL be disabled until the user checks "Сертификаты ДС/СС/СГР актуальны — проверил" checkbox.

8.4 WHEN the user accepts bulk autofill, THEN (a) all suggested values SHALL be written to the respective `quote_items` + `customs_*` columns, (b) `invoices.customs_completed_at = NOW()`, (c) a single `entity_notes` entry SHALL audit which historical Q-numbers were used.

8.5 Autofilled rows SHALL be visually distinct in the handsontable (light-blue row tint + ✨ sparkle icon in the № column with tooltip citing the source Q-number and fill date).

8.6 For partial autofill (some fields matched, others empty), the suggested fields SHALL be highlighted within the row while empty fields remain editable.

### Requirement 9: Customs expenses — per-item and per-quote

**Objective:** Capture customs-related costs that aren't per-item duties (broker fees, translations, testing).

#### Acceptance Criteria

9.1 The system SHALL expose `kvota.customs_item_expenses (quote_item_id, label, amount_rub, notes)` for per-item costs.

9.2 The system SHALL expose `kvota.customs_quote_expenses (quote_id, label, amount_rub, notes)` for per-quote costs (broker fees, DT filing).

9.3 The customs page SHALL display two cards below the handsontable: "Доп. расходы по позиции" (scoped to the currently-selected row) and "Общие расходы на КП", each with an inline add form.

9.4 A row action button (`↗` icon) in the handsontable SHALL open a Dialog with all item fields (including hidden-by-view columns + item-level expenses), allowing expanded editing.

### Requirement 10: Table views (saved column configs)

**Objective:** Allow customs users to hide irrelevant columns and switch between presets for different product categories.

#### Acceptance Criteria

10.1 The system SHALL expose `kvota.table_views (organization_id, user_id NULL|uuid, table_key, name, is_default, config jsonb)` where `user_id IS NULL` denotes org-wide views and `user_id = X` denotes personal views.

10.2 The customs page SHALL display a dropdown "Вид" in the toolbar listing the current user's views (personal + org-wide), plus "Настроить колонки" and "Создать новый вид" actions.

10.3 Org-wide views SHALL be CRUD-able only by `admin` or the role matching the table (`head_of_customs` for customs tables, `head_of_logistics` for logistics tables).

10.4 Personal views SHALL be CRUD-able only by their owner.

10.5 WHEN the user changes column visibility or order without saving, THEN the changes SHALL persist in local state but NOT in the database until the user saves as new or updates the current view.

10.6 WHEN the handsontable columns schema changes (e.g. after migration B drops `customs_ds_sgr`), THEN existing views SHALL gracefully ignore unknown column keys without erroring.

### Requirement 11: Entity notes — polymorphic comments with RBAC

**Objective:** Single shared notes primitive used for MOZ→logistics, MOP→logistics, logistics-about-customer, logistics-for-invoice comments.

#### Acceptance Criteria

11.1 The system SHALL expose `kvota.entity_notes (entity_type, entity_id, author_id, author_role, visible_to TEXT[], body, pinned, created_at)`.

11.2 The Logistics step's right panel SHALL display three note groups: МОЗ → логисту (quote-level), МОП → логисту (quote-level), заметка о клиенте (customer-level, persistent across all future quotes with this customer).

11.3 A note where `entity_type='customer'` and `visible_to=['logistics','customs','sales','admin','top_manager']` SHALL be readable by all listed roles and writable by `logistics`, `customs`, `admin`.

11.4 A note from logistics to the procurement team (`entity_type='invoice'`, `visible_to=['procurement','head_of_procurement']`) SHALL be created via a dedicated "Комментарий для КП поставщика" card in the Logistics step.

11.5 RLS policies SHALL enforce `visible_to` on SELECT (user must have one of the listed roles or `'*'`).

### Requirement 12: Smart delta — trigger-based review flags

**Objective:** When procurement changes items after logistics/customs already priced them, surface precisely what needs re-review.

#### Acceptance Criteria

12.1 The system SHALL create a DB trigger `invoice_items_change_trigger` on `kvota.invoice_items` firing AFTER INSERT/UPDATE/DELETE.

12.2 The trigger SHALL apply this matrix:

| Field change | `logistics_needs_review_since` | `customs_needs_review_since` |
|--------------|-------------------------------|------------------------------|
| `price_original`, `product_code`, `product_name`, `brand` | — | — |
| `quantity`, `total_weight`, `total_volume`, `packages_count` | ✅ | — |
| `supplier_id` | ✅ | ✅ |
| INSERT / DELETE row | ✅ | ✅ |

12.3 Flags SHALL only be raised when `logistics_completed_at IS NOT NULL` (no point flagging work not yet done).

12.4 When flag is raised, a `logistics_operational_events` row SHALL be inserted with `event_type='procurement_data_changed'` and a JSON diff for audit.

12.5 WHEN a logistician views an invoice with `logistics_needs_review_since IS NOT NULL`, THEN a yellow banner SHALL display the diff and the "Завершить расценку" button SHALL be disabled until the user clicks either "Подтвердить без изменений" (clears flag) or edits any segment (auto-clears flag).

### Requirement 13: Admin routing — Logistics tab

**Objective:** Close the UI gap — `route_logistics_assignments` backend exists but has no Next.js management UI.

#### Acceptance Criteria

13.1 The page `/admin/routing` SHALL add a new tab "Логистика" accessible to `admin` and `head_of_logistics`.

13.2 The Logistics tab SHALL display: (a) stats strip (5 cards: logisticians count, patterns count, coverage %, unassigned invoice count), (b) unassigned invoices list (if any) with inline "Назначить логиста" action, (c) patterns table sorted exact-first then by wildcard count.

13.3 The patterns table SHALL display columns: specificity badge (Точный/Wildcard), origin chip (flag + country), destination chip, assigned user (avatar + name + email), usage count ("N за месяц"), row actions (edit, delete).

13.4 A side panel "Новый маршрут" SHALL provide fields: origin country dropdown (or `*`), destination city dropdown (or `*`), logistics manager dropdown. Live preview of the resulting pattern SHALL be shown.

13.5 A "Coverage warnings" card SHALL list countries present in active invoices but without a matching pattern, with one-click "Добавить" that prefills the side panel.

### Requirement 14: `head_of_customs` role

**Objective:** Add a missing role symmetric to `head_of_logistics`.

#### Acceptance Criteria

14.1 Migration SHALL insert `head_of_customs` into `kvota.roles` for every existing organization, idempotently.

14.2 All permission checks that reference `head_of_logistics` SHALL additionally consider `head_of_customs` where the domain is customs (e.g. unassigned customs inbox, customs routing tab).

14.3 One user MAY have both `head_of_logistics` and `head_of_customs` via the existing `user_roles` many-to-many, with UI role-switcher toggling workspace context.

### Requirement 15: Locations — typed by role

**Objective:** Replace boolean `is_hub` / `is_customs_point` with a `location_type` enum that also supports the new "own warehouse" concept.

#### Acceptance Criteria

15.1 Migration SHALL add `kvota.locations.location_type VARCHAR(20) NOT NULL DEFAULT 'hub'` with CHECK constraint `location_type IN ('supplier', 'hub', 'customs', 'own_warehouse', 'client')`.

15.2 Migration SHALL backfill `location_type` from existing booleans: `is_customs_point=true → 'customs'`, `is_hub=true AND is_customs_point=false → 'hub'`, all others → default `'hub'` (manual review recommended).

15.3 `is_hub` and `is_customs_point` columns SHALL be preserved (not dropped) for backwards compat with `search_locations()` RPC for six months, then removed in a follow-up migration.

15.4 Location pickers in the Route Constructor SHALL filter by `location_type` based on context (segment start from node of type X allows destination only of certain types).

### Requirement 16: RBAC hardening — hide finance from logistics

**Objective:** Logisticians and customs users must not see financial data.

#### Acceptance Criteria

16.1 Quote detail page tabs: the "Финансы" and "Валютные инвойсы" tabs SHALL NOT be rendered for users with roles `logistics` or `customs` (unless they also have `admin`, `finance`, or `top_manager`).

16.2 API endpoints returning financial data SHALL reject requests from users with only `logistics` / `customs` role via 403.

16.3 Existing RLS policies on `plan_fact_items`, `invoices` (`amount_*` columns) SHALL be audited to ensure logistics/customs role can only read logistics/customs-relevant columns (enforced via view if necessary).

---

## Out of scope (deferred)

- External vs Internal МОЛ split (pricing vs execution phase) — deferred to a separate spec.
- Carriers registry — deferred (user explicit "сейчас можно пропустить").
- Suppliers contacts with roles — moved to `/procurement` branch (see parent design spec §10).
- Auto-switch customs table view by product category — future enhancement.

## Open UX items (pending reviewer decision during implementation)

Three UX nuances with recommendations in parent design spec §11:
1. Customs "Пошлина" column — composite single column vs three parallel columns (recommendation: composite).
2. Customs expenses storage — dedicated tables vs JSON on quote_items (recommendation: dedicated tables, reflected in R9.1-9.2).
3. Row "expand" modal layout (recommendation: Dialog via `↗` icon, reflected in R9.4).

Reviewer may override during implementation; tasks will reflect final decision.
