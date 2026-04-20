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
- `settings_profile.py` — 11 routes (/settings GET+POST, /settings/telegram GET+POST 301 shims, /profile GET+POST, /profile/{user_id} GET+POST admin save + profile view with tabs, /profile/{user_id}/edit-field|update-field|cancel-edit inline-edit HTMX trio) + 1 render helper (`_render_profile_field_display`). Superseded by Next.js `/settings` + `/profile` — archived 2026-04-20 Phase 6C-2B-4. NOT including `/api/{settings,profile}/*` (FastAPI, still alive), `/admin/*` (separate archive decision), or `/telegram/*` top-level (separate archive 6C-2B-6). FastHTML nav entries for `/settings` and `/profile` (main.py lines 2586, 2590, 2795, 2902) left intact — they become dead links post-archive, safe per Caddy cutover.
- `training.py` — 7 routes (/training registry GET, /training/videos HTMX filter, /training/new-form GET + /training/new POST create, /training/{video_id}/edit-form GET + /training/{video_id}/edit POST update, /training/{video_id}/delete DELETE) + 3 render helpers (`_get_embed_url`, `_get_thumbnail_url`, `_render_video_cards`) + 1 module constant (`_PLATFORM_LABELS`). Superseded by Next.js `/training` — archived 2026-04-20 Phase 6C-2B-5. NOT including `services/training_video_service.py` (service layer left alive in `services/`; becomes effectively unused after this archive but not touched per task scope), `training_manager` role infrastructure (sidebar impersonation, ROLE_LABELS_RU entry, `/admin/impersonate` guard — all still alive and unrelated to this archive), or sidebar/nav entries for `/training` (left intact, dead links post-archive, safe per Caddy cutover). No `/api/training/*` FastAPI sub-app exists.
- `approvals_changelog_telegram.py` — 6 routes from 3 independent cross-cutting areas: `/approvals` GET (Top Manager approvals workspace, standalone page between quote-control clusters), `/changelog` GET (timeline of product updates, reads `services/changelog_service`), `/telegram` GET + `/telegram/generate-code` POST + `/telegram/disconnect` POST + `/telegram/status` GET (Telegram pairing page + HTMX fragments) + 1 render helper (`_telegram_status_fragment`). Superseded by Next.js (/approvals → /quotes?status=pending_approval + dashboard widget, /changelog → app.kvotaflow.ru/changelog reading `/api/changelog`, /telegram → /settings/telegram reading `/api/integrations/*`) — archived 2026-04-20 Phase 6C-2B-6. Removed unused `services.telegram_service` imports (`TELEGRAM_BOT_USERNAME`, `get_user_telegram_status`, `request_verification_code`, `unlink_telegram_account`, `send_procurement_invoice_complete_notification`) from main.py; kept `notify_creator_of_return` (still called by `/quote-control/{quote_id}/return-to-control`). NOT including `/api/telegram/webhook` or `/api/integrations/*` (FastAPI, alive), `services/telegram_service.py` or `services/changelog_service.py` (service layers still alive), `/quote-control/*` routes (separate archive decision, 6C-2B-12), or `/admin/*` feedback routes (separate decision). Sidebar/nav entries for `/approvals`, `/changelog`, `/telegram` (main.py lines 2571, 2726, 2727, 2740) left intact, become dead links post-archive, safe per Caddy cutover.

## Why preserve

- Git history alone is harder to browse than a dedicated archive directory
- Routes were broken post-migration-284 (Phase 5d exempt list) before archival — not losing working code
- Allows easy copy-back if an obscure flow needs restoration

## Not imported

These files are NOT imported by `main.py` or `api/app.py`. The FastHTML routes they defined are effectively deleted from the running app. They will return 404 in production, which is an improvement over the 500 errors they returned before this archive.

## Recovery

To restore a route: copy the handler back to `main.py`, restore imports, re-apply the `@rt(...)` decorator. Then regenerate tests if needed. Not recommended — rewrite via Next.js + FastAPI instead.
