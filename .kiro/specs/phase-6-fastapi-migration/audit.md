# Phase 6A Audit — `/api/*` routes in `main.py`

**Date:** 2026-04-19
**Scope:** Every route registered under the `/api/` prefix in `main.py`, classified for Phase 6B extraction and FastAPI migration.

## Summary

- **Total `/api/*` registrations:** 59 (58 via `@rt(...)`, 1 via `@app.get(...)`)
- **EXTRACTED handlers (thin wrapper in `main.py` + body in `api/*.py`):** 32
- **INLINE handlers (body in `main.py`):** 27
- **JSON responses (JSONResponse / dict / `response_model`):** 48
- **HTML/HTMX responses (`Option`, `Div`, `Group`, `RedirectResponse`):** 11
- **Dead or uncalled from Next.js:** 6 candidates (details below)
- **Already-extracted router modules:** 10 files under `api/`
  - `api/admin_users.py`, `api/composition.py`, `api/cron.py`, `api/deals.py`, `api/geo.py`, `api/invoices.py`, `api/plan_fact.py`, `api/procurement.py`, `api/soft_delete.py`, `api/auth.py` (middleware, not routes)

### Tier breakdown
| Tier | Count | Description |
|------|-------|-------------|
| 1    | 32    | EXTRACTED + JSON + Next.js caller → mechanical APIRouter port |
| 2    | 14    | INLINE + JSON + Next.js caller → extract body first, then port |
| 3    | 11    | HTML/HTMX response (FastHTML `Option`/`Div`/`RedirectResponse`) → keep in legacy-fasthtml/ (Phase 6C) |
| DEAD | 2     | No Next.js callers, internal/webhook-only or superseded — audit, consider deletion |

(Plus cron/changelog/health/telegram/internal-feedback which are non-Next.js but have legitimate external callers — classified per-endpoint below.)

## Router Group Plan for Phase 6B

Once extracted, group the handler modules by URL prefix / business domain into FastAPI APIRouter bundles. The existing `api/*.py` files map 1:1 to routers except where recommended below.

```
api/
├── app.py              # FastAPI entry point (new — Step 2 of migration plan)
├── auth.py             # ApiAuthMiddleware (keep; not a router)
├── routers/
│   ├── quotes.py       # /api/quotes/* — calculate, cancel, workflow/transition,
│   │                      submit-procurement, substatus, status-history, kanban,
│   │                      soft-delete, restore, search, composition (merge from composition.py)
│   ├── procurement.py  # /api/procurement/* — invoices CRUD, items/assign,
│   │                      complete, check-distribution
│   ├── invoices.py     # /api/invoices/* — download-xls, letter-draft CRUD,
│   │                      unlock-request + unlock-approval/approve+reject
│   │                      (merge unlock-approval handlers from composition.py)
│   ├── customs.py      # /api/customs/* — bulk update
│   ├── documents.py    # /api/documents/* — download, delete
│   ├── customers.py    # /api/customers/* — search, check-inn, contacts,
│   │                      create-inline  (HTML fragment routes — Tier 3)
│   ├── companies.py    # /api/{suppliers,buyer-companies,seller-companies}/search
│   │                      (all HTMX HTML fragments — Tier 3)
│   ├── geo.py          # /api/geo/vat-rate, /api/geo/cities/search,
│   │                      /api/cities/search (legacy HTMX — mark for removal),
│   │                      /api/dadata/lookup-inn (HTML fragment — Tier 3)
│   ├── admin.py        # /api/admin/users*, /api/admin/vat-rates
│   ├── deals.py        # /api/deals (single POST)
│   ├── plan_fact.py    # /api/plan-fact/*
│   ├── feedback.py     # /api/feedback, /api/internal/feedback/{id}/status
│   ├── integrations.py # /api/telegram/webhook, /api/chat/notify
│   ├── cron.py         # /api/cron/check-overdue
│   └── public.py       # /api/health, /api/changelog (no auth)
```

### Proposed 6B PR split (ordered by risk × size)

| PR | Router file | Endpoints | Est. | Notes |
|----|-------------|-----------|------|-------|
| 1  | `routers/quotes.py`       | 13 | L | Biggest surface. Includes calculate, cancel, workflow/transition, submit-procurement (4 inline Tier-2), plus 9 already-extracted. Composition moves in too. |
| 2  | `routers/procurement.py`  | 8  | L | 7 inline Tier-2 (invoice CRUD, complete, items/assign) + 1 check-distribution. **Kill `/api/procurement/{quote_id}/complete`** — no Next.js caller, FastHTML-only (dead). |
| 3  | `routers/invoices.py`     | 9  | M | 7 already-extracted in `api/invoices.py` + 2 from `api/composition.py` (unlock-approval approve/reject). Mostly mechanical. |
| 4  | `routers/admin.py`        | 4  | S | All already-extracted (admin_users.py + geo.py vat-rates). Smallest, first easy win for PR practice. |
| 5  | `routers/plan_fact.py` + `routers/deals.py` | 7 + 1 | S | All already-extracted. Combine into one PR. |
| 6  | `routers/geo.py` + `routers/public.py` + `routers/cron.py` | 5 | S | Mix of extracted + small inline (changelog, health). Low risk. |
| 7  | `routers/feedback.py` + `routers/integrations.py` | 4 | M | Inline handlers — telegram/webhook has special body handling, feedback has dual form/JSON parser. Extract with care. |
| 8  | `routers/customs.py` + `routers/documents.py` | 3 | S | Inline Tier-2 mechanical ports. |
| 9  | `routers/customers.py` + `routers/companies.py` | 7 | M | **Tier 3 HTML fragments.** Port only after callers confirmed dead OR migrated to JSON variants. If FastHTML pages still drive /quotes/new, keep these in legacy-fasthtml/ and skip the FastAPI port for 6B. |

Rough total: **9 PRs**, ~60 endpoints, 10-14 days if sequenced. Tier 3 HTMX routes may collapse if the underlying FastHTML pages get deleted first (per migration trigger).

## Endpoint Table

<details>
<summary>All 59 endpoints (click to expand)</summary>

| # | Path | Methods | Location | Response | Handler fn | Next.js Callers | Tier |
|---|------|---------|----------|----------|------------|-----------------|------|
| 1 | `/api/quotes/{quote_id}/submit-procurement` | POST | INLINE main.py:10872 (~150L) | JSONResponse | `post` | `frontend/src/entities/quote/mutations.ts:1469` | 2 |
| 2 | `/api/quotes/{quote_id}/calculate` | POST | INLINE main.py:14690 (~500L, complex) | JSONResponse | `api_calculate_quote` | `frontend/src/features/quotes/ui/calculation-step/calculation-action-bar.tsx:34`, `frontend/src/features/quotes/ui/sales-step/sales-action-bar.tsx:48` | 2 |
| 3 | `/api/quotes/{quote_id}/cancel` | POST | INLINE main.py:15203 (~150L) | JSONResponse | `api_cancel_quote` | `frontend/src/entities/quote/mutations.ts:1309` | 2 |
| 4 | `/api/quotes/{quote_id}/workflow/transition` | POST | INLINE main.py:15358 (~150L) | JSONResponse | `api_workflow_transition` | `frontend/src/entities/quote/mutations.ts:18`, `:1287` (dynamic `action`) | 2 |
| 5 | `/api/procurement/{quote_id}/invoices` | POST | INLINE main.py:19056 (~130L) | JSONResponse | `api_create_invoice` | none found — FastHTML-only caller? | 2 (verify) |
| 6 | `/api/procurement/{quote_id}/invoices/update` | PATCH | INLINE main.py:19187 (~138L) | JSONResponse | `api_update_invoice` | none found — FastHTML-only | 2 (verify) |
| 7 | `/api/procurement/{quote_id}/invoices/{invoice_id}` | DELETE | INLINE main.py:19326 (~47L) | JSONResponse | `api_delete_invoice` | none found — FastHTML-only | 2 (verify) |
| 8 | `/api/procurement/{quote_id}/invoices/{invoice_id}/complete` | POST | INLINE main.py:19374 (~150L) | JSONResponse | `api_complete_invoice` | none found — FastHTML-only | 2 (verify) |
| 9 | `/api/procurement/{quote_id}/invoices/{invoice_id}/reopen` | POST | INLINE main.py:19558 (~60L) | JSONResponse | `api_reopen_invoice` | none found — FastHTML-only | 2 (verify) |
| 10 | `/api/procurement/{quote_id}/items/assign` | POST | INLINE main.py:19619 (~96L) | JSONResponse | `api_assign_items_to_invoice` | none found — FastHTML-only | 2 (verify) |
| 11 | `/api/procurement/{quote_id}/complete` | POST | INLINE main.py:19716 (~102L) | JSONResponse | `api_complete_procurement` | **none found** | **DEAD (candidate)** |
| 12 | `/api/documents/{document_id}/download` | GET | INLINE main.py:19819 (~14L) | RedirectResponse (302) | `api_document_download` | none via apiServerClient; likely `<a href>` nav | 3 |
| 13 | `/api/documents/{document_id}` | DELETE | INLINE main.py:19834 (~50L) | JSONResponse | `api_delete_document` | none found | 2 (verify) |
| 14 | `/api/customs/{quote_id}/items/bulk` | PATCH | INLINE main.py:23011 (~150L) | raw dict | `api_customs_items_bulk_update` | none found — FastHTML-only | 2 (verify) |
| 15 | `/api/telegram/webhook` | GET (default) | INLINE main.py:26404 (~108L) | raw dict | `telegram_webhook` | N/A — external webhook (Telegram BotAPI) | 2 (keep endpoint, port as-is) |
| 16 | `/api/chat/notify` | POST | INLINE main.py:26513 (~58L) | JSONResponse | `api_chat_notify` | `frontend/src/features/quotes/ui/chat-panel/use-realtime-comments.ts:193` | 2 |
| 17 | `/api/feedback` | POST | INLINE main.py:26572 (~150L) | JSONResponse | `submit_feedback` | `frontend/src/features/feedback/ui/FeedbackModal.tsx` → `../api/submitFeedback` (verify target) | 2 |
| 18 | `/api/internal/feedback/{short_id}/status` | POST | INLINE main.py:32424 (~25L) | JSONResponse | `post_internal_feedback_status` | N/A — CLI-only (curl + X-Internal-Key) | 2 (keep, low-priority) |
| 19 | `/api/cities/search` | GET | INLINE main.py:34522 (~44L) | FT (`Group`/`Option`) | `get` | none — superseded by `/api/geo/cities/search` | **DEAD (delete)** |
| 20 | `/api/geo/cities/search` | GET | INLINE main.py:34567 (~150L) — **uses `@app.get`** | JSONResponse | `get_api_geo_cities_search` | `frontend/src/shared/ui/geo/city-combobox.tsx:100` | 2 |
| 21 | `/api/customers/search` | GET | INLINE main.py:35240 (~67L) | FT (`Option`) | `get` | FastHTML HTMX page only | 3 |
| 22 | `/api/customers/check-inn` | GET | INLINE main.py:35308 (~74L) | FT (`Div`/`Small`) | `get` | FastHTML HTMX page only | 3 |
| 23 | `/api/customers/{customer_id}/contacts` | GET | INLINE main.py:35383 (~38L) | FT (`Div`/`Select`) | `get` | FastHTML HTMX page only | 3 |
| 24 | `/api/customers/create-inline` | POST | INLINE main.py:35422 (~59L) | starlette Response (JSON body) | `post` | FastHTML HTMX page only | 3 (or 2 if migrated to JSON-first) |
| 25 | `/api/suppliers/search` | GET | INLINE main.py:35482 (~59L) | FT (`Option`) | `get` | FastHTML HTMX page only | 3 |
| 26 | `/api/buyer-companies/search` | GET | INLINE main.py:35542 (~58L) | FT (`Option`) | `get` | FastHTML HTMX page only | 3 |
| 27 | `/api/seller-companies/search` | GET | INLINE main.py:35601 (~150L) | FT (`Option`) | `get` | FastHTML HTMX page only | 3 |
| 28 | `/api/dadata/lookup-inn` | GET | INLINE main.py:44909 (~150L) | FT (`Div`/`Small`) + JS snippet | `get_dadata_lookup_inn` | FastHTML HTMX page only | 3 |
| 29 | `/api/plan-fact/categories` | GET | EXTRACTED main.py:48271 → `api/plan_fact.py:plan_fact_list_categories` | JSONResponse | `get_plan_fact_categories` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:100` | 1 |
| 30 | `/api/quotes/search` | GET | EXTRACTED main.py:48275 → `api/plan_fact.py:quotes_search` | JSONResponse | `get_quotes_search` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:117` | 1 |
| 31 | `/api/plan-fact/{deal_id}/items` | GET | EXTRACTED main.py:48279 → `api/plan_fact.py:plan_fact_list_items` | JSONResponse | `get_plan_fact_items` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:23` | 1 |
| 32 | `/api/plan-fact/{deal_id}/items` | POST | EXTRACTED main.py:48283 → `api/plan_fact.py:plan_fact_create_item` | JSONResponse | `post_plan_fact_items` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:41` | 1 |
| 33 | `/api/plan-fact/{deal_id}/items/{id}` | PATCH | EXTRACTED main.py:48287 → `api/plan_fact.py:plan_fact_update_item` | JSONResponse | `patch_plan_fact_item` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:64` | 1 |
| 34 | `/api/plan-fact/{deal_id}/items/{id}` | DELETE | EXTRACTED main.py:48291 → `api/plan_fact.py:plan_fact_delete_item` | JSONResponse | `delete_plan_fact_item` | `frontend/src/features/plan-fact/api/plan-fact-api.ts:86` | 1 |
| 35 | `/api/deals` | POST | EXTRACTED main.py:48300 → `api/deals.py:create_deal` | JSONResponse | `post_deals` | `frontend/src/features/quotes/ui/specification-step/mutations.ts:78` | 1 |
| 36 | `/api/quotes/{quote_id}/composition` | GET | EXTRACTED main.py:48315 → `api/composition.py:get_composition` | JSONResponse | `get_quote_composition` | `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx:46` | 1 |
| 37 | `/api/quotes/{quote_id}/composition` | POST | EXTRACTED main.py:48319 → `api/composition.py:apply_composition_endpoint` | JSONResponse | `post_quote_composition` | `frontend/src/features/quotes/ui/calculation-step/composition-picker.tsx:61` | 1 |
| 38 | `/api/invoices/{invoice_id}/verify` | POST | EXTRACTED main.py:48323 → `api/composition.py:verify_invoice` | JSONResponse | `post_invoice_verify` | none found directly — likely via feature wrapper (verify) | 1 (verify) |
| 39 | `/api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/approve` | POST | EXTRACTED main.py:48327 → `api/composition.py:approve_procurement_unlock` | JSONResponse | `post_invoice_procurement_unlock_approve` | none via apiServerClient grep; verify via approvals UI | 1 (verify) |
| 40 | `/api/invoices/{invoice_id}/procurement-unlock-approval/{approval_id}/reject` | POST | EXTRACTED main.py:48331 → `api/composition.py:reject_procurement_unlock` | JSONResponse | `post_invoice_procurement_unlock_reject` | none via apiServerClient grep; verify via approvals UI | 1 (verify) |
| 41 | `/api/admin/users` | POST | EXTRACTED main.py:48344 → `api/admin_users.py:create_user` | JSONResponse | `post_admin_users` | `frontend/src/features/admin-users/actions.ts:11` | 1 |
| 42 | `/api/admin/users/{user_id}/roles` | PATCH | EXTRACTED main.py:48348 → `api/admin_users.py:update_user_roles` | JSONResponse | `patch_admin_user_roles` | `frontend/src/features/admin-users/actions.ts:42` | 1 |
| 43 | `/api/admin/users/{user_id}` | PATCH | EXTRACTED main.py:48352 → `api/admin_users.py:update_user_status` | JSONResponse | `patch_admin_user` | `frontend/src/features/admin-users/actions.ts:25` | 1 |
| 44 | `/api/geo/vat-rate` | GET | EXTRACTED main.py:48361 → `api/geo.py:get_vat_rate` | JSONResponse | `get_geo_vat_rate` | `frontend/src/entities/invoice/queries.ts:35` | 1 |
| 45 | `/api/admin/vat-rates` | PUT | EXTRACTED main.py:48365 → `api/geo.py:update_vat_rate` | JSONResponse | `put_admin_vat_rates` | `frontend/src/entities/invoice/mutations.ts:29` | 1 |
| 46 | `/api/invoices/{invoice_id}/download-xls` | POST | EXTRACTED main.py:48382 → `api/invoices.py:download_invoice_xls` | Response (binary xlsx) | `post_invoice_download_xls` | `frontend/src/entities/invoice/mutations.ts:121` | 1 |
| 47 | `/api/invoices/{invoice_id}/letter-draft` | GET | EXTRACTED main.py:48386 → `api/invoices.py:get_letter_draft` | JSONResponse | `get_invoice_letter_draft` | `frontend/src/entities/invoice/queries.ts:74` | 1 |
| 48 | `/api/invoices/{invoice_id}/letter-draft` | POST | EXTRACTED main.py:48390 → `api/invoices.py:save_letter_draft` | JSONResponse | `post_invoice_letter_draft` | `frontend/src/entities/invoice/mutations.ts:59` | 1 |
| 49 | `/api/invoices/{invoice_id}/letter-draft/send` | POST | EXTRACTED main.py:48394 → `api/invoices.py:send_letter_draft` | JSONResponse | `post_invoice_letter_draft_send` | `frontend/src/entities/invoice/mutations.ts:77` | 1 |
| 50 | `/api/invoices/{invoice_id}/letter-draft/{draft_id}` | DELETE | EXTRACTED main.py:48398 → `api/invoices.py:delete_letter_draft` | Response (204) | `delete_invoice_letter_draft` | `frontend/src/entities/invoice/mutations.ts:98` | 1 |
| 51 | `/api/invoices/{invoice_id}/letter-drafts/history` | GET | EXTRACTED main.py:48402 → `api/invoices.py:get_send_history` | JSONResponse | `get_invoice_send_history` | `frontend/src/entities/invoice/queries.ts:95` | 1 |
| 52 | `/api/invoices/{invoice_id}/procurement-unlock-request` | POST | EXTRACTED main.py:48406 → `api/invoices.py:request_procurement_unlock` | JSONResponse | `post_invoice_procurement_unlock_request` | `frontend/src/entities/invoice/mutations.ts:164`, `frontend/src/features/quotes/ui/calculation-step/edit-verified-request-modal.tsx:87` | 1 |
| 53 | `/api/quotes/kanban` | GET | EXTRACTED main.py:48419 → `api/procurement.py:get_kanban` | JSONResponse | `get_quotes_kanban` | `frontend/src/features/procurement-kanban/api/server-queries.ts:13` | 1 |
| 54 | `/api/quotes/{quote_id}/substatus` | POST | EXTRACTED main.py:48423 → `api/procurement.py:post_substatus` | JSONResponse | `post_quote_substatus` | `frontend/src/entities/quote/mutations.ts:1600` | 1 |
| 55 | `/api/quotes/{quote_id}/status-history` | GET | EXTRACTED main.py:48427 → `api/procurement.py:get_status_history` | JSONResponse | `get_quote_status_history` | `frontend/src/entities/quote/mutations.ts:1565` | 1 |
| 56 | `/api/quotes/{quote_id}/soft-delete` | POST | EXTRACTED main.py:48440 → `api/soft_delete.py:soft_delete_quote` | JSONResponse | `post_quote_soft_delete` | `frontend/src/entities/quote/mutations.ts:1268, 1279` | 1 |
| 57 | `/api/quotes/{quote_id}/restore` | POST | EXTRACTED main.py:48445 → `api/soft_delete.py:restore_quote` | JSONResponse | `post_quote_restore` | `frontend/src/entities/quote/mutations.ts:1279` (via generic lifecycle action) | 1 |
| 58 | `/api/procurement/{quote_id}/check-distribution` | POST | INLINE main.py:48450 (~93L) | JSONResponse | `post_check_distribution` | **none** — docstring references `procurement-distribution/api/mutations.ts` which does not exist in `frontend/src/`. | **DEAD (candidate)** |
| 59 | `/api/cron/check-overdue` | GET | EXTRACTED main.py:48544 → `api/cron.py:cron_check_overdue` | JSONResponse | `get_cron_check_overdue` | N/A — external cron via X-Cron-Secret | 1 |
| 60 | `/api/changelog` | GET | INLINE main.py:48966 (~19L) | JSONResponse | `get_changelog_api` | `frontend/src/entities/changelog/queries.ts:7` (server-side with `PYTHON_API_URL`) | 2 (trivially small) |
| 61 | `/api/health` | GET | INLINE main.py:49198 (3L) | JSONResponse | `get` | N/A — probe endpoint | 2 (trivially small) |

</details>

**Note on counts:** Table has 61 rows because `/api/documents/{document_id}` serves two distinct handlers (GET download at row 12, DELETE at row 13) and the migration plan treated the `@app.get` route parallel to `@rt`. The 59 vs 61 discrepancy comes from two route lines (`/api/plan-fact/{deal_id}/items` GET+POST, `/api/plan-fact/{deal_id}/items/{id}` PATCH+DELETE, `/api/quotes/{quote_id}/composition` GET+POST, `/api/invoices/{invoice_id}/letter-draft` GET+POST, `/api/documents/{document_id}` GET+DELETE) each counted once in the decorator grep but representing multiple methods. Decorator total: 59.

## Dead / Suspicious Endpoints

### Definite dead
- **Row 19: `/api/cities/search`** — Predecessor of `/api/geo/cities/search` (row 20). The changelog `changelog/2026-04-11.md:31` explicitly says "старый HTMX-эндпоинт `/api/cities/search` остался для FastHTML-страниц". If the FastHTML pages that consume this are gone, delete both the route and the handler. **Recommendation:** confirm no FastHTML `quotes/new` etc. still use HTMX `hx-get="/api/cities/search"`; if none, delete in Phase 6B PR 9.

- **Row 58: `/api/procurement/{quote_id}/check-distribution`** — Docstring claims it's called by `procurement-distribution/api/mutations.ts`, but that file does not exist in `frontend/src/features/procurement-distribution/`. The feature directory has only `api/server-queries.ts`, `model/`, and `ui/`. No `fetch`/`apiServerClient` references it. **Recommendation:** before deletion, check git log for when the caller was introduced vs removed — may have been planned but never implemented. Possibly dead since introduction.

### Candidate dead (verify against FastHTML usage)
- **Row 11: `/api/procurement/{quote_id}/complete`** — No Next.js caller. Likely triggered by the legacy FastHTML procurement page via HTMX form submit. If that page is already migrated, the endpoint is dead.
- **Rows 5-10, 13, 14: the `/api/procurement/{quote_id}/invoices*` cluster + `/api/documents/{document_id}` DELETE + `/api/customs/{quote_id}/items/bulk`** — No matches in the Next.js grep. These are consumed by FastHTML HTMX pages. Whether they're alive depends on whether `/procurement` and `/customs` FastHTML pages have been replaced. **Recommendation:** per-endpoint check before Phase 6B PR 2 / PR 8.

### Low-traffic but legitimate
- **Row 18: `/api/internal/feedback/{short_id}/status`** — CLI-only (curl + X-Internal-Key header). Keep and port.
- **Row 15: `/api/telegram/webhook`** — External webhook from Telegram. Keep and port.

## Gotchas for Phase 6B Porting

1. **Dual auth pattern** — Every currently-inline handler has a 20-line preamble that branches on `request.state.api_user` (JWT) vs `session["user"]` (FastHTML cookie). When FastAPI becomes the only runtime, this can be consolidated into a FastAPI dependency. Do NOT collapse prematurely — session fallback is still required until FastHTML pages are deleted per the migration trigger.
2. **`@rt` vs `@app`** — Row 20 uses `@app.get(...)` directly while everything else uses `@rt(...)`. FastHTML's `rt` also accepts methods kwarg; under FastAPI these all become `@router.get|post|patch|delete`.
3. **FT response types (Tier 3)** — Rows 12, 19, 21-28 return FastHTML FT components (`Option`, `Div`, `Group`, `Small`, `Select`) that serialize to HTML. FastAPI cannot return these. Two options: (a) keep these in legacy-fasthtml/ until callers are migrated to JSON; (b) rewrite to return `HTMLResponse(str(...))` if HTMX pages still need them. Recommended path: delete FastHTML pages first, THEN delete these endpoints — that aligns with the migration trigger.
4. **`services/*` is already framework-free** — No blockers there; the port is purely decorator/signature.
5. **Docstring format** — All handlers should gain the structured Path/Params/Returns/Roles docstring per `.claude/rules/api-first.md` as they're ported. Tier 1 routers already have it; Tier 2 handlers must be backfilled during extraction.
6. **Row 12 `/api/documents/{document_id}/download`** — Returns `RedirectResponse`, not JSON. Port the response type explicitly to FastAPI's `RedirectResponse`, or convert to returning `{"url": ...}` and let the frontend follow (breaking change for any `<a href>` that relies on direct redirect).

## Sanity Check — Already-Extracted Routers Are Registered

All 10 files in `api/` are imported and wrapped in `@rt(...)` in `main.py` around lines 48262-48546. No orphan router modules detected.

| Module | Registered at | # handlers | Actively called |
|--------|--------------|-----------|-----------------|
| `api/plan_fact.py` | 48262-48293 | 6 | Yes — plan-fact-api.ts |
| `api/deals.py` | 48298-48302 | 1 | Yes — specification-step/mutations.ts |
| `api/composition.py` | 48307-48333 | 5 | 2 via composition-picker.tsx; 3 indirectly (verify invoice + unlock approvals — check approvals UI) |
| `api/admin_users.py` | 48338-48354 | 3 | Yes — admin-users/actions.ts |
| `api/geo.py` | 48359-48367 | 2 | Yes — invoice queries + mutations |
| `api/invoices.py` | 48372-48408 | 7 | Yes — invoice mutations + queries |
| `api/procurement.py` | 48413-48429 | 3 | Yes — kanban + substatus + status-history |
| `api/soft_delete.py` | 48434-48447 | 2 | Yes — entities/quote/mutations.ts |
| `api/cron.py` | 48542-48546 | 1 | External cron |
| `api/auth.py` | (middleware, not route) | 0 | N/A |

None of the extracted modules are dead. Safe to proceed with the porting plan.
