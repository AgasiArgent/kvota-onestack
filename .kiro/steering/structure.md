# Project Structure

## Organization Philosophy

**Dual-system monorepo** during strangler fig migration. The Python monolith (`main.py` + `services/`) coexists with a growing Next.js frontend (`frontend/`). New features go to Next.js; FastHTML routes are deleted as pages migrate.

## Directory Patterns

### Python Backend (Legacy — shrinking)

**Location:** Project root
**Pattern:** Monolith entry + domain services

```
main.py                     # Monolith: routes + HTML rendering (~49K lines)
services/                   # Domain services (one file per domain)
  ├── database.py           # Supabase client (shared)
  ├── deal_service.py       # Deal CRUD + business logic
  ├── customer_service.py   # Customer operations
  └── ...                   # ~48 service files
```

**Naming:** `snake_case` for files and functions. Services named `{domain}_service.py`.

**Pattern:** Route handlers in `main.py` call service functions. Services call `database.py` for Supabase access. No cross-service imports unless explicitly needed.

### Python API (New — growing)

**Location:** `api/`
**Purpose:** JSON endpoints for Next.js to call when Supabase direct access isn't enough

```
api/
├── __init__.py             # Router mounted at /api
├── auth.py                 # JWT validation middleware (ApiAuthMiddleware)
├── cron.py                 # Scheduled tasks (overdue checks)
├── plan_fact.py            # Plan vs fact analysis endpoints
└── ...                     # New domain files as business logic migrates
```

**Rule:** All business operations (workflow transitions, document generation, multi-step orchestration) go through Python API. See `api-first.md` for the full pattern. CRUD-only operations go through Supabase directly.

### Python Backend — Target Structure (Post-Migration)

Once FastHTML is fully retired, `main.py` is deleted. The Python backend becomes a focused API service organized for parallel development:

```
api/
├── __init__.py             # App factory, middleware, router mounting
├── auth.py                 # JWT validation middleware
├── routes/                 # Route handlers — one file per domain
│   ├── calculation.py      # /api/calculate
│   ├── workflow.py         # /api/quotes/{id}/transition, approvals
│   ├── exports.py          # PDF/Excel generation endpoints
│   ├── integrations.py     # DaData, Telegram, HERE
│   └── ...                 # New domains as needed
├── services/               # Business logic (migrated from current services/)
│   ├── database.py
│   ├── deal_service.py
│   └── ...
├── calculation_engine.py   # Frozen — never modify
├── calculation_models.py   # Frozen
└── calculation_mapper.py   # Frozen
```

**Parallel-friendly rules:**
- **800 lines max per file** — if a file approaches this, split by subdomain (e.g., `exports.py` → `exports/quotes.py`, `exports/specs.py`)
- **One domain per route file** — different developers can work on `routes/calculation.py` and `routes/workflow.py` without merge conflicts
- **Services own business logic** — route handlers validate input, call a service, return JSON. No business logic in routes.
- **No god files** — the entire point of this restructure is eliminating the 49K-line monolith. If any file grows beyond 800 lines, split before adding new code.
- **Flat over nested** — prefer `routes/quote_exports.py` over `routes/quotes/exports.py` until there are 3+ files for a domain
- **Domain over technical grouping** — initial route files (`exports.py`, `integrations.py`) group by technical concern for migration convenience. As endpoints grow, split by business domain: `integrations.py` → `customers.py` (DaData), `notifications.py` (Telegram), `logistics.py` (HERE geocoding)

### Next.js Frontend (New — growing)

**Location:** `frontend/`
**Architecture:** Feature-Sliced Design (FSD)

```
frontend/
├── app/                    # Next.js App Router (routing shell only)
│   ├── layout.tsx
│   ├── (auth)/             # Auth routes
│   └── [feature]/page.tsx  # Thin shells importing from src/
├── src/
│   ├── shared/             # Layer 1: No business logic
│   │   ├── ui/             # shadcn components, design tokens
│   │   ├── lib/            # Supabase clients, API client, utils
│   │   ├── config/         # Env vars, constants
│   │   └── types/          # Generated DB types, shared interfaces
│   ├── entities/           # Layer 2: Business entity models + UI
│   │   ├── quote/          # Type, QuoteCard, useQuote
│   │   ├── customer/
│   │   └── ...
│   ├── features/           # Layer 3: User actions
│   │   ├── chat/           # Send message, subscribe
│   │   ├── calculation/    # Trigger calc, display results
│   │   └── ...
│   ├── widgets/            # Layer 4: Composite UI blocks
│   │   ├── sidebar/
│   │   ├── dashboard-charts/
│   │   └── ...
│   └── pages/              # Layer 5: Full page compositions
```

**FSD import rule:** Layers import only from layers below. `features/` → `entities/` → `shared/`. Never upward. `app/` is routing glue outside FSD hierarchy.

### Database Migrations

**Location:** `migrations/`
**Pattern:** Sequential numbered SQL files: `001_initial.sql`, `210_fix_telegram_users_unique_constraint.sql`
**Rule:** Each migration does one thing. Never modify applied migrations — create new ones.

### Deployment

**Location:** `docker-compose.prod.yml`, `.github/workflows/`, `Dockerfile`
**Pattern:** Push to `main` → GitHub Actions builds → deploys to beget-kvota VPS

## Naming Conventions

### Python (Current)
- **Files:** `snake_case.py` — `deal_service.py`, `calculation_engine.py`
- **Functions:** `snake_case` — `get_quote_items()`, `build_calculation_inputs()`
- **Classes:** `PascalCase` — `CalculationInput`, `QuoteItem`
- **Routes:** `@rt("/path")` with `def get()` / `def post()` handlers

### TypeScript (Next.js)
- **Files:** `kebab-case.tsx` for components, `camelCase.ts` for utilities
- **Components:** `PascalCase` — `QuoteCard`, `SidebarNav`
- **Functions:** `camelCase` — `useQuote()`, `fetchCustomers()`
- **Types:** `PascalCase` — `Quote`, `Customer`, `DealPayment`

## Import Organization

### Python
```python
# Standard library
from datetime import datetime

# Third-party
from supabase import create_client

# Local services
from services.database import supabase
from services.deal_service import get_deal
```

### TypeScript (FSD)
```typescript
// External packages
import { useQuery } from '@tanstack/react-query'

// Shared layer (absolute)
import { supabase } from '@/shared/lib/supabase'
import { Button } from '@/shared/ui/button'

// Entity layer
import { QuoteCard } from '@/entities/quote'

// Relative (within same slice)
import { useCalculation } from './hooks'
```

**Path alias:** `@/` maps to `src/`

## Navigation Architecture

- **Hub-and-spoke:** `/tasks` is the single entry point for all users
- **Object-oriented URLs:** noun-based (`/quotes/{id}`), not action-based
- **Role-based tabs:** departments see different tabs on the same entity page
- **Sidebar:** Главное → Реестры → Финансы → Администрирование (sections filtered by role)
- **No deep nesting:** max 2 levels (`/quotes/{id}`, not `/quotes/{id}/items/{item_id}/edit`)

## Quote Detail Step Components

Each step in the quote detail page (`/quotes/[id]`) follows a consistent architecture:

```
features/quotes/ui/[step]-step/
├── [step]-step.tsx          # Root: "use client", props from QuoteStepContent
├── [step]-action-bar.tsx    # Sticky/fixed bar with workflow buttons
├── use-[step]-data.ts       # Client-side data fetching (when page props insufficient)
├── [panel].tsx              # Presentational panels (Card-based, one per section)
└── [dialog].tsx             # Sheet/Dialog for actions needing user input
```

**Props from parent** (`QuoteStepContent` switch): `{ quote, items, invoices, userRoles, calcVariables }`

**Not available from parent** — fetch client-side:
- `userId` → `supabase.auth.getUser()` (avoids prop-drilling through shared components)
- Calc summaries, documents → custom `use[Step]Data` hook

**Workflow mutations:** New operations with business logic or side effects (deal creation, document generation, multi-table transitions) must go through Python API endpoints — Server Actions are thin wrappers using `apiServerClient` (see `api-first.md`). Simple single-field updates on non-workflow fields (e.g., display name, boolean flags like `is_archived`) can use Supabase direct in `entities/quote/mutations.ts`. Some legacy workflow transitions still go direct to Supabase (see migration status in `api-first.md`). Call `router.refresh()` after mutation.

**Wiring in:** Add case to switch in `quote-step-content.tsx`. Step must be registered in `ROLE_ALLOWED_STEPS` and `STATUS_TO_STEP` (both in `entities/quote/types.ts`).

**Gotchas:**
- `quote_comments` table: column is `body` (not `comment`), no `comment_type` column — prefix body with context like `[Возврат на доработку] ...`
- DB-generated types have `boolean | null` — match nullability in custom interfaces
- Existing steps: sales, procurement, logistics, customs, calculation, control (all built)

## Code Organization Principles

1. **Entity lifecycle is sacred:** Quote → Specification → Deal is one entity at different stages. Never create separate data layers.
2. **Delete immediately:** When a Next.js page replaces a FastHTML route, delete the FastHTML route and its HTML helpers. No dead code.
3. **Services stay:** `services/` directory is well-modularized (48 files) and shared by both stacks. Don't restructure during migration — clean up after.
4. **API-first for business logic:** All business operations (workflows, document generation, multi-step orchestration) live in Python API — accessible by both UI and AI agents. CRUD goes direct to Supabase. See `api-first.md`.
5. **800 lines max:** No file exceeds 800 lines. Split before adding new code to a file approaching the limit.
6. **Parallel by design:** Each domain gets its own route file and service file. Two developers should never need to edit the same file for unrelated features.

---
_Document patterns, not file trees. New files following patterns shouldn't require updates_
