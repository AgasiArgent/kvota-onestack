# Legacy FastHTML Archive

Archived during Phase 6C of the FastAPI migration (2026-04-20 onwards).

## What's here

- `quotes_new.py` — `/quotes/new` GET+POST form + `customer_search_dropdown` helper (superseded by Next.js `create-quote-dialog.tsx`) — archived 2026-04-20 Phase 6C-1
- `customers_new.py` — `/customers/new` GET+POST form + 4 HTMX customer autocomplete endpoints + DaData INN lookup + 3 company search endpoints + dropdown helpers (superseded by Next.js customer creation flow) — archived 2026-04-20 Phase 6C-1
- `procurement_workspace.py` — `/procurement/{id}` GET page + 7 invoice/items HTMX endpoints + `render_invoices_list` helper (superseded by Next.js `/procurement/kanban` and `/quotes/[id]` procurement step) — archived 2026-04-20 Phase 6C-1
- `cities_search.py` — `GET /api/cities/search` HTMX endpoint (superseded by FastAPI `GET /api/geo/cities/search`) — archived 2026-04-20 Phase 6C-1
- `customers.py` — 26 /customers routes (registry, detail with tabs, inline-edit fragments, contacts, warehouses, calls, notes) + 9 render helpers + ORDER_SOURCE constants. Superseded by Next.js `/customers` + children — archived 2026-04-20 Phase 6C-2B-1
- `suppliers.py` — 10 /suppliers routes (registry, create form, detail with general+brands tabs, edit form, deactivate, brand CRUD) + 4 render helpers (`_supplier_brand_row`, `_supplier_brands_tab`, `_supplier_brands_list_partial`, `_supplier_form`). Superseded by Next.js `/suppliers` + children — archived 2026-04-20 Phase 6C-2B-2. NOT including `/supplier-invoices/*` (no Next.js replacement yet, separate archive decision).
- `companies.py` — 15 routes (/companies unified tabs page + /buyer-companies + /seller-companies legacy split: registry redirects, create forms, detail views, edit forms, soft-delete) + 2 render helpers (`_buyer_company_form`, `_seller_company_form`). Superseded by Next.js `/companies` — archived 2026-04-20 Phase 6C-2B-3. NOT including `/api/{buyer-,seller-,}companies/*` (FastAPI, still alive) or `/customer-contracts/*` (separate area).

## Why preserve

- Git history alone is harder to browse than a dedicated archive directory
- Routes were broken post-migration-284 (Phase 5d exempt list) before archival — not losing working code
- Allows easy copy-back if an obscure flow needs restoration

## Not imported

These files are NOT imported by `main.py` or `api/app.py`. The FastHTML routes they defined are effectively deleted from the running app. They will return 404 in production, which is an improvement over the 500 errors they returned before this archive.

## Recovery

To restore a route: copy the handler back to `main.py`, restore imports, re-apply the `@rt(...)` decorator. Then regenerate tests if needed. Not recommended — rewrite via Next.js + FastAPI instead.
