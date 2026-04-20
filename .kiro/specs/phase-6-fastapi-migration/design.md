# Phase 6: FastHTML → FastAPI Migration — Design

**Status:** Draft (2026-04-19), refined during 6B rollout
**Owner:** OneStack backend
**Related:** [audit.md](audit.md), [memory: project_fastapi_migration.md](../../../~/.claude/projects/-Users-andreynovikov-workspace-tech-projects-kvota-onestack/memory/project_fastapi_migration.md)

## Goal

Migrate OneStack's Python API surface from FastHTML's `@rt(...)` decorator (bound to FastHTML's HTML rendering system) to FastAPI's `@router.{method}(...)` decorators. This unlocks:

1. Auto-generated OpenAPI spec at `/api/docs` + `/api/openapi.json`
2. MCP tool definitions generated from OpenAPI
3. Runtime request validation via Pydantic models (progressive adoption)
4. Dependency injection for auth, DB sessions, role guards
5. A clean "main.py" that is no longer a 49K-line monolith

## Non-goals

- **No new business logic.** Every migrated endpoint preserves its existing request/response contract.
- **No Pydantic-first adoption.** Pydantic models are added progressively per endpoint; existing `request.json()` patterns are preserved during bulk migration.
- **No Docker entry-point switch.** `python main.py` remains the CMD until Phase 6C. FastAPI lives as a sub-app mounted on FastHTML.
- **No Caddy routing changes.** FastHTML and FastAPI share one Python process; Caddy sees one backend.
- **No auth refactor.** `ApiAuthMiddleware` stays on the outer FastHTML app. Dual-auth (JWT + session fallback) preserved per `.kiro/steering/strangler-fig-auth.md`.

## Architectural decisions

### D1: FastAPI as a mounted sub-app (not a parallel process)

**Decision:** Create `api/app.py` with `api_app = FastAPI(...)`. In `main.py`, mount via `app.mount("/api", api_app)` after `app.add_middleware(ApiAuthMiddleware)`.

**Rationale:**
- FastHTML internally extends Starlette; FastAPI extends Starlette. They share the same ASGI contract and can coexist in one process.
- Mounting keeps: one Docker container, one port (5001), one set of env vars, one deployment target.
- ApiAuthMiddleware on outer app still runs for `/api/*` because Starlette middleware processes scope *before* routing to mounted apps. `request.state.api_user` propagates to handlers inside the mounted app.
- Alternatives rejected: (a) parallel uvicorn process — adds ops surface; (b) route-level port split — Caddy churn; (c) full swap now — requires all 58 `@rt` migrated atomically.

**Routing precedence — CRITICAL:** Starlette matches routes in declaration order. `Mount` is a **prefix-owning** route: once registered, it claims the entire `/api/*` namespace ahead of anything declared later. Therefore `app.mount("/api", api_app)` MUST be declared **after** all legacy `@rt("/api/...")` handlers, not before. Placing it earlier shadows every non-migrated endpoint, returning 404 for paths FastAPI doesn't know about.

Concrete position in `main.py`: the mount lives at the bottom of the file, right before the `if __name__ == "__main__"` / run-server block (line ~49197 as of 6B-0). A banner comment + integration test (`tests/test_api_app_mount.py::TestLegacyRouteRegression`) guard against accidental reshuffle.

Verified in 6B-0 integration test: a mounted `/api/health` and a non-migrated `/api/quotes/kanban` coexist — the @rt route resolves first, the sub-app receives unmatched /api/* paths.

**Lesson learned (2026-04-20, 6B-0):** The initial plan placed the mount right after `app.add_middleware(ApiAuthMiddleware)` (line ~152). Smoke test showed every /api/quotes/kanban request returning 404 because the mount intercepted and FastAPI had no route. Fix: move mount to bottom of file. Document for future devs: **NEVER** move `app.mount("/api", api_app)` above any `@rt("/api/...")` handler. As handlers migrate to FastAPI in 6B-1..6B-9, their @rt lines are deleted from main.py and served by the mount. Once 6B-10 completes, the remaining @rt /api/* handlers are only Tier 3 (HTML) and stay above the mount until Phase 6C deletes them.

### D2: APIRouter per feature area

**Decision:** One `api/routers/{area}.py` file per business domain (quotes, procurement, invoices, admin, etc). Each file exposes `router = APIRouter(tags=[...])` and registers handlers. `api/app.py` calls `api_app.include_router(xxx.router, prefix="/xxx")` for each.

**Rationale:**
- Mirrors the existing `api/*.py` structure (one domain per file).
- Keeps routers small (≤200 lines each) — audit measured 27-150 lines per feature area.
- Prefix lives in `app.py`, not router — easier to re-mount under a version prefix (`/api/v2/...`) later.
- `tags=["..."]` drives OpenAPI section grouping for Swagger UI readability.

### D3: Handler function pattern (Starlette-compatible)

**Decision:** Handlers stay as `async def name(request: Request) -> JSONResponse:` signature. Decorators change from `@rt("/path", methods=["POST"])` to `@router.post("/path")`.

**Rationale:**
- Zero change to handler bodies. Existing tests (direct function call with MagicMock Request) keep working.
- Defers Pydantic adoption — 46 handlers migrate first with identical I/O shape, then per-endpoint Pydantic upgrade happens selectively.
- Response type preserved: `JSONResponse(...)`, `Response(..., media_type=...)`, `RedirectResponse(...)` all work identically under FastAPI.

### D4: Dual-auth preserved until Phase 6C

**Decision:** Handlers keep the 20-line preamble that branches on `request.state.api_user` (JWT) vs `session["user"]` (cookie). No FastAPI `Depends()` consolidation in 6B.

**Rationale:**
- FastHTML HTMX pages still exist in `main.py`. Some call the same `/api/*` endpoints via cookie session (not JWT). A FastAPI dependency that *requires* JWT would break those callers.
- Post-Phase-6C, when FastHTML HTML pages are gone and all /api/* callers use JWT, we can extract the preamble into `Depends(require_api_user)`. Tracked as Phase 7 (not scheduled).

### D5: Tier 3 (HTML/HTMX) endpoints stay in main.py

**Decision:** 11 endpoints returning FastHTML FT components (`Option`, `Div`, `Group`, `RedirectResponse`) are NOT ported to FastAPI in 6B. They remain `@rt(...)` in main.py.

**Rationale:**
- FastAPI cannot return FastHTML FT objects (they serialize via FastHTML's own renderer).
- These endpoints serve HTMX fragments to FastHTML pages. Both live or die together.
- Phase 6C deletes FastHTML HTML pages; these endpoints get deleted alongside them.
- If any Tier 3 endpoint is found to also serve Next.js callers, it gets rewritten to return JSON and migrates up to Tier 2.

### D6: DEAD endpoints deleted before migration, not after

**Decision:** Confirmed-dead endpoints (`/api/procurement/{id}/check-distribution`, `/api/cities/search`) are deleted in 6B-10 as a standalone PR, before the 6C archival.

**Rationale:**
- Avoids migrating code that will be deleted two weeks later.
- Smaller main.py = less refactoring surface.
- Verification before delete: (a) grep `frontend/src/` for path literal → 0 hits, (b) grep `main.py` for path string in JS literals → 0 hits, (c) `git log -S "<path>"` to confirm not recently introduced.

## PR sequencing (6B-0 → 6B-10)

See [audit.md §Router Group Plan](audit.md#router-group-plan-for-phase-6b) for router-to-endpoint mapping.

```
6B-0  Foundation         (2 endpoints — health + changelog)      SMALL
6B-1  Admin              (4 endpoints — Tier 1 mechanical)       SMALL
6B-2  Plan-fact + Deals  (7 endpoints — Tier 1)                  SMALL
6B-3  Invoices           (7 endpoints — Tier 1)                  MEDIUM
6B-4  Procurement + Composition  (7 endpoints — Tier 1)          MEDIUM
6B-5  Soft-delete + Cron + Geo   (5 endpoints — Tier 1 mix)      SMALL
6B-6  Quote actions      (4 endpoints — Tier 2 big extract)      LARGE
6B-7  Chat + Feedback    (2 endpoints — Tier 2 medium)           SMALL
6B-8  Telegram + Internal (2 endpoints — Tier 2 small)           SMALL
6B-9  Documents + Customs (3 endpoints — Tier 2 mechanical)      SMALL
6B-10 Dead cleanup       (2-3 endpoints — delete)                 SMALL
```

Total: ~43 endpoints migrated (excluding 11 Tier 3 that stay and 2-3 DEAD that get deleted).

## Phase 6C scope (follow-up initiative)

After 6B completes:
1. Split `main.py` HTML routes into `legacy-fasthtml/{area}.py` modules by domain.
2. Delete Tier 3 HTMX endpoints alongside their parent FastHTML pages.
3. Consider switching Docker CMD to `uvicorn api.app:app` *if* FastAPI can satisfy all remaining /api/* traffic and FastHTML's remaining surface is small enough to mount as a sub-app on FastAPI (inverted mount).
4. Delete `main.py` if all its responsibilities are distributed.

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Mount order bug — `@rt("/api/foo")` shadows mounted route | Low | 6B-0 integration test verifies coexistence; mount called before @rt registrations |
| Middleware scope lost — `request.state.api_user` not propagated into sub-app | Low | Starlette docs confirm scope shared; verified in 6B-0 |
| Test regression — existing MagicMock-based tests fail under FastAPI | Very low | Tests call handlers as functions, not via TestClient; decorator change is invisible |
| Frontend caller break — path changes | Zero | Paths preserved identically. Only decorator changes. |
| Swagger UI slow on 60 endpoints | Low | `redoc_url=None` + minimal descriptions until Pydantic phase |
| Dockerfile healthcheck breaks — hits `/login` not `/api/health` | Zero | Unchanged; both endpoints work |
| Sentry instrumentation lost | Low | sentry-sdk[starlette] instruments both FastHTML + FastAPI transparently |
| Pydantic model drift — response shape changes | N/A | No Pydantic in 6B; deferred to per-endpoint work |

## Success criteria

- [ ] 6B-0 merged: `api/app.py` exists, `/api/docs` renders Swagger UI, health + changelog return expected responses.
- [ ] 6B-1..6B-9 merged: each PR ships green CI + local curl smoke + no Next.js regression.
- [ ] 6B-10 merged: 2-3 DEAD endpoints deleted from main.py.
- [ ] `grep -c "@rt(\"/api/" main.py` drops from 58 to ~11 (Tier 3 remainders).
- [ ] `/api/openapi.json` lists at least 43 endpoints.
- [ ] Sentry shows no new error rate after each deploy.
- [ ] Existing test suite remains green after every PR (no test edits required beyond new FastAPI mount tests).
