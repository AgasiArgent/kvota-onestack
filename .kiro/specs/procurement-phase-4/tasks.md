# Implementation Plan — Procurement Phase 4

Tasks grouped by ship phase (4a → 4b → 4c) and architectural boundary within each phase. Parallel-capable tasks marked with `(P)`.

**Ship structure:**

- **Phase 4a** (Sections 1–5): VAT auto-detect + Send flow + Edit-after-send approval. Migrations 269–270. Ships first.
- **Phase 4b** (Section 6): Bilingual document output. Migration 271. Ships after 4a is validated on prod.
- **Phase 4c** (Sections 7–8): Procurement state machine + kanban page. Migration 272. Ships last.
- **Phase 4d** (Section 9): Verification, deploy, smoke test. Runs after each ship phase completes.

**Wave structure within Phase 4a:**

- Wave A1 (parallel): Sections 1, 2 — backend foundations (VAT service + send service). No frontend deps, independent file sets.
- Wave A2 (parallel, blocked on A1): Sections 3, 4, 5 — frontend wiring. All consume A1 services but touch disjoint component files.

---

## Phase 4a — Send Flow + VAT + Approval Gate

### 1. VAT Rates Backend — Migration, Service, and API

- [ ] 1.1 (P) Create migration 269 for `kvota.vat_rates_by_country` table with seed data
  - SQL file in `migrations/` — verify latest migration number before writing
  - Table: `country_code CHAR(2) PK`, `rate NUMERIC(5,2) NOT NULL DEFAULT 20.00`, `notes TEXT`, `updated_at TIMESTAMPTZ`, `updated_by UUID`
  - Seed: EAEU (RU, KZ, BY, AM, KG) at 0%, 10 major import countries at 20%
  - Apply on dev Supabase, regenerate `database.types.ts`
  - _Requirements: 1.1, 1.2_

- [ ] 1.2 (P) Implement `services/vat_service.py` with rate lookup and admin CRUD
  - `get_vat_rate(country_code)` → returns rate from DB, defaults to 20.00 for unknown countries
  - `list_all_rates()` → all rows for admin display
  - `upsert_rate(country_code, rate, notes, user_id)` → insert/update, sets `updated_at` and `updated_by`
  - Python tests: lookup known/unknown countries, default fallback, EAEU=0, upsert correctness
  - _Requirements: 1.3, 2.3, 2.4_

- [ ] 1.3 Add `GET /api/geo/vat-rate` and `PUT /api/admin/vat-rates` endpoints
  - Extend `api/geo.py` (or `main.py` if no separate api/ dir yet) with VAT rate lookup
  - New `api/admin.py` for admin-only rate CRUD (or add to existing admin endpoints)
  - Auth: any authenticated user for GET, admin-only for PUT
  - Structured docstrings per `api-first.md`
  - Python tests: 200 with rate, 400 missing country_code, 401 unauth, admin role guard
  - _Requirements: 1.3, 1.4, 1.5, 2.3, 2.4, 2.5_

---

### 2. Send Flow Backend — Migration, Services, and API Endpoints

- [ ] 2.1 (P) Create migration 270 for `invoices.sent_at` and `invoice_letter_drafts` table
  - `ALTER TABLE kvota.invoices ADD COLUMN sent_at TIMESTAMPTZ`
  - Full `invoice_letter_drafts` table with `method`, `language`, `recipient_email`, `subject`, `body_text`, `sent_at` columns
  - Partial unique index for one active draft per invoice
  - Apply on dev Supabase, regenerate `database.types.ts`
  - _Requirements: 4.4, 5.8, 6.6_

- [ ] 2.2 (P) Implement `services/invoice_send_service.py` with commit, draft CRUD, and send history
  - `commit_invoice_send(invoice_id, user_id, method, ...)` → atomic write of letter_drafts row + update invoices.sent_at
  - `save_draft()`, `get_active_draft()`, `get_send_history()`, `is_invoice_sent()`, `check_edit_permission()`
  - Python tests: commit atomicity (mock DB), draft save/load round-trip, history ordering, is_sent check, edit permission logic
  - _Requirements: 4.4, 5.8, 5.10, 6.1, 6.2, 6.4, 7.1_

- [ ] 2.3 (P) Implement `services/xls_export_service.py` for invoice XLS generation
  - `generate_invoice_xls(invoice_id, language='ru')` → returns bytes using openpyxl
  - Columns: brand, requested SKU, manufacturer SKU, manufacturer name, item name, quantity, MOQ, price, production time, weight, dimensions, notes
  - Language param controls column headers (RU/EN) and item name field (`name` vs `name_en`)
  - Python tests: generate with mock data, verify column headers, verify file is valid XLSX, RU vs EN headers
  - _Requirements: 4.3, 8.2, 8.3, 8.4_

- [ ] 2.4 (P) Implement `services/letter_templates.py` with Russian template and render function
  - `LETTER_TEMPLATE_RU` constant with `{greeting}`, `{items_list}`, `{delivery_country}`, `{incoterms}`, `{currency}`, `{sender_name}`, `{sender_email}`, `{sender_phone}` placeholders
  - `render_letter(template_lang, context)` → `(subject, body_text)` using `str.format_map()` with defaultdict
  - Python tests: render with full context, render with missing fields (graceful defaults), subject format
  - _Requirements: 5.2, 5.4, 5.5, 5.6_

- [ ] 2.5 Add send flow API endpoints in `api/invoices.py`
  - `POST /api/invoices/{id}/download-xls` → generate XLS + commit + return file (transactional)
  - `GET /api/invoices/{id}/letter-draft` → fetch active draft
  - `POST /api/invoices/{id}/letter-draft` → create/update draft
  - `POST /api/invoices/{id}/letter-draft/send` → mark as sent (commit)
  - `DELETE /api/invoices/{id}/letter-draft/{draft_id}` → delete unsent draft
  - `GET /api/invoices/{id}/letter-drafts/history` → all sent rows
  - `POST /api/invoices/{id}/edit-request-approval` → delegate to approval_service
  - All endpoints: auth required, role-gated (procurement/admin/head_of_procurement), structured docstrings
  - Edit-after-send guard: mutating endpoints check `is_invoice_sent()` → 403 `EDIT_REQUIRES_APPROVAL`
  - Python tests: each endpoint happy path + auth/role errors + sent-invoice guard
  - _Requirements: 4.2, 4.4, 4.5, 5.8, 5.10, 6.1, 6.5, 7.1, 7.3, 7.4, 7.6_

---

### 3. VAT Admin UI

- [ ] 3.1 Create admin VAT rates page at `/admin/vat-rates` with CRUD table
  - New `app/admin/vat-rates/page.tsx` page shell with admin role guard
  - New `features/admin/ui/vat-rates-table.tsx` — table showing all rates with columns: country code, country name (Russian via findCountryByCode), rate, notes, last updated, updated by
  - Inline edit: click rate cell → input → save via PUT endpoint → optimistic update
  - New `entities/invoice/queries.ts` hook: `useVatRates()` for fetching all rates
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

---

### 4. VAT Auto-Fill on Invoice Create Modal

- [ ] 4.1 Wire VAT auto-fill into invoice-create-modal.tsx
  - Add `vatRate` and `vatManuallyOverridden` state
  - `useEffect` on `countryCode` change → call `/api/geo/vat-rate` → set `vatRate` (skip if manually overridden or country is null)
  - VAT rate input field with "manual" badge + reset button when overridden
  - On submit: pass `vat_rate` through to `createInvoice()` → mutation writes to `quote_items.vat_rate` for assigned items
  - Handle edge case: `pickup_country_code` is NULL (legacy invoices) → skip auto-fill silently
  - Frontend tests: auto-fill fires on country change, manual override preserves value, reset clears override, null country skips fetch
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

---

### 5. Send Flow Frontend — Invoice Card + Composer + History + Approval Gate

- [ ] 5.1 Add "Send КП" button group to invoice-card.tsx
  - Two buttons: "Скачать XLS" and "Подготовить письмо"
  - Visible when invoice has assigned items AND user has procurement/admin/head_of_procurement role
  - "Скачать XLS" → calls POST download-xls endpoint → triggers file download → shows toast on success
  - After send: display "Отправлено {date}" badge and "Send History" expandable section
  - When invoice is sent: hide normal edit controls, show "Редактировать с одобрением" button
  - _Requirements: 4.1, 4.6, 6.5, 7.2_

- [ ] 5.2 Implement letter-draft-composer.tsx with pre-fill and draft lifecycle
  - Opens as a side panel or dialog from "Подготовить письмо" button
  - Pre-populates: `recipient_email` from supplier, `subject` from template (first 2-3 SKUs + company), `body_text` from `LETTER_TEMPLATE_RU` with all substituted fields
  - Edge cases: null supplier.email → placeholder + send disabled, null contact_person → "поставщик" fallback, empty items → "(позиции не указаны)", missing phone → omit from signature
  - "Сохранить черновик" button → saves draft via POST endpoint
  - "Отправить" button → marks as sent via send endpoint → closes composer → refreshes invoice card
  - When active draft exists → pre-load saved data instead of template
  - New `entities/invoice/mutations.ts` functions: `saveLetterDraft()`, `sendLetterDraft()`, `deleteLetterDraft()`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

- [ ] 5.3 Implement send-history-panel.tsx showing all sent rows
  - Expandable panel on invoice card showing: date, method (XLS/Letter), created_by name, language, subject (for letter drafts)
  - New `entities/invoice/queries.ts` hook: `useSendHistory(invoiceId)`
  - Display "КП отправлено через скачивание XLS" for xls_download rows with null body
  - _Requirements: 6.3, 6.5_

- [ ] 5.4 Implement edit-approval-button.tsx for post-send edit requests
  - Button "Редактировать с одобрением" visible when `invoices.sent_at IS NOT NULL`
  - Click → calls POST edit-request-approval → shows toast "Запрос на одобрение отправлен"
  - When approved (poll or realtime): unlock invoice edit controls + prompt to re-send after changes
  - New `entities/invoice/mutations.ts` function: `requestEditApproval(invoiceId)`
  - _Requirements: 7.2, 7.3, 7.5_

---

## Phase 4b — Bilingual Document Output

### 6. English Item Names + Bilingual XLS + English Letter Template

- [ ] 6.1 (P) Create migration 271 for `quote_items.name_en` column
  - `ALTER TABLE kvota.quote_items ADD COLUMN name_en TEXT`
  - Apply on dev Supabase, regenerate `database.types.ts`
  - _Requirements: 8.1_

- [ ] 6.2 (P) Add English letter template constant alongside Russian in `letter_templates.py`
  - `LETTER_TEMPLATE_EN` with same placeholder syntax, English text, "Dear {contact_person}" / "Dear Supplier" greeting
  - Extend `render_letter()` to select template by language param
  - Python tests: render EN template, verify English greeting and placeholders
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [ ] 6.3 Add RU/EN language toggle to send flow and wire bilingual XLS
  - Language toggle (RU / EN) on invoice-card.tsx send buttons and letter-draft-composer.tsx
  - Selected language passes to download-xls endpoint and letter template rendering
  - XLS English variant: English column headers + `name_en` field with fallback to Russian name when NULL
  - `invoice_letter_drafts.language` records which language was used in send history
  - Frontend tests: language toggle state, EN XLS column headers, fallback for missing name_en
  - _Requirements: 8.2, 8.3, 8.4, 8.5, 9.2_

- [ ] 6.4 Add `name_en` column to procurement handsontable
  - Add editable column in `procurement-handsontable.tsx` for English item name entry
  - Position: after Russian item name column
  - Column header: "Наим. (EN)" or similar
  - Save behavior: inline edit via existing handsontable bulk-update mechanism
  - _Requirements: 8.1_

---

## Phase 4c — Procurement State Machine + Kanban Page

### 7. Sub-Status State Machine Backend

- [ ] 7.1 (P) Create migration 272 for `procurement_substatus` column and `status_history` table
  - `ALTER TABLE kvota.quotes ADD COLUMN procurement_substatus VARCHAR(30)` with CHECK constraint
  - `CREATE TABLE kvota.status_history` with full audit schema
  - Backfill existing `pending_procurement` quotes to `distributing`
  - Apply on dev Supabase, regenerate `database.types.ts`
  - _Requirements: 10.1, 10.2, 10.3, 10.7, 10.8_

- [ ] 7.2 (P) Extend `services/workflow_service.py` with `SubStateTransition` reusable pattern
  - `SubStateTransition` dataclass mirroring `StatusTransition`: `parent_status`, `from_substatus`, `to_substatus`, `allowed_roles`, `requires_reason`
  - `PROCUREMENT_SUBSTATUS_TRANSITIONS` list with 6 transitions (3 forward, 3 backward requiring reason)
  - `transition_substatus(quote_id, to_substatus, user_id, user_roles, reason)` → validates, writes `status_history` row, updates `quotes.procurement_substatus`
  - Design as reusable: a future `LOGISTICS_SUBSTATUS_TRANSITIONS` list can plug into the same `transition_substatus()` function with different `parent_status`
  - Python tests: forward transition succeeds, backward without reason fails, invalid transition rejected, history row written, role-gate enforced
  - _Requirements: 10.4, 10.5, 10.8_

- [ ] 7.3 Add sub-status and kanban API endpoints
  - `GET /api/quotes/kanban?status=pending_procurement` → quotes grouped by substatus with computed `days_in_state` from latest status_history entry
  - `POST /api/quotes/{id}/substatus` → transition with reason (required for backward moves)
  - `GET /api/quotes/{id}/status-history` → full audit log ordered by `transitioned_at DESC`
  - Auth + role-gate: `procurement`, `admin`, `head_of_procurement`
  - Structured docstrings per `api-first.md`
  - Python tests: kanban grouping, transition happy path + backward-without-reason error, history retrieval
  - _Requirements: 10.5, 10.6, 11.3_

---

### 8. Procurement Kanban Page Frontend

- [ ] 8.1 Create kanban page at `/procurement/kanban` with board layout
  - New `app/procurement/kanban/page.tsx` page shell with role guard (procurement/admin/head_of_procurement)
  - New `features/procurement/ui/kanban-board.tsx` — 4 columns: Распределение, Поиск поставщика, Ожидание цен, Цены готовы
  - Column headers show count of quotes in each sub-state
  - Fetch data via `GET /api/quotes/kanban` endpoint
  - New `shared/lib/workflow-substates.ts` — constants mirroring Python sub-status values and labels
  - _Requirements: 11.1, 11.3_

- [ ] 8.2 Implement kanban cards with quote info and days-in-state
  - New `features/procurement/ui/kanban-card.tsx` — displays: quote identifier (IDN), customer name, days in current sub-state, assignees, truncated reason
  - `days_in_state` computed from the API response (server-side calculation from status_history)
  - Visual hierarchy: quote number prominent, customer name secondary, days badge, reason as tooltip
  - _Requirements: 11.2_

- [ ] 8.3 Implement drag-to-move with reason dialog for backward transitions
  - Install `@dnd-kit/sortable` dependency
  - Drag card between columns → calls POST substatus endpoint
  - Forward moves: immediate, no dialog
  - Backward moves: open `features/procurement/ui/substatus-reason-dialog.tsx` requiring mandatory reason text before completing the transition
  - Optimistic update with rollback on API error
  - _Requirements: 11.4_

- [ ] 8.4 Implement status history panel for quote audit trail
  - New `features/procurement/ui/status-history-panel.tsx` — timeline view of all transitions for a quote
  - Shows: from/to sub-status, date, actor name, reason
  - Accessible from kanban card (click to expand) or from quote detail page
  - New `entities/quote/queries.ts` hook: `useStatusHistory(quoteId)`
  - _Requirements: 10.6, 11.2_

- [ ] 8.5 Add kanban link to sidebar for procurement roles
  - Modify `widgets/sidebar/sidebar.tsx` — add "Канбан закупок" link under procurement section
  - Visible only to `procurement`, `admin`, `head_of_procurement` roles
  - Sales and other roles do not see the link or have access to the page
  - _Requirements: 11.5, 11.6_

---

## Phase 4d — Verification and Ship

### 9. Non-Regression Tests + Deploy

- [ ] 9.1 Run non-regression test suite for each phase before committing
  - Verify all existing Python tests pass after Phase 4 changes
  - Verify Phase 3 dual-write pattern still works (pickup_country + pickup_country_code)
  - Verify existing workflow transitions in workflow_service.py unaffected by sub-status addition
  - Verify existing approval flows work with new `edit_sent_invoice` type coexisting
  - Verify calculation engine files untouched (frozen files check)
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [ ] 9.2 Browser test each ship phase on localhost before pushing
  - Phase 4a: test VAT auto-fill on country change, test XLS download + sent_at set, test letter draft save/preview/send, test edit-after-send shows approval button, test admin VAT rates page
  - Phase 4b: test RU/EN toggle on send flow, verify English XLS has correct headers, verify name_en column in handsontable
  - Phase 4c: test kanban page loads with 4 columns, drag forward succeeds, backward prompts for reason, status history shows entries
  - _Requirements: all_

- [ ] 9.3 Commit each phase as a separate logical unit and push to main
  - Phase 4a: 1 commit with migrations 269-270 + backend services + frontend wiring
  - Phase 4b: 1 commit with migration 271 + bilingual features
  - Phase 4c: 1 commit with migration 272 + state machine + kanban
  - Wait for CI to pass and deploy to succeed between each phase
  - _Requirements: all_

---

## Requirements Coverage

| REQ | Tasks |
|---|---|
| 1 | 1.1, 1.2, 1.3 |
| 2 | 1.2, 1.3, 3.1 |
| 3 | 4.1 |
| 4 | 2.1, 2.3, 2.5, 5.1 |
| 5 | 2.1, 2.2, 2.4, 2.5, 5.2 |
| 6 | 2.2, 2.5, 5.3 |
| 7 | 2.2, 2.5, 5.1, 5.4 |
| 8 | 2.3, 6.1, 6.3, 6.4 |
| 9 | 2.4, 6.2, 6.3 |
| 10 | 7.1, 7.2, 7.3, 8.4 |
| 11 | 7.3, 8.1, 8.2, 8.3, 8.4, 8.5 |
| 12 | 9.1, 9.2, 9.3 |
