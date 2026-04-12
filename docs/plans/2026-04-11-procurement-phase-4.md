# Procurement Phase 4 — Plan

**Date:** 2026-04-11
**Scope Mode:** HOLD
**Status:** Ready for specification (kiro spec-init)
**Depends on:** Phase 3 (v0.6.0, shipped 2026-04-11, commit d1fe852) ✅
**Blocks:** Phase 5 (integrated mail system needs `invoice_letter_drafts.method='email'` extension)

## Problem Statement

Procurement officers communicate with suppliers entirely outside Kvota (manual emails from Outlook), calculate VAT by hand on every quote item, translate all КП documents to English manually (90% of suppliers don't know Russian), and have zero visibility into where quotes are stuck within the procurement phase. Phase 4 addresses all four gaps: it builds the first in-Kvota supplier communication channel (send flow), automates VAT lookup by country, adds bilingual document output, and introduces a procurement kanban with auditable sub-state transitions.

## Scope Mode Rationale

HOLD: scope was shaped during an interactive premise challenge that reframed three of the four features (edit window → approval-only, full i18n → bilingual documents, kanban state machine → visibility-first with proven reusable pattern). What remains needs rigor on data models and UX, not more brainstorming.

## Ship Order

Three reversible chunks, each validated on prod before the next ships:

| Phase | Features | Estimate |
|---|---|---|
| **4a** | КП send flow (XLS download + letter draft buffer) + VAT auto-detect + edit-after-send approval gate | ~8-9 days |
| **4b** | Bilingual document output (English XLS + English letter template + `name_en` column) | ~2-3 days |
| **4c** | Procurement state machine + kanban (reusable sub-state pattern + audit trail + kanban page) | ~5-7 days |

**Total: ~15-19 days, 3 ship events.**

---

## Core Requirements

### Phase 4a — Send Flow + VAT + Approval Gate

**VAT auto-detection:**

1. A `kvota.vat_rates_by_country` table exists with columns: `country_code CHAR(2) PK`, `rate NUMERIC(5,2) NOT NULL`, `notes TEXT`, `updated_at TIMESTAMPTZ`, `updated_by UUID`. Seed data: EAEU countries (RU, KZ, BY, AM, KG) = 0%, all others default to 20%.
2. `GET /api/geo/vat-rate?country_code=X` returns `{ "success": true, "data": { "country_code": "CN", "rate": 20.00 } }`. Authenticated, follows API-first pattern matching `/api/geo/cities/search`.
3. Admin UI page at `/admin/vat-rates` displays all rates in a table with inline-edit capability. Accessible to `admin` role only.
4. Invoice create modal: when user selects a country via CountryCombobox, the frontend calls `/api/geo/vat-rate` and auto-fills the VAT rate field. If user manually overrides, the override is preserved (track `vat_manually_overridden: bool` to prevent auto-fill from overwriting manual edits).
5. VAT rate is written as a snapshot at invoice save time. Never live-recomputed from the rates table — protects historical quotes from policy changes.

**Send flow:**

6. Invoice card renders a "Отправить КП" button group with two actions: "Скачать XLS" (Download XLS) and "Подготовить письмо" (Prepare Letter Draft). Visible to `procurement`, `admin`, `head_of_procurement`.
7. **Download XLS path:** generates an XLS file from invoice + assigned items data, downloads to user's browser, AND writes an `invoice_letter_drafts` row with `method='xls_download'`, `body_text=NULL`, `sent_at=NOW()`. Updates `invoices.sent_at` via `commit_invoice_send()` service function.
8. **Letter draft path:** opens a composer UI pre-filled from invoice/supplier/user data. Pre-populated fields: `recipient_email` (from `supplier.email`, editable), `subject` (from template with SKU + company), `body_text` (from hardcoded Russian template with `{{greeting}}`, `{{items_list}}`, `{{delivery_country}}`, `{{incoterms}}`, `{{currency}}`, `{{sender_signature}}`). Edge cases: null `supplier.email` → blank with placeholder; null `contact_person` → fallback to "поставщик"; empty items → "(позиции не указаны)"; null `auth.users.phone` → omit from signature.
9. Letter draft can be saved without sending (`sent_at = NULL`). At most one unsent draft per invoice at a time (partial unique index). User can return to the draft later to review, edit, or send.
10. "Отправить" (Mark as sent) action on letter draft commits the invoice: writes `sent_at` on the draft row AND updates `invoices.sent_at` via `commit_invoice_send()`.
11. Every commit — regardless of XLS or letter draft path — writes an immutable row to `invoice_letter_drafts`. Sent rows are never overwritten. Re-sends after approved edits create NEW rows (1:N history with full audit trail).
12. `invoices.sent_at TIMESTAMPTZ NULL` is a denormalized column maintained by `commit_invoice_send()` service function. Always equals `MAX(sent_at)` from the invoice's letter_drafts. Kept for fast query filtering ("show me all unsent invoices").

**Approval gate for edit-after-send:**

13. When `invoices.sent_at IS NOT NULL`, any mutating request to the invoice is blocked at the API layer with `403 EDIT_WINDOW_EXPIRED` (or similar). No time window — ALL post-send edits require approval regardless of elapsed time.
14. Procurement officer can request approval via `POST /api/invoices/{id}/edit-request-approval`, which delegates to existing `approval_service.create_approval()` with `approval_type='edit_sent_invoice'`.
15. `head_of_procurement` (and `admin`) can approve the request. On approval, the invoice is temporarily unlocked for editing. After edits, user re-sends via either path (new row in letter_drafts).

**Data model — `invoice_letter_drafts`:**

16. Table schema:
    ```sql
    CREATE TABLE kvota.invoice_letter_drafts (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      invoice_id UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
      created_by UUID NOT NULL REFERENCES auth.users(id),
      language CHAR(2) NOT NULL DEFAULT 'ru' CHECK (language IN ('ru', 'en')),
      method VARCHAR(20) NOT NULL CHECK (method IN ('xls_download', 'letter_draft')),
      recipient_email TEXT,
      subject TEXT,
      body_text TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      sent_at TIMESTAMPTZ NULL
    );
    CREATE UNIQUE INDEX idx_invoice_letter_drafts_one_active
      ON kvota.invoice_letter_drafts(invoice_id) WHERE sent_at IS NULL;
    ```

### Phase 4b — Bilingual Document Output

17. `kvota.quote_items.name_en TEXT NULL` column exists. Users fill it in manually; no AI translation in scope.
18. XLS export supports a `language` parameter. English variant uses English column headers (Brand, SKU, Description, Qty, MOQ, Price, etc.) and `name_en` for item names. Falls back to Russian name when `name_en IS NULL` — no block, just uses what exists.
19. Letter body has an English template (`LETTER_TEMPLATE_EN` constant in `services/letter_templates.py`) alongside the Russian one. Same placeholders, different text.
20. Both send paths (Download XLS and Prepare Letter Draft) show a RU/EN language toggle. Selected language flows through to XLS generation and template selection.
21. Letter draft `language` column records which language was used. History shows "sent in English on 12.04.2026, re-sent in Russian on 14.04.2026".

### Phase 4c — Procurement State Machine + Kanban

22. `kvota.quotes.procurement_substatus VARCHAR(30) NULL` column with CHECK constraint ensuring valid `(workflow_status, procurement_substatus)` pairs. Sub-statuses are only valid when `workflow_status = 'pending_procurement'`.
23. Initial sub-states: `distributing`, `searching_supplier`, `waiting_prices`, `prices_ready`. More may be added later via follow-up migrations.
24. `kvota.status_history` table records every transition: `(id, quote_id, from_status, from_substatus, to_status, to_substatus, transitioned_at TIMESTAMPTZ, transitioned_by UUID, reason TEXT NOT NULL)`. Every transition writes a row — free audit trail forever.
25. `services/workflow_service.py` extended with a `SubStateTransition` class built as a REUSABLE pattern. The pattern extends to `logistics_substatus`, `customs_substatus`, etc. in future phases without redesign.
26. API endpoints: `GET /api/quotes/kanban?status=pending_procurement` (grouped by substatus), `POST /api/quotes/{id}/substatus` (transition with mandatory reason on backward moves), `GET /api/quotes/{id}/status-history`.
27. Kanban page at `/procurement/kanban` with 4 columns. Cards show: quote identifier, days in current sub-state, reason for current state, assignees, last-updated timestamp.
28. Drag-to-move interaction. Forward moves are allowed freely. Backward moves prompt for a mandatory reason (Russian audit culture requirement).
29. Role gating: `procurement`, `admin`, `head_of_procurement` see the kanban page and can transition sub-states. `sales` and other roles see only the parent `workflow_status` — no kanban page access, no sub-status visibility.
30. Existing 331 `workflow_status` consumers remain completely untouched. Expand-contract: new column, new table, zero modifications to existing code.
31. Migration backfills all existing `pending_procurement` quotes to `distributing` as the default entry sub-state.

---

## Deferred Items

| # | Item | Rationale | Returns when |
|---|---|---|---|
| 1 | Admin-editable letter templates (DB table) | YAGNI; hardcoded templates ship in 4a | Procurement requests hot-swap without deploys |
| 2 | Per-user saved letter templates | No evidence each officer needs own style | Users ask for it |
| 3 | AI agent for international product names | User explicitly said out of scope | Separate initiative, Phase 5+ |
| 4 | Direct email from Kvota (integrated mail) | User: "sometime later we'll add mail system" | Phase 5+ as `method='email'` |
| 5 | Full Next.js UI translation via next-intl | Replaced with narrower bilingual document output | Non-Russian users need to navigate the UI |
| 6 | Time-based edit window (1-hour countdown) | Dropped; approval-only is cleaner and simpler | Never |
| 7 | HS-code-aware VAT lookup (10% preferential) | Country-only in Phase 4; HS codes manual | Procurement encounters a 10% category |
| 8 | EAEU indirect VAT separate code path | KZ/BY/AM/KG = 0% for calculation purposes; mechanism distinction is informational only | EAEU imports become frequent enough to warrant |
| 9 | Auto-calculated deadline in letter | Speculative; YAGNI | Pattern emerges (procurement always types deadline) |
| 10 | Re-send marker ("Повторно...") | Speculative | Re-sends become frequent |
| 11 | Multi-invoice letters | Out of scope for 4a | Phase 5+ with integrated mail |
| 12 | Other department sub-states | 4c builds the reusable pattern; actual logistics/customs/spec-control sub-states are future | Per-department request |

---

## Key Decisions

| ID | Decision | Context |
|---|---|---|
| D1 | ПЭО = finance concept, not customs ТН ВЭД. Table named `vat_rates_by_country`. | User clarified 2026-04-11 |
| D2 | Country-only VAT lookup. No HS-code awareness. | User: "HS codes entered manually at later stages" |
| D3 | Hardcoded template constants + admin UI for VAT rates. Templates upgrade to DB later if needed. | Hybrid approach from /plan Q1 |
| D4 | 1-hour edit window is invoice-level, confirmed. Then dropped entirely in favor of approval-only. | User: "edit with approval is ok for now" |
| D5 | Send flow for КП does NOT exist today. Two paths built: XLS download + letter draft buffer. | Scope discovery 2026-04-11 |
| D6 | Ship order: 4a (send+VAT+approval) → 4b (bilingual) → 4c (kanban). Each validated on prod. | User: "b then a" (Phase 4 before DataTable rollout) |
| D7 | VAT lookup = server-side Python endpoint `/api/geo/vat-rate`. | API-first rule, matches Phase 3 pattern |
| D8 | VAT rate snapshot at capture, never live-recompute. | Stale-rate protection |
| D9 | i18n = bilingual document output only (XLS + letter), NOT Next.js UI translation. | User: "90% of suppliers don't know Russian, translation is done manually" |
| D10 | Kanban = Option 2 full state machine with `procurement_substatus` + `status_history` audit table. | User: "proven pattern for future use in other departments" |
| D11 | Letter template: hardcoded in repo. Upgrade to DB-backed if procurement asks. | /plan Q1, option A |
| D12 | Letter draft lifecycle: 1:N with soft history. Partial unique index ensures one active draft per invoice. | /plan Q2, option B |
| D13 | Letter pre-population: reasonable pre-fill from invoice/supplier/user data. Items list in body + attachment. | /plan Q3, option B |
| D14 | Commit semantics: every commit (XLS or draft) writes `invoice_letter_drafts` row. `invoices.sent_at` is denormalized. | /plan Q4, option B |
| D15 | EAEU VAT rate = 0% for calculation purposes (collected via declaration, not customs). | User confirmed 2026-04-12 |

---

## Open Questions (resolve during kiro spec-design)

- [ ] **VAT write target:** auto-fill writes to existing `quote_items.vat_rate` per item, or to a new `invoices.vat_rate` column? (Verify migration 229 schema during spec-design)
- [ ] **Approval service invoice support:** does `create_approval(quote_id, ...)` need an `invoice_id` parameter, or pass invoice context via `modifications` JSONB? (Check function signature)
- [ ] **XLS generation library:** add `openpyxl` to `requirements.txt` (server-side, matches API-first). Verify no existing XLS/XLSX dependency.

---

## Dream State Alignment

Every Phase 4 deliverable is a clean stepping-stone: `invoice_letter_drafts` extends to `method='email'` (Phase 5 mail); `SubStateTransition` pattern extends to logistics/customs (future departments); `vat_rates_by_country` extends to HS-code dimension (one ALTER); `LETTER_TEMPLATE_EN` constant upgrades to DB-backed templates (one import swap); `quote_items.name_en` becomes the AI translation target (zero schema change). No debt or detours identified.

## Implementation Notes

- **Migration atomicity:** each phase ships its own migrations (4a: 269-271, 4b: 272, 4c: 273-274). Check `ls migrations/ | tail -5` before generating — concurrent work may shift numbers.
- **Template substitution:** use `str.format_map()` with a defaultdict for missing keys. No Jinja2.
- **XLS download atomicity:** generate file first → on success, write drafts row + update `invoices.sent_at` in a single transaction → return file. If file gen fails, no row written.
- **Kanban DnD:** use `@dnd-kit/sortable` for drag interactions.
- **Feature flag:** ship send-flow UI buttons behind `NEXT_PUBLIC_SEND_FLOW_ENABLED` env var. Remove flag once stable on prod.
- **Rollback:** migrations are forward-only (applied to prod Supabase). Rollback = feature-flag the UI off, not schema reversal.
- **Backward compatibility:** Phase 3's `pickup_country_code` dual-write pattern MUST keep working. VAT lookup reads the new column; if NULL (legacy invoices), VAT auto-fill silently skips (no error, no default).
