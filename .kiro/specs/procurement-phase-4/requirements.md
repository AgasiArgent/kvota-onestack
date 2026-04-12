# Requirements Document

## Introduction

Procurement Phase 4 for OneStack (Kvota quotation management system). This spec ships three reversible chunks that address four procurement team gaps: (1) no in-Kvota supplier communication channel, (2) manual VAT calculation on every item, (3) manual Russian-to-English document translation for 90% of suppliers, and (4) zero visibility into where quotes are stuck within the procurement phase.

Phase 3 (v0.6.0, shipped 2026-04-11) laid the foundation: shared CountryCombobox, CityCombobox, `invoices.pickup_country_code`, Incoterms 2020, MOQ column, and 5 new currencies. Phase 4 builds on that infrastructure — VAT lookup reads the new `pickup_country_code` column, bilingual documents reuse the geo components' `findCountryByName` helper, and the kanban page leverages the existing workflow state machine in `services/workflow_service.py`.

**Key principles:**

- **API-first** — all business operations (VAT lookup, send flow, approval gate, sub-status transitions) go through Python API endpoints callable by both the Next.js UI and AI agents (per `api-first.md` steering).
- **Symmetric audit** — every supplier communication commit (XLS download or letter draft send) writes an immutable history row, regardless of path. Re-sends always append, never overwrite.
- **Expand-contract for workflow** — the 331 existing `workflow_status` consumers remain untouched. Sub-statuses are a new column with its own state machine, not a modification of the existing enum.
- **Snapshot-at-capture for financial data** — VAT rates are written when the invoice is saved, never live-recomputed. Historical quotes are protected from policy changes.
- **Reusable patterns** — the sub-state machine in Phase 4c is designed as a generic `SubStateTransition` pattern that future departments (logistics, customs, spec control) can extend without redesign.

**Out of scope (explicitly deferred):**

- Full Next.js UI translation via `next-intl` — only bilingual document output (XLS + letter body).
- Time-based edit window (1-hour countdown) — replaced by simpler approval-only gate on post-send edits.
- HS-code-aware VAT lookup (10% preferential rates) — country-only in Phase 4.
- Admin-editable letter templates in DB — hardcoded constants in repo for Phase 4; upgrade later.
- Direct email sending from Kvota — deferred to Phase 5+ integrated mail system.
- AI agent for international product name translation.
- Multi-invoice letters covering multiple КП to the same supplier.
- Logistics/customs/spec-control sub-states — 4c builds the pattern; other departments use it in future phases.
- EAEU indirect VAT separate code path (0% for calculation is sufficient).

## Requirements

### Requirement 1: VAT Rates Reference Table

**Objective:** As a system administrator, I want a per-country VAT rate reference table seeded with current regulations, so that procurement officers and the VAT auto-fill feature have a single source of truth for import VAT rates.

#### Acceptance Criteria

1. The system shall provide a `kvota.vat_rates_by_country` table with columns: `country_code CHAR(2) PRIMARY KEY`, `rate NUMERIC(5,2) NOT NULL`, `notes TEXT`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `updated_by UUID REFERENCES auth.users(id)`.
2. When the migration is applied, the system shall seed the table with EAEU countries (RU, KZ, BY, AM, KG) at rate 0% and a default entry for all other countries at rate 20%.
3. The system shall expose a `GET /api/geo/vat-rate?country_code=X` endpoint that returns `{ "success": true, "data": { "country_code": "CN", "rate": 20.00 } }` for known countries and defaults to 20.00 for countries not explicitly in the table.
4. The VAT rate endpoint shall require authentication (JWT Bearer or session) and return HTTP 401 when called unauthenticated.
5. The VAT rate endpoint handler shall include a structured docstring with Path, Params, Returns, and Roles sections per `api-first.md`.

### Requirement 2: VAT Rates Admin UI

**Objective:** As an administrator, I want to view and edit per-country VAT rates through the admin panel, so that finance team can adjust rates when regulations change without requiring a code deployment.

#### Acceptance Criteria

1. The system shall render an admin page at `/admin/vat-rates` accessible to users with the `admin` role.
2. The admin page shall display all `vat_rates_by_country` rows in a table with columns: country code, country name (Russian), rate (%), notes, last updated, updated by.
3. When the admin edits a rate via inline editing, the system shall update the row through `PUT /api/admin/vat-rates` and reflect the change immediately in the table.
4. When a rate is updated, the system shall set `updated_at = NOW()` and `updated_by` to the acting user's ID.
5. The admin page shall not be accessible to non-admin roles. When a non-admin user navigates to `/admin/vat-rates`, the system shall return a 404 page.

### Requirement 3: VAT Auto-Fill on Invoice Creation

**Objective:** As a procurement officer creating a supplier invoice, I want the VAT rate to be auto-populated when I select the supplier's country, so that I don't have to look up and enter the rate manually for every invoice.

#### Acceptance Criteria

1. When the user selects a country via the CountryCombobox in the invoice create modal, the system shall call `GET /api/geo/vat-rate?country_code=X` and pre-fill the VAT rate field with the returned rate.
2. When the user manually edits the VAT rate field after auto-fill, the system shall preserve the manual override and not overwrite it on subsequent country changes (tracked via a `vat_manually_overridden` flag in component state).
3. When `vat_manually_overridden` is true, the system shall display a visual indicator (badge or icon) near the VAT field showing "manual" with a reset button that clears the override and re-fetches from the rates table.
4. When the invoice is saved, the system shall write the VAT rate as a snapshot value on the invoice items. The snapshot shall never be live-recomputed from the rates table — it protects historical quotes from policy changes.
5. When `invoices.pickup_country_code` is NULL (legacy invoices created before Phase 3), the VAT auto-fill shall silently skip without error or default — the field remains as the user set it.

### Requirement 4: Send Flow — XLS Download Path

**Objective:** As a procurement officer, I want to download the supplier КП as an XLS file so that I can attach it to my own email and send it to the supplier.

#### Acceptance Criteria

1. When an invoice has assigned items, the invoice card shall render a "Скачать XLS" (Download XLS) button visible to users with roles `procurement`, `admin`, or `head_of_procurement`.
2. When the user clicks "Скачать XLS", the system shall call `POST /api/invoices/{id}/download-xls` which generates an XLS file from the invoice and its assigned items.
3. The generated XLS shall include columns: brand, requested SKU, manufacturer SKU, manufacturer name, item name, quantity, MOQ, price (in invoice currency), production time, weight, dimensions, notes.
4. When XLS generation succeeds, the system shall write an `invoice_letter_drafts` row with `method='xls_download'`, `body_text=NULL`, `sent_at=NOW()`, and update `invoices.sent_at` via the `commit_invoice_send()` service function — all within a single transaction.
5. When XLS generation fails, the system shall not write any draft row or update `invoices.sent_at`, and shall return an error to the frontend.
6. The browser shall download the generated XLS file with a filename pattern `KP-{invoice_number}-{date}.xlsx`.

### Requirement 5: Send Flow — Letter Draft Composer

**Objective:** As a procurement officer, I want to compose a pre-filled letter to the supplier within Kvota, review it, save as a draft for later, and mark it as sent when I've emailed it, so that I have a record of what was communicated.

#### Acceptance Criteria

1. When the user clicks "Подготовить письмо" (Prepare Letter Draft) on the invoice card, the system shall open a letter draft composer UI.
2. The composer shall pre-populate from invoice, supplier, and user data: `recipient_email` from `supplier.email` (editable), `subject` from a template with the first 2-3 SKUs and the company name, `body_text` from a hardcoded Russian template with substituted fields: `{{greeting}}` (supplier contact person or "поставщик" fallback), `{{items_list}}` (formatted text list of assigned items with SKU, name, quantity, MOQ), `{{delivery_country}}`, `{{incoterms}}` (from `invoice.supplier_incoterms`), `{{currency}}`, `{{sender_signature}}` (user name, email, phone from auth profile).
3. When `supplier.email` is NULL, the recipient field shall display a placeholder "укажите email поставщика" and the "Отправить" button shall be disabled until the user enters an email.
4. When `supplier.contact_person` is NULL, the greeting shall fall back to "Уважаемый поставщик".
5. When the invoice has no assigned items, the items list section shall display "(позиции не указаны)".
6. When `auth.users.phone` is missing from the user's profile, the signature shall omit the phone line rather than showing an empty slash.
7. The user shall be able to edit any pre-filled field (recipient, subject, body) before saving or sending.
8. When the user clicks "Сохранить черновик" (Save Draft), the system shall write an `invoice_letter_drafts` row with `method='letter_draft'`, `sent_at=NULL`, and the current form data. At most one unsent draft per invoice shall exist at a time (enforced by partial unique index on `invoice_id WHERE sent_at IS NULL`).
9. When the user returns to a saved draft later, the composer shall load the saved data and allow further editing.
10. When the user clicks "Отправить" (Mark as sent), the system shall set `sent_at=NOW()` on the draft row AND update `invoices.sent_at` via `commit_invoice_send()`.

### Requirement 6: Send Flow — Audit Trail & History

**Objective:** As a procurement manager, I want a complete history of all communications sent to a supplier for a given invoice, so that I can trace what was sent, when, and by whom — including re-sends after edits.

#### Acceptance Criteria

1. Every commit action (XLS download or letter draft send) shall write an immutable row to `kvota.invoice_letter_drafts`. Sent rows shall never be updated or deleted.
2. When a user re-sends (after an approved edit), the system shall create a NEW draft row, not modify the previous sent row. The invoice shall accumulate a 1:N history of all sends.
3. The `invoice_letter_drafts` table shall include a `method` column with values `'xls_download'` or `'letter_draft'` to distinguish the communication path.
4. The `invoices.sent_at` column shall be a denormalized field always equal to `MAX(sent_at)` from the invoice's letter_drafts. It shall be maintained by the `commit_invoice_send()` service function.
5. The invoice detail view shall display a "История отправок" (Send History) section showing all sent rows for the invoice: date, method, created_by user name, language, and for letter drafts — the subject line.
6. The `invoice_letter_drafts` table schema shall use a partial unique index `ON (invoice_id) WHERE sent_at IS NULL` to ensure at most one active (unsent) draft per invoice.

### Requirement 7: Edit-After-Send Approval Gate

**Objective:** As a procurement officer, I want to be able to edit a sent invoice with approval from my manager, so that I can correct errors in what was communicated to the supplier while maintaining an audit trail.

#### Acceptance Criteria

1. When `invoices.sent_at IS NOT NULL`, any mutating API request to the invoice (update items, change fields) shall be blocked with HTTP 403 and error code `EDIT_REQUIRES_APPROVAL`.
2. When a sent invoice is displayed, the UI shall show an "Редактировать с одобрением" (Edit with approval) button instead of the normal edit controls.
3. When the user clicks "Редактировать с одобрением", the system shall call `POST /api/invoices/{id}/edit-request-approval` which delegates to `approval_service.create_approval()` with `approval_type='edit_sent_invoice'`.
4. Users with roles `head_of_procurement` or `admin` shall be able to approve the edit request. On approval, the invoice shall be temporarily unlocked for editing.
5. After the user completes their edits on an approved-for-edit invoice, the system shall prompt them to re-send the КП (via either XLS download or letter draft) to ensure the supplier receives the corrected version. A new row in `invoice_letter_drafts` shall be created on re-send.
6. The approval request and decision shall be recorded in the existing `kvota.approvals` table, preserving the full audit trail of who requested, who approved, and what was changed.

### Requirement 8: Bilingual XLS Export

**Objective:** As a procurement officer sending a КП to a non-Russian-speaking supplier, I want to generate the XLS with English column headers and item names, so that the supplier can read the document without manual translation.

#### Acceptance Criteria

1. The system shall provide a `kvota.quote_items.name_en TEXT NULL` column for storing English item names. Users fill it in manually; no AI translation is in scope.
2. When a user initiates a send action (XLS download or letter draft), the UI shall display a language toggle (RU / EN) allowing the user to choose the output language.
3. When English is selected and XLS is generated, the system shall use English column headers (Brand, Requested SKU, Manufacturer SKU, Item Name, Quantity, MOQ, Price, Lead Time, Weight, Dimensions, Notes) and the `name_en` field for item names.
4. When `name_en` is NULL for an item, the English XLS shall fall back to the Russian `name` field for that item — no block, no error, the row uses whatever name exists.
5. The letter draft `language` column shall record which language was used (`'ru'` or `'en'`), so the send history shows "sent in English on 12.04.2026".

### Requirement 9: Bilingual Letter Template

**Objective:** As a procurement officer, I want an English letter template alongside the Russian one, so that I can send a properly formatted English letter to international suppliers without translating manually.

#### Acceptance Criteria

1. The system shall provide a `LETTER_TEMPLATE_EN` constant in `services/letter_templates.py` alongside the existing `LETTER_TEMPLATE_RU`, using the same placeholder syntax and substitution fields.
2. When the user selects English (EN) as the language in the letter draft composer, the system shall render the composer with the English template pre-filled.
3. The English template shall use the same substitution fields as the Russian template: greeting, items list, delivery country, incoterms, currency, sender signature.
4. When the greeting substitutes a `contact_person`, it shall use an English-appropriate greeting ("Dear {name}" or "Dear Supplier" as fallback).

### Requirement 10: Procurement Sub-Status State Machine

**Objective:** As a system architect, I want a reusable sub-state pattern on top of the existing `workflow_status`, so that procurement can track granular progress within `pending_procurement` and the same pattern can be extended to other departments later.

#### Acceptance Criteria

1. The system shall provide a `kvota.quotes.procurement_substatus VARCHAR(30) NULL` column with a CHECK constraint ensuring sub-statuses are only valid when `workflow_status = 'pending_procurement'`.
2. The initial sub-states shall be: `distributing`, `searching_supplier`, `waiting_prices`, `prices_ready`. Additional sub-states may be added via follow-up migrations.
3. The system shall provide a `kvota.status_history` table with columns: `id UUID PK`, `quote_id UUID FK`, `from_status VARCHAR`, `from_substatus VARCHAR`, `to_status VARCHAR`, `to_substatus VARCHAR`, `transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, `transitioned_by UUID FK`, `reason TEXT NOT NULL`. Every sub-status transition shall write a row.
4. The `services/workflow_service.py` shall be extended with a `SubStateTransition` class (or equivalent pattern) that validates allowed transitions, enforces mandatory reason on backward moves, and writes history rows. This class shall be designed as a reusable pattern that can be instantiated for logistics, customs, or spec-control sub-states in future phases without architectural redesign.
5. The system shall expose `POST /api/quotes/{id}/substatus` accepting `{ "to_substatus": "...", "reason": "..." }`. For forward transitions, `reason` is optional. For backward transitions (e.g., `waiting_prices` → `searching_supplier`), `reason` is required — the endpoint shall return HTTP 400 if reason is missing on a backward move.
6. The system shall expose `GET /api/quotes/{id}/status-history` returning the full transition log for a quote.
7. When the migration is applied, all existing quotes with `workflow_status = 'pending_procurement'` shall be backfilled to `procurement_substatus = 'distributing'` as the default entry sub-state.
8. All 331 existing `workflow_status` consumers shall remain completely untouched. The sub-status is additive — no modification to the existing workflow_status enum, CHECK constraint, or transition logic.

### Requirement 11: Procurement Kanban Page

**Objective:** As a procurement officer, I want a kanban board showing my team's quotes organized by procurement sub-state, so that I can see at a glance where work is stuck and prioritize accordingly.

#### Acceptance Criteria

1. The system shall render a kanban page at `/procurement/kanban` with columns corresponding to the 4 procurement sub-states: Распределение (distributing), Поиск поставщика (searching_supplier), Ожидание цен (waiting_prices), Цены готовы (prices_ready).
2. Each card on the kanban shall display: quote identifier (IDN or number), customer name, days in current sub-state (computed from the most recent `status_history` entry for this sub-state), assignees, and a truncated reason for current state.
3. The system shall expose `GET /api/quotes/kanban?status=pending_procurement` returning quotes grouped by `procurement_substatus`, with computed `days_in_state` for each quote.
4. When a user drags a card from one column to another, the system shall call `POST /api/quotes/{id}/substatus` with the target sub-state. Forward moves shall proceed immediately. Backward moves shall prompt a dialog requiring a mandatory reason before completing the transition.
5. The kanban page shall be accessible to users with roles `procurement`, `admin`, and `head_of_procurement`. Users with other roles (including `sales`) shall not see the kanban page in navigation or be able to access it via direct URL.
6. Sales dashboards and other views that display `workflow_status` shall continue to show only the parent `pending_procurement` value — sub-statuses shall not leak to non-procurement roles.

### Requirement 12: Non-Regression Guarantees

**Objective:** Phase 4 extends infrastructure shipped in Phase 3 and touches the procurement workflow. These guarantees ensure backward compatibility.

#### Acceptance Criteria

1. Phase 3's dual-write pattern for `invoices.pickup_country` (legacy text) and `invoices.pickup_country_code` (ISO-2) shall continue to work unchanged. VAT auto-fill reads `pickup_country_code` but shall not modify or depend on `pickup_country`.
2. The existing `workflow_status` CHECK constraint (18 values, migration 135) and all transition logic in `workflow_service.py:ALLOWED_TRANSITIONS` shall remain unmodified.
3. The calculation engine files (`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`) shall not be modified.
4. The existing approval flow infrastructure (`services/approval_service.py`, `kvota.approvals` table) shall be extended, not replaced. New approval types (`edit_sent_invoice`) shall coexist with existing types.
5. All existing Python tests shall continue to pass after Phase 4 changes. The Phase 4 test suite shall include regression tests verifying that existing VAT manual entry, existing workflow transitions, and existing approval flows are not affected.
6. The letter draft `method` column shall use extensible values (`'xls_download'`, `'letter_draft'`) that allow Phase 5 to add `'email'` without schema changes.
