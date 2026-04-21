# OneStack (Kvota Quotation Management System)

**Stack:** FastAPI (uvicorn) + Next.js 15 | **DB:** Supabase PostgreSQL (schema: `kvota`) | **Deploy:** Docker on beget-kvota
**Domain:** kvotaflow.ru → app.kvotaflow.ru | **Containers:** kvota-onestack (Python), kvota-frontend (Next.js) | **Latest migration:** 283

> Phase 6C retired FastHTML entirely (2026-04-21). The Python service is now pure FastAPI served via `uvicorn api.app:api_app`. All UI lives in `frontend/` (Next.js App Router). Archived FastHTML handlers remain in `legacy-fasthtml/` for reference only — never imported at runtime.

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
