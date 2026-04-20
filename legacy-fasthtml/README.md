# Legacy FastHTML Archive

Archived 2026-04-20 during Phase 6C-1 of the FastAPI migration.

## What's here

- `quotes_new.py` — `/quotes/new` GET+POST form + `customer_search_dropdown` helper (superseded by Next.js `create-quote-dialog.tsx`)
- `customers_new.py` — `/customers/new` GET+POST form + 4 HTMX customer autocomplete endpoints + DaData INN lookup + 3 company search endpoints + dropdown helpers (superseded by Next.js customer creation flow)
- `procurement_workspace.py` — `/procurement/{id}` GET page + 7 invoice/items HTMX endpoints + `render_invoices_list` helper (superseded by Next.js `/procurement/kanban` and `/quotes/[id]` procurement step)
- `cities_search.py` — `GET /api/cities/search` HTMX endpoint (superseded by FastAPI `GET /api/geo/cities/search`)

## Why preserve

- Git history alone is harder to browse than a dedicated archive directory
- Routes were broken post-migration-284 (Phase 5d exempt list) before archival — not losing working code
- Allows easy copy-back if an obscure flow needs restoration

## Not imported

These files are NOT imported by `main.py` or `api/app.py`. The FastHTML routes they defined are effectively deleted from the running app. They will return 404 in production, which is an improvement over the 500 errors they returned before this archive.

## Recovery

To restore a route: copy the handler back to `main.py`, restore imports, re-apply the `@rt(...)` decorator. Then regenerate tests if needed. Not recommended — rewrite via Next.js + FastAPI instead.
