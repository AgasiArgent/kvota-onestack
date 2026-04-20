# Phase 6: FastHTML → FastAPI Migration — Requirements

**Status:** Draft (2026-04-19)

## Stakeholders

- **OneStack backend devs** — primary actors, implement and ship
- **AI agents** (LLM callers) — downstream consumers of the generated OpenAPI → MCP pipeline
- **Next.js frontend** — must continue functioning throughout without user-visible disruption

## User stories (EARS format)

### REQ-1: OpenAPI surface

As an AI agent developer, I want every JSON `/api/*` endpoint to appear in the auto-generated OpenAPI spec, so that MCP tools can be generated without hand-maintained schemas.

**Acceptance:**
- `GET /api/openapi.json` returns a valid OpenAPI 3.x JSON document.
- Every migrated endpoint is documented with path, method, and response shape placeholder (even before Pydantic models are added).
- Swagger UI at `/api/docs` renders the full list.

### REQ-2: Backwards compatibility

As the Next.js frontend, I want migrated endpoints to preserve their exact request/response contracts, so that no UI change is required during Phase 6B.

**Acceptance:**
- Every migrated endpoint returns the same JSON shape it did before migration.
- Status codes unchanged (200/201/400/401/403/404/409/500).
- No path changes — `/api/admin/users` stays `/api/admin/users`, not `/api/v1/admin/users`.
- No breaking change to auth (JWT forwarding via ApiAuthMiddleware).

### REQ-3: Incremental, safe rollout

As a backend dev, I want to ship each router migration as a standalone PR, so that bugs can be isolated and reverted quickly.

**Acceptance:**
- Each 6B-N PR is ≤ ~400 lines diff (per git-workflow guideline).
- Each PR passes CI in isolation (`pytest tests/ -v`).
- Reverting any one 6B-N PR does not break other merged PRs or the live app.
- Browser smoke on kvotaflow.ru after each merge confirms no regression.

### REQ-4: FastHTML coexistence during transition

As an operator, I want FastHTML pages (HTMX routes) to keep serving traffic during the entire 6B rollout, so that user-visible features are not disrupted by the migration.

**Acceptance:**
- FastHTML HTML routes continue to return their existing markup.
- FastHTML HTMX fragment routes (Tier 3) are NOT migrated in 6B — deferred to 6C.
- Dual-auth (JWT + session cookie) continues to work — FastHTML page users authenticated via cookie; Next.js via JWT.

### REQ-5: Dead code elimination

As the repo owner, I want confirmed-dead endpoints deleted rather than migrated, so that the code surface reflects reality.

**Acceptance:**
- Endpoints with zero callers (from Next.js and FastHTML) are deleted in 6B-10.
- Candidate-dead endpoints have ≥ 2 verification signals (no frontend grep match, no FastHTML hx-*/fetch match, no git log revival).

### REQ-6: Test continuity

As a backend dev, I want existing test suite to keep passing without test edits, so that regression protection remains intact.

**Acceptance:**
- No test file in `tests/test_api_*.py` needs editing for 6B-1..6B-9.
- New test `tests/test_api_app_mount.py` validates the FastAPI mount.
- Full `pytest tests/ -v` runs in ≤ 2 minutes on CI.

### REQ-7: Observability unchanged

As the on-call dev, I want Sentry and structured logs to keep capturing events from migrated endpoints with the same fidelity as before.

**Acceptance:**
- Sentry continues to capture exceptions from FastAPI handlers (sentry-sdk[starlette] instruments both frameworks).
- No new error-rate spike post-deploy for any 6B PR.
- Log format unchanged.

## Out of scope (for Phase 6)

- Pydantic model conversion (deferred, per endpoint later)
- Consolidating dual-auth into `Depends()` (deferred to Phase 7)
- Docker CMD change to uvicorn (Phase 6C)
- Caddy routing changes (Phase 6C if needed)
- Async DB session migration (not planned)
- Rate limiting on `/api/*` (not planned)

## Constraints

- **No breaking changes to JWT auth flow.** `request.state.api_user` populated by ApiAuthMiddleware must remain accessible in FastAPI handlers.
- **No Python version bump.** Stay on 3.12 (CI-pinned).
- **No dependency conflicts.** `fastapi` must coexist with `python-fasthtml` and `sentry-sdk[starlette]` without warnings.
- **Tier 3 endpoints stay in main.py.** Do not try to return FastHTML FT components from FastAPI.

## Success metrics

- All 43 migration-target endpoints (32 Tier 1 + 14 Tier 2 - duplicates) ported.
- Zero Sentry regressions across 10 post-deploy days.
- MCP tool generation proof-of-concept runs against `/api/openapi.json` — deferred to post-6C.
