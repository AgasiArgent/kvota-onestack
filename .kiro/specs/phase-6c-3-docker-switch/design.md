# Phase 6C-3 — Docker CMD switch to uvicorn (FINAL PR of Phase 6C)

**Date:** 2026-04-21
**Branch:** `feat/phase-6c-3-docker-uvicorn-switch`
**Base:** main @ 87b832d (after PR #51 cost-analysis archive)
**Status:** In progress

## Context

After PR #51 merged, main.py reached 7,176 LOC with **0 routes** (zero `@rt` and zero `@app.get` decorators). All FastHTML routes archived to `legacy-fasthtml/`. Docker is still running `python main.py` which invokes FastHTML's `serve()` wrapper around uvicorn. HEALTHCHECK hits `/login` which now returns 404.

This PR completes the strangler fig by flipping the default app from FastHTML-shell to pure FastAPI.

## Goals

1. Docker CMD → `uvicorn api.app:api_app --host 0.0.0.0 --port 5001`
2. Dockerfile HEALTHCHECK → `/api/health` (already in docker-compose.prod.yml)
3. Relocate middleware (Sentry, SessionMiddleware, ApiAuthMiddleware) from main.py to api/app.py
4. Relocate shared helpers (build_calculation_inputs + deps) from main.py to `services/calculation_helpers.py`
5. Reduce main.py to a tiny backward-compat stub (`app = api_app`) for test imports
6. Zero production downtime

## Non-Goals

- Changing the `/api/*` URL contract (Next.js frontend expects this prefix)
- Modifying Next.js, Caddy, or any frontend routing
- Removing FastHTML from requirements.txt (still transitively needed by `btn` helper in `api/feedback.py` for legacy HTMX response)
- Cleaning up dead helpers in main.py (deferred to a future cleanup PR)

## Architecture

### Current (pre-6C-3)

```
main.py
├── Sentry init (L22-29)
├── fast_app()           ← FastHTML factory (internally installs SessionMiddleware)
├── ApiAuthMiddleware    ← L96
├── ... 7K lines of helpers + archived-route comments ...
├── build_calculation_inputs (L4844)  ← imported by api/quotes.py
├── btn helper (L3932)                ← imported by api/feedback.py
├── app.mount("/api", api_app)  ← FastAPI sub-app mounted at /api
└── serve(port=5001)

Docker CMD: python main.py
```

### Target (post-6C-3)

```
api/app.py
├── Sentry init
├── FastAPI() root app (api_app)
├── add_middleware(SessionMiddleware)  ← explicit, since FastAPI doesn't auto-install
├── add_middleware(ApiAuthMiddleware)
├── _api_sub = FastAPI(...)            ← existing sub-app with /health, /quotes, etc.
├── include_router(...) ... many
└── api_app.mount("/api", _api_sub)    ← preserves /api/* URL contract

main.py (30 lines)
└── from api.app import api_app as app   ← re-export for tests

services/calculation_helpers.py (new)
├── COUNTRY_NAME_MAP, EU_COUNTRY_VAT_RATES, EU_ISO_CODES, DIRECT_COUNTRY_ZONES
├── normalize_country_to_iso
├── resolve_vat_zone
├── _calc_combined_duty
└── build_calculation_inputs

Docker CMD: uvicorn api.app:api_app --host 0.0.0.0 --port 5001
```

## Why keep `/api` prefix (mount pattern)

Three reasons not to flatten `/api/health` → `/health`:

1. **Frontend contract**: Next.js calls `/api/*`, Caddy routes `/api/*` to Python container. Renaming would cascade through 20+ frontend files + Caddy config.
2. **Health check consistency**: `docker-compose.prod.yml` already checks `/api/health`. Changing would require two coordinated changes.
3. **Clean layering**: Middleware like `ApiAuthMiddleware` explicitly checks `path.startswith("/api/")` — flattening would break its guard.

The mount is just an internal detail now. FastAPI mounting another FastAPI is a normal pattern.

## File Changes

### New files

**`services/calculation_helpers.py`** — all calc-related main.py functions and constants.
Functions: `normalize_country_to_iso`, `resolve_vat_zone`, `_calc_combined_duty`, `build_calculation_inputs`.
Constants: `COUNTRY_NAME_MAP`, `EU_COUNTRY_VAT_RATES`, `EU_ISO_CODES`, `DIRECT_COUNTRY_ZONES`.
Imports: `calculation_mapper`, `calculation_models`, `services.currency_service`.

**`api/ui_helpers.py`** — FastHTML `btn` helper relocated from main.py (kept alive because `api/feedback.py` HTMX responses still use it).

### Modified files

**`api/app.py`** — expand from 55 lines to ~90 lines:
- Load dotenv
- Sentry init (moved from main.py L22-29)
- Split: rename current `api_app` to `_api_sub`; create new outer `api_app` wrapping it
- `api_app.add_middleware(SessionMiddleware, secret_key=os.getenv("APP_SECRET", ...))` — critical, 9+ endpoints read `request.session`
- `api_app.add_middleware(ApiAuthMiddleware)`
- `api_app.mount("/api", _api_sub)` — preserves URL contract

**`main.py`** — reduce from 7,176 to ~30 lines:
```python
"""OneStack — FastHTML shell retired 2026-04-21 in Phase 6C-3.
Application now runs as pure FastAPI: `uvicorn api.app:api_app`.
This stub re-exports app for test backward compatibility.
"""
from api.app import api_app as app  # noqa: F401 — re-export for tests
__all__ = ["app"]
```

**`Dockerfile`** — two lines:
```diff
- HEALTHCHECK ... CMD python -c "...'http://localhost:5001/login'"
+ HEALTHCHECK ... CMD python -c "...'http://localhost:5001/api/health'"
- CMD ["python", "main.py"]
+ CMD ["uvicorn", "api.app:api_app", "--host", "0.0.0.0", "--port", "5001"]
```

**`requirements.txt`** — add explicit pin:
```
uvicorn[standard]>=0.27.0
```
(FastAPI depends on uvicorn transitively, but explicit pin is good practice.)

**`api/quotes.py:92`** — update import:
```diff
- from main import build_calculation_inputs
+ from services.calculation_helpers import build_calculation_inputs
```

**`api/feedback.py:58, 85`** — update import:
```diff
- from main import btn
+ from api.ui_helpers import btn
```

**Test imports** — sweep:
```
tests/test_main_calc_entry_points.py:426: from main import build_calculation_inputs
```
→ update to `from services.calculation_helpers import build_calculation_inputs`

Other test imports of `from main import app` / `import main` — **no change needed**, the stub preserves them.

Test files that parse main.py source for `def build_calculation_inputs(...)` (e.g., tests/test_customs_page_fixes.py L69) — update to parse `services/calculation_helpers.py`.

## Risks

| Risk | Mitigation |
|------|-----------|
| SessionMiddleware not registered before route → `request.session` raises | Add `SessionMiddleware` to `api_app` BEFORE mount; localhost smoke test the Next.js flow |
| Sentry init before middleware → error handler chain breaks | Init Sentry at top of api/app.py, BEFORE app creation (same pattern as current main.py) |
| Circular import: `api.app` → `services.calculation_helpers` → something → `api` | Deps audit: `services/*` never imports from `api/*` |
| Test `from main import app` breaks | Keep main.py stub re-exporting `app = api_app` |
| uvicorn missing from requirements | Add explicit pin; also FastAPI pulls starlette+uvicorn |
| Container takes longer to start (healthcheck racy) | `start_period: 10s` in compose — verify uvicorn cold start ≤5s |
| Production deploy: SESSION_SECRET mismatch logs users out | APP_SECRET env var is same for FastHTML and FastAPI — no change |
| `legacy-fasthtml/*.py` archive files import `from main import COUNTRY_NAME_MAP, build_calculation_inputs, btn` | Archive files are `# flake8: noqa`, never imported at runtime — broken imports inside them are acceptable. Document in README. |

## Test Plan

1. `py_compile main.py && py_compile api/app.py && py_compile services/calculation_helpers.py`
2. Full pytest suite: `pytest tests/ -x --ignore=tests/test_customs_page_fixes.py` (that file parses source)
3. After parser updated: `pytest tests/test_customs_page_fixes.py`
4. Docker build: `docker build -t kvota-test .`
5. Docker run locally with env: `docker run -p 5001:5001 --env-file .env kvota-test`
6. `curl http://localhost:5001/api/health` → `{"success": true, "status": "ok"}`
7. `curl http://localhost:5001/api/openapi.json` → valid JSON with all routers
8. Browser test on localhost:3000 with Next.js pointed at local Python via `PYTHON_API_URL=http://localhost:5001`:
   - Login flow (sets session cookie)
   - Navigate to a page that triggers `/api/quotes/*` (verify JWT dual-auth works)
   - Navigate to `/api/changelog` (verify public path passes)
   - Feedback submit form (verify btn helper renders HTML)
9. Container logs: no Sentry errors, no middleware init errors

## Commit Strategy

Single commit, single PR.

**Commit title:**
```
feat(phase-6c-3): switch Docker to uvicorn, relocate middleware, retire main.py FastHTML shell
```

**PR body sections:**
- Summary (3 bullets)
- Architecture change (diagram before/after)
- File moves (table)
- Test plan checklist
- Deploy gate: STOP + CONFIRM before production

## Rollback

If production check fails:
1. `gh pr revert <PR_NUMBER> --head` → auto-create revert PR
2. Deploy reverts the Dockerfile CMD only (main.py stub can stay — it's harmless)
3. Manual: `ssh beget-kvota "cd /root/onestack && git checkout main.py Dockerfile && docker-compose restart onestack"`

Expected rollback time: <3 minutes.

## Success Criteria

- [ ] `curl kvotaflow.ru/api/health` returns 200 within 30s of deploy
- [ ] CI green
- [ ] No sentry errors during 5-minute post-deploy watch
- [ ] Existing Next.js pages load without regressions (dashboard, quotes, tasks)
- [ ] main.py reduced to ≤50 lines
