# Phase 6: FastHTML → FastAPI Migration — Task Breakdown

**Related:** [audit.md](audit.md) — endpoint inventory • [design.md](design.md) — architecture

## 6A: Audit — **COMPLETED** (2026-04-19)

Deliverable: [audit.md](audit.md) — 59 /api/* routes classified (32 Tier 1 mechanical, 14 Tier 2 extract, 11 Tier 3 HTML-only, 2 DEAD).

## 6B: Migrate JSON routes to FastAPI sub-app

Each sub-task = one self-contained PR. Sequencing matters: 6B-0 establishes foundation; 6B-1..6B-9 can run in any order but sharing main.py means sequential merge (avoid conflict). 6B-10 last.

### 6B-0: Foundation PR — `api/app.py` + first migration (IN PROGRESS)

**ClickUp task:** #30

**Changes:**
- Add `fastapi>=0.110.0` to `requirements.txt`
- Create `api/app.py` with `api_app = FastAPI(docs_url="/docs", openapi_url="/openapi.json")`
- Create `api/routers/__init__.py` + `api/routers/public.py`
- Move `/api/health` (3 lines) + `/api/changelog` (~19 lines) from main.py inline into `api/routers/public.py`
- In main.py: mount via `app.mount("/api", api_app)` after ApiAuthMiddleware, remove the 2 migrated @rt lines
- Test: `tests/test_api_app_mount.py` — health/changelog/docs/openapi.json all return 200

**Acceptance:** `pytest` green. Curl smoke: `/api/health` → `{"status":"ok"}`, `/api/docs` → 200 HTML, `/api/openapi.json` → JSON with `openapi` key.

### 6B-1: Admin router (Tier 1 mechanical)

**ClickUp task:** #31

**Endpoints (4):**
- `POST /api/admin/users` → `api/admin_users.py:create_user`
- `PATCH /api/admin/users/{user_id}/roles` → `api/admin_users.py:update_user_roles`
- `PATCH /api/admin/users/{user_id}` → `api/admin_users.py:update_user_status`
- `PUT /api/admin/vat-rates` → `api/geo.py:update_vat_rate`

**Changes:**
- Create `api/routers/admin.py` with APIRouter
- Add `@router.{method}(...)` decorators to existing api/* handler functions (import + wrap)
- `api_app.include_router(admin.router, prefix="/admin")`
- Remove @rt wrappers from main.py (lines ~48344-48354, ~48365)

**Acceptance:** Existing `tests/test_api_admin_users.py` passes unchanged. `/api/docs` shows 4 new endpoints under `admin` tag.

### 6B-2: Plan-fact + Deals routers (Tier 1)

**ClickUp task:** #32

**Endpoints (7):** plan-fact categories + items (6) + `/api/deals` POST.

**Same mechanical pattern as 6B-1.** Combined into one PR (smallest viable groups).

### 6B-3: Invoices router (Tier 1)

**ClickUp task:** #33

**Endpoints (7):** `/api/invoices/{id}/` download-xls, letter-draft GET/POST, letter-draft/send, letter-draft/{draft_id} DELETE, letter-drafts/history, procurement-unlock-request.

### 6B-4: Procurement + Composition routers (Tier 1)

**ClickUp task:** #34

**Endpoints (7):** kanban + substatus + status-history (procurement.py) + composition GET/POST + invoice verify + unlock-approval approve/reject.

**Decision point:** `composition.py` endpoints split across quotes and invoices routers per audit §Router Group Plan. Include in this PR for cohesion, OR split and defer the quote-composition endpoints to 6B-6 alongside quote actions. Choose at implementation time based on PR size.

### 6B-5: Soft-delete + Cron + Geo mix (Tier 1 + one Tier 2)

**ClickUp task:** #35

**Endpoints (5):**
- `/api/quotes/{id}/soft-delete` + `/restore` (Tier 1)
- `/api/cron/check-overdue` (Tier 1, external caller only)
- `/api/geo/vat-rate` (Tier 1)
- `/api/geo/cities/search` (Tier 2 — extract from main.py:34567 ~150 lines, uses `@app.get`)

### 6B-6: Quote actions (Tier 2 big)

**ClickUp task:** #36

**Endpoints (4) with INLINE bodies to extract:**
- `POST /api/quotes/{id}/submit-procurement` (~150L, main.py:10872)
- `POST /api/quotes/{id}/calculate` (~500L, main.py:14690 — the biggest)
- `POST /api/quotes/{id}/cancel` (~150L, main.py:15203)
- `POST /api/quotes/{id}/workflow/transition` (~150L, main.py:15358)

**Changes:**
1. Move handler bodies to `api/quotes.py` (new) as async functions
2. Create `api/routers/quotes.py` with @router decorators importing from api.quotes
3. Remove @rt wrappers from main.py
4. Keep existing composition endpoints where 6B-4 left them

**Sub-split option:** if PR > 600 lines diff, split calculate into its own PR (6B-6a) and the other three into 6B-6b.

### 6B-7: Chat + Feedback (Tier 2)

**ClickUp task:** #37

**Endpoints (2):**
- `POST /api/chat/notify` (~58L, main.py:26513)
- `POST /api/feedback` (~150L, main.py:26572) — dual form/JSON parser, preserve exact behavior

### 6B-8: Telegram + Internal feedback (Tier 2)

**ClickUp task:** #38

**Endpoints (2):**
- `GET /api/telegram/webhook` (main.py:26404) — external Telegram BotAPI webhook
- `POST /api/internal/feedback/{short_id}/status` (main.py:32424) — X-Internal-Key auth

Preserve: webhook body handling (default GET method + POST body semantics); custom header auth pattern.

### 6B-9: Documents + Customs (Tier 2 mechanical)

**ClickUp task:** #39

**Endpoints (3):**
- `GET /api/documents/{id}/download` — RedirectResponse 302, not JSON. Port the RedirectResponse explicitly.
- `DELETE /api/documents/{id}` (~50L, main.py:19834)
- `PATCH /api/customs/{id}/items/bulk` (~150L, main.py:23011)

### 6B-10: Dead endpoint cleanup

**ClickUp task:** #40

**Delete (verified DEAD):**
- `/api/procurement/{id}/check-distribution` (main.py:48450-48537) — no callers, docstring references non-existent file. Commit e042f2d planned but never wired up.

**Keep (verified ALIVE via FastHTML):**
- `/api/cities/search` — still called at main.py:9664, 12455 (hx_get), :18527 (fetch). Survive Phase 6C.
- `/api/procurement/{id}/complete` — called at main.py:18837 inline JS. Survive Phase 6C.
- `/api/procurement/{id}/invoices*` — called from FastHTML procurement page (@rt around main.py:19000+). Survive Phase 6C if that page lives.

**Final check before merge:**
- `git log -S "check-distribution"` shows no recent revival
- `rg "/api/procurement/[^/]+/check-distribution" --type-add 'web:*.{py,ts,tsx,js,html}'` → 0 hits outside main.py/handler

### 6B verification after all PRs merge

- `grep -c '@rt("/api/' main.py` drops from 58 to ~11 (Tier 3 HTMX only)
- `/api/openapi.json` has ≥ 43 endpoints
- Sentry error rate unchanged post-deploy
- No Next.js caller regression (verify via browser smoke on kvotaflow.ru key flows: calc, workflow transition, kanban, plan-fact, admin)

## 6C: Archive legacy FastHTML (separate initiative, post-6B)

**ClickUp task:** #29

Not scoped yet — plan when 6B completes. Summary of targets:
- Split main.py HTML routes into `legacy-fasthtml/{area}.py` by feature area
- Delete Tier 3 HTMX endpoints alongside parent pages
- Delete /api/cities/search + /api/procurement/{id}/complete + invoice handlers after their FastHTML callers die
- Evaluate Docker CMD switch to `uvicorn api.app:app`
- Target: main.py gone OR stub entrypoint only
