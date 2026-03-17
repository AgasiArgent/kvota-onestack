# OneStack Frontend Migration — Strangler Fig Design

**Date:** 2026-03-10
**Status:** Approved
**Approach:** Frontend-first strangler fig migration from FastHTML to Next.js

---

## Problem

- `main.py` is 49K lines — a monolith mixing route handlers + HTML rendering
- FastHTML + HTMX limits UI capabilities (no real-time chat, no rich dashboards, limited interactivity)
- Single file prevents parallel development
- Need: real-time chat, beautiful dashboards, fast/responsive UI

## End State

Next.js frontend + thin Python API + direct Supabase access. FastHTML fully deleted.

---

## Architecture

### Frontend: Next.js 15 (App Router)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | Next.js 15 (App Router) | Server components, streaming, layouts |
| UI | shadcn/ui + Tailwind CSS | Owned source, customizable, matches existing Tailwind usage |
| Data | Supabase JS client + TanStack Query | Direct reads with caching, optimistic updates |
| Real-time | Supabase Realtime | Built-in Postgres change subscriptions, no extra infra |
| Charts | Tremor or Recharts | Data-heavy dashboard components |
| Auth | `@supabase/ssr` | Official Next.js App Router auth package |

### Frontend Structure: Feature-Sliced Design (FSD)

```
frontend/
├── app/                        # Next.js App Router (routing only, thin)
│   ├── layout.tsx
│   ├── (auth)/
│   ├── chat/
│   ├── dashboard/
│   └── ...
├── src/
│   ├── shared/                 # Layer 1: No business logic
│   │   ├── ui/                 # shadcn components, design system tokens
│   │   ├── lib/                # Supabase clients, Python API client, utils
│   │   ├── config/             # Env vars, constants
│   │   └── types/              # Generated DB types, shared interfaces
│   ├── entities/               # Layer 2: Business entities
│   │   ├── quote/              # Type, QuoteCard, useQuote
│   │   ├── customer/
│   │   ├── deal/
│   │   ├── user/
│   │   └── invoice/
│   ├── features/               # Layer 3: User actions
│   │   ├── chat/               # Send message, subscribe
│   │   ├── calculation/        # Trigger calc, display results
│   │   ├── approval/           # Approve/reject workflows
│   │   └── auth/               # Login, logout, session
│   ├── widgets/                # Layer 4: Composite UI blocks
│   │   ├── sidebar/
│   │   ├── dashboard-charts/
│   │   ├── quote-detail-tabs/
│   │   └── header/
│   └── pages/                  # Layer 5: Full page compositions
```

**FSD import rule:** Layers import only from layers below. `features/` → `entities/` → `shared/`. Never upward.

**App Router ↔ FSD boundary:** `app/` directory is outside the FSD hierarchy. Each `app/**/page.tsx` is a thin shell that imports a page composition from `src/pages/` (or directly from `src/widgets/` for simple pages). `app/` files have no FSD import restrictions — they are routing glue, not an FSD layer. All business logic, data fetching, and UI composition lives inside `src/`.

### Backend: Thin Python API

Added to existing FastHTML app under `/api/*` prefix. Only for operations that require server-side Python:

```
api/
├── __init__.py                # Router mounted at /api
├── calculation.py             # POST /api/calculate
├── workflow.py                # POST /api/quotes/{id}/transition, approvals
├── exports.py                 # GET /api/exports/quote-pdf/{id}, Excel, etc.
└── integrations.py            # POST /api/dadata/inn, Telegram, HERE
```

~500-800 lines extracted from existing JSON-returning handlers in main.py.

### Data Access Pattern

```
Next.js ──→ Supabase (direct, for CRUD reads/writes, RLS enforced)
Next.js ──→ Python API (for calculation, workflow, exports, integrations)
Python API ──→ services/ (existing business logic layer)
```

Most pages need only Supabase. Python API is called only for complex business operations.

### Auth

- Next.js uses Supabase Auth via `@supabase/ssr`
- FastHTML continues existing session-based auth (unchanged during migration)
- Both validate against same `auth.users` table
- Next.js → Python API calls include Supabase JWT as Bearer token
- Python API validates JWT for protected `/api/*` endpoints

**Auth bridge prerequisite (Phase 1):** FastHTML currently uses server-side sessions with no JWT awareness. Before any user-facing Next.js page goes live, the Python API must add JWT validation middleware for `/api/*` routes. This is scoped to Phase 1 (Foundation). Users navigating between FastHTML and Next.js pages will maintain separate sessions — FastHTML uses its cookie, Next.js uses Supabase JWT. Both authenticate against the same `auth.users` table, so the user identity is consistent even though the session mechanisms differ. Full auth unification (replacing FastHTML sessions with Supabase JWT) happens naturally when FastHTML is fully retired.

---

## Deployment

### Monorepo Structure

```
onestack/
├── main.py                    # Existing FastHTML (shrinks over time)
├── services/                  # Existing Python services (untouched)
├── api/                       # NEW: Thin JSON API layer
├── frontend/                  # NEW: Next.js app
└── docker-compose.prod.yml    # Updated: adds frontend container
```

### Docker

New container added to `docker-compose.prod.yml`:

```yaml
kvota-frontend:
  build: ./frontend
  restart: always
  environment:
    - NEXT_PUBLIC_SUPABASE_URL=...
    - NEXT_PUBLIC_SUPABASE_ANON_KEY=...
    - PYTHON_API_URL=http://kvota-onestack:8000
```

### Caddy Routing (path-based)

```
kvotaflow.ru {
    handle /api/* {
        reverse_proxy kvota-onestack:8000
    }
    handle /v2/* {
        reverse_proxy kvota-frontend:3000
    }
    handle /chat/* {
        reverse_proxy kvota-frontend:3000
    }
    handle /dashboard/* {
        reverse_proxy kvota-frontend:3000
    }
    handle /_next/* {
        reverse_proxy kvota-frontend:3000
    }
    handle {
        reverse_proxy kvota-onestack:8000
    }
}
```

### Coexistence Strategy

- **Early phases:** migrated pages use `/v2/` prefix (allows comparison with FastHTML version)
- **Later phases:** direct path takeover (Caddy route moves from FastHTML → Next.js)
- **Rule:** Delete FastHTML route + HTML helpers immediately when Next.js replacement is live. No dead code.

---

## Migration Order

| Phase | Pages | Risk | Notes |
|-------|-------|------|-------|
| 1. Foundation | Auth, layout, sidebar, FSD scaffold, design system, Supabase client | Zero | No user-facing changes |
| 2. Chat | `/chat/*` | Zero | New feature, pure addition |
| 3. Dashboard | `/dashboard/*` | Zero | New feature, built from scratch |
| 4. Simple pages | Customers, suppliers, training, settings | Low | Straightforward CRUD |
| 5. Medium pages | Deals, specs, invoices, admin | Medium | Some workflow logic |
| 6. Core workflow | Quotes list + detail, procurement, logistics, customs | Highest | Battle-tested patterns, migrate last |

By phase 6, all patterns are proven on simpler pages.

---

## Page-Specific Requirements (from User Feedback, 2026-03-17)

Requirements from real user feedback to incorporate during migration. Not just "replicate FastHTML" — improve.

### Phase 4: Customers

**Overview tab:**
- Move `notes` from CRM tab → Overview tab, editable inline
- Add `general_email` field (bulk mailing address, separate from contact emails) — short description of purpose

**CRM tab:**
- Contact phones: migrate from single `phone VARCHAR(50)` to `phones jsonb` array. Each entry: `{number, ext, label}` (рабочий, мобильный, добавочный). DB migration required.
- Contact form: full CRUD — create, edit, delete contacts inline
- Addresses: make editable (currently read-only in Next.js)
- Calls: add `assigned_to` field — manager can assign a call to another user
- Calls: show contact phone/email in call detail/list view (join through `contact_name` → `customer_contacts`)

**Documents tab:**
- Add Contracts section showing `customer_contracts` table (contract_number, contract_date, status)
- Contract number is used downstream for document generation (specs, invoices) — must be selectable
- Contracts CRUD: create/edit/delete with contract_number, date, status, notes

**Positions tab:**
- Show `sku` (артикул) and `idn_sku` as separate columns — users confuse them when displayed as one

**General (all tabs):**
- Responsive tables: horizontal scroll on narrow screens, or column priority hiding
- All data-display tables should handle gracefully at 1200px–1920px range (primary user screens)

### Phase 6: Quotes

- Registry: display manager full name (not ID)
- Remove "Отправить получателю" action button
- Keep validation/download button available on ALL quote stages (currently disappears on later stages)

### Phase 6: Procurement

Significant feature requests collected — requires separate spec document. Key themes:
- Restructured procurement info: priority (стандартно/быстрее/дешевле), end-user flag, tender flag
- Table columns redesign: brand, request SKU, manufacturer SKU, name, quantity, price, readiness, weight, dimensions (mm, not volume)
- Request distribution system: by brand assignment, manual, tender routing
- Positions registry with pricing (filterable by brand, manager, date)
- Cross-department chat on all workflow pages

---

## Python Changes (Minimal)

**Do:**
- Extract JSON-returning handlers into `api/` module (~500-800 lines)
- Add JWT validation middleware for `/api/*` routes
- Add any new API endpoints as Next.js pages need them

**Don't:**
- Don't split main.py into route modules (routes die as pages migrate)
- Don't refactor HTML rendering helpers (they die with FastHTML)
- Don't restructure services/ layer (already well-modularized: 47 files across domain boundaries)

**Note on Supabase schema:** The Next.js Supabase client must be configured to use the `kvota` schema (not `public`). All tables live in `kvota.*` and RLS policies reference `kvota.` prefixed tables. Set this in the Supabase client initialization.

---

## Key Decisions

| Decision | Choice | Alternative Considered |
|----------|--------|----------------------|
| Migration strategy | Frontend-first (strangler fig) | API-first bottom-up — rejected: refactors code that will be deleted |
| Frontend framework | Next.js 15 | Astro, Inertia.js — rejected: less React ecosystem, less real-time support |
| Frontend architecture | FSD | Flat by-type — rejected: doesn't scale, poor encapsulation |
| UI library | shadcn/ui | MUI, Ant Design — rejected: heavy dependencies, hard to customize |
| Data access | Supabase direct + thin Python API | All through Python API — rejected: unnecessary middleman for CRUD |
| Auth | Supabase Auth | Shared sessions, OAuth — rejected: Supabase already in stack |
| Coexistence | Path-based Caddy routing | Subdomain, iframe — rejected: subdomain feels like two apps, iframe is fragile |
| Repo structure | Monorepo | Multi-repo — rejected: coordination overhead for small team |
| Python refactoring | Minimal (API extraction only) | Full main.py split — rejected: wasted effort on dying code |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Two auth systems during transition | Users need separate login if cookie expires | Both use same `auth.users` table; full unification when FastHTML retired |
| Supabase RLS gaps | Data leaks in direct client access | Audit RLS policies before each page migration |
| Main.py merge conflicts during transition | Dev friction | Minimize Python changes; new work goes to Next.js |
| Design inconsistency between old/new pages | Confusing UX | Port design system tokens to Tailwind config first |
| Calculation engine integration | Complex data mapping | Dedicated `/api/calculate` endpoint tested against existing results |
