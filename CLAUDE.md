# OneStack (Kvota Quotation Management System)

**Stack:** FastHTML + HTMX | **DB:** Supabase PostgreSQL (schema: `kvota`) | **Deploy:** Docker on beget-kvota
**Domain:** kvotaflow.ru | **Container:** kvota-onestack | **Latest migration:** 187

---

## CRITICAL: Calculation Engine — DO NOT MODIFY

**Never change:** `calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`

If data schema changes, adapt in `build_calculation_inputs()` (main.py) — transform new field names to what the engine expects:

```python
'base_price_vat': item.get('purchase_price_original')  # map new→old
```

---

## Entity Lifecycle

**Quote → Specification → Deal** = same business entity at different stages. They share data via `deals.specification_id` (1:1). Never create separate data layers for specs vs deals.

See `BUSINESS_LOGIC.md` for full entity relationships and payment architecture.

---

## Navigation Architecture

Read `.claude/NAVIGATION_ARCHITECTURE.md` before creating new pages.

- **Hub-and-Spoke:** `/tasks` = single entry point for all tasks
- **Object-oriented URLs:** noun-based (`/quotes/{id}`), not action-based
- **Role-based tabs:** tabs on entity pages, not separate workspace routes
- **Sidebar:** Главное → Реестры → Финансы → Администрирование
- No deep URL nesting, no data duplication across pages

---

## Database

- **Schema:** always `kvota.table_name` (never `public`)
- **Role column:** `r.slug` (never `r.code`) in RLS policies
- **Migrations:** sequential numbering, use `scripts/apply-migrations.sh` via SSH
- **Reference:** `.claude/skills/db-kvota/skill.md`
- **After migrations:** regenerate frontend types: `cd frontend && npm run db:types`

---

## Frontend Type Safety

Auto-generated `database.types.ts` catches wrong column names at **build time**. After DB migrations: `cd frontend && npm run db:types`.

- Never use `as any` to suppress Supabase query types — fix the query instead
- Before using `amount`/`total`/`price` columns, check `.kiro/steering/database.md` — confusable column reference
- FK joins (`quotes!inner(...)`) aren't type-checked — verify manually

---

## Common Pitfalls

**PostgREST FK ambiguity:** When a table has multiple FKs to the same target, specify explicitly: `quotes!customer_id(name)` not `customers(name)`. Causes silent failures after deployment.

**Python variable scoping:** Variables in GET handler are NOT available in POST handler — they're separate functions. Always verify every variable is defined in scope.

**Hardcoded values:** Never use hardcoded timestamps, IDs, or URLs. Use `datetime.now()`, generated UUIDs, or config vars.

---

## Deployment

Push to main → GitHub Actions auto-deploys. Before confirming deployment:

1. Check GitHub Actions passed
2. Test in browser at https://kvotaflow.ru
3. Verify functionality, check console errors

```bash
ssh beget-kvota "docker logs kvota-onestack --tail 50"
```

---

## Design System

Read `design-system.md` before any UI work. CSS in `APP_STYLES` (main.py).
Font: Inter | Use constrained spacing/type scales | No `transition: all` | No `transform: translateY()` on hover | Use `.btn` BEM classes.

---

## Workflow: Sales → Procurement

- **Sales** enters: name, SKU, brand, quantity
- **Procurement** fills: price (in supplier currency), country, production time, supply chain, total weight/volume
- Currency conversion to quote currency happens at calculation stage

---

## Localhost dev — Python API proxy

Frontend client code calls `/api/*` for anything backed by the Python service
(workflow transitions, calc engine, document exports, geo/VAT lookups, letter
flow). In production Caddy routes `/api/*` to the Python container.

On localhost:3000 the Next.js dev server proxies `/api/*` to whatever
`frontend/.env.local` sets `PYTHON_API_URL` to, via the rewrite in
`frontend/next.config.ts`. Without this, every Python-backed call returns the
Next.js 404 HTML page and the frontend crashes on `res.json()` (classic symptom:
*"Unexpected token '<', '<!DOCTYPE \"...\" is not valid JSON"*).

**WARNING — when `PYTHON_API_URL` points at a remote host (e.g.
`https://kvotaflow.ru`), every workflow transition, document write, and
notification triggered from your localhost UI runs against that remote
instance.** State changes, sent emails, audit log entries are real. For
isolated testing, run the Python container locally and set
`PYTHON_API_URL=http://localhost:5001`.

This applies to **every Python-backed feature still served by FastHTML** —
i.e., the strangler-fig endpoints not yet migrated to Next.js Server Actions
or direct Supabase calls. Pure Supabase reads/writes from the browser hit
Supabase directly and are NOT affected by this proxy.
