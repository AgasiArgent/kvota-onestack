# Technology Stack

## Architecture

**Current:** Python monolith (FastHTML + HTMX) serving server-rendered HTML with Supabase PostgreSQL backend.

**In progress:** Strangler fig migration to Next.js frontend. FastHTML pages are replaced one by one while the Python backend shrinks to a thin API layer. Both systems coexist during transition via Caddy path-based routing.

## Current Stack (FastHTML — shrinking)

- **Language:** Python 3.11+
- **Framework:** FastHTML (Starlette-based) — server-rendered HTML
- **Interactivity:** HTMX for partial page updates
- **CSS:** PicoCSS v2 + Tailwind CDN + DaisyUI v4
- **Entry point:** `main.py` (~49K lines, monolith)

## Target Stack (Next.js — growing)

- **Framework:** Next.js 15 (App Router)
- **Language:** TypeScript (strict mode)
- **UI:** shadcn/ui + Tailwind CSS v4
- **Data:** Supabase JS client (direct) + TanStack Query
- **Real-time:** Supabase Realtime (Postgres change subscriptions)
- **Charts:** Tremor or Recharts
- **Auth:** `@supabase/ssr` (Supabase Auth)
- **Architecture:** Feature-Sliced Design (FSD)

## Shared Infrastructure

- **Database:** Supabase PostgreSQL, schema `kvota` (never `public`)
- **Auth:** Supabase Auth (`auth.users` table shared by both stacks)
- **Deploy:** Docker on beget-kvota VPS, Caddy reverse proxy
- **CI/CD:** GitHub Actions — push to `main` auto-deploys
- **Domain:** kvotaflow.ru (app.kvotaflow.ru)

## Key Libraries (Python)

- `supabase-py` — DB client (configured with `schema="kvota"`)
- PostgREST — REST API over PostgreSQL (FK joins, filtering)
- Calculation engine — `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` (frozen, never modify)

## Development Standards

### Calculation Engine — Frozen

`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py` are **never modified**. If data schema changes, adapt in `build_calculation_inputs()` by mapping new field names to what the engine expects.

### Database Conventions

- Schema: always `kvota.*` — both Python (`schema="kvota"`) and JS client (`db: { schema: "kvota" }`)
- Role column: `r.slug` (never `r.code`) in RLS policies
- Migrations: sequential numbering (latest: 253), applied via `scripts/apply-migrations.sh` over SSH
- PostgREST FK joins: specify FK explicitly when ambiguous (`quotes!customer_id(name)`)

### Design System

Documented in `design-system.md`. Font: Inter. Blue primary palette with slate grays. Constrained spacing/type scales. No `transition: all`. No `transform: translateY()` on hover. BEM `.btn` classes. Design tokens to be ported to Tailwind config during migration.

### Python Pitfalls

- No `**kwargs` in POST handlers — FastHTML ignores untyped params. Use explicit typed params: `field_name: str = ""`
- Variables in GET handler are NOT available in POST handler — separate function scopes
- FK null safety: `(obj.get("fk_field") or {}).get("column", default)` — NOT `.get("fk", {}).get()`

## Development Environment

### Required Tools

- Python 3.11+ with venv
- Node.js 20+ (for Next.js frontend)
- Docker + Docker Compose
- SSH access to beget-kvota VPS

### Common Commands

```bash
# Python dev: python main.py (port 5001)
# Frontend dev: cd frontend && npm run dev (port 3000)
# Tests: pytest
# Deploy: git push origin main (auto via GitHub Actions)
# Migrations: ssh beget-kvota "cd ~/kvota-onestack && ./scripts/apply-migrations.sh"
# Logs: ssh beget-kvota "docker logs kvota-onestack --tail 50"
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migration strategy | Frontend-first strangler fig | Avoids refactoring code that will be deleted |
| Frontend framework | Next.js 15 (App Router) | Server components, streaming, best React ecosystem |
| Frontend architecture | Feature-Sliced Design (FSD) | Scales better than flat-by-type, enforces import boundaries |
| Data access (API-first) | Supabase direct for CRUD + Python API for business logic (see `api-first.md`) | Single source of truth — humans and AI agents use same API. CRUD stays direct for simplicity (no business logic = no Python layer needed) |
| Coexistence | Caddy path-based routing | Both apps on same domain, seamless UX |
| Python refactoring | Extract business ops to `/api/*` endpoints | Python becomes focused API service, not dying code |

---
_Document standards and patterns, not every dependency_
