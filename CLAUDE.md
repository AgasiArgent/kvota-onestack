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

The Next.js frontend uses auto-generated `database.types.ts` to catch wrong column names at **build time**.

**Workflow after DB schema changes:**
1. Apply migration to DB
2. Run `cd frontend && npm run db:types` to regenerate types
3. Run `npm run build` — TS compiler will flag any broken queries

**What it catches:** nonexistent columns (e.g. `is_active` instead of `status`), wrong table names
**What it does NOT catch:** picking the wrong valid column (e.g. `total_amount` vs `total_amount_without_vat`)

**Rules for frontend queries:**
- Never use `as any` to suppress Supabase query types — fix the query instead
- RPC function types must be added manually to the `Functions` section of `database.types.ts`
- FK joins (`quotes!inner(...)`) are not type-checked (Relationships array is empty in generated types) — verify these manually
- Before using an `amount`/`total`/`price` column, check the reference below — many columns sound similar but mean different things

**Confusable columns — quotes table:**

| Need this | Use this column | NOT this |
|-----------|----------------|----------|
| Total price for client (in quote currency) | `total_amount_quote` | `total_amount` (base, no margin) |
| Total including VAT (in quote currency) | `total_with_vat_quote` | `total_with_vat_usd` (USD) |
| Total in USD (for internal reporting) | `total_amount_usd` | `total_usd` (subtotal) |
| Profit in quote currency | `profit_quote_currency` | `total_profit_usd` (USD) |
| Revenue excl. VAT in quote currency | `revenue_no_vat_quote_currency` | `total_quote_currency` |
| COGS in quote currency | `cogs_quote_currency` | — |
| Quote status (lifecycle) | `status` | `workflow_status` (approval flow) |

**Confusable columns — quote_items table:**

| Need this | Use this column | NOT this |
|-----------|----------------|----------|
| Purchase price (supplier currency) | `purchase_price_original` | `base_price_vat` (calculated) |
| Proforma excl. VAT (supplier currency) | `proforma_amount_excl_vat` | `proforma_amount_incl_vat` |
| Proforma excl. VAT (USD) | `proforma_amount_excl_vat_usd` | `proforma_amount_excl_vat` (original) |
| Product identifier (supplier's) | `supplier_sku` | `idn_sku` (internal), `product_code` (old) |

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
