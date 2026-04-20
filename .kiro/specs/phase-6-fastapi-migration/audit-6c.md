# Phase 6C-2 Audit: FastHTML HTML Routes (2026-04-20)

## Methodology

- Route inventory: `Grep ^@rt\(` in `main.py` (exhaustive, `head_limit: 0`) -> **230 matches** + 2 `@app.get(...)`  = **232 routes** total.
- Route sampling: 0 `/api/*` handlers remain (Phase 6B complete, verified via `Grep @rt\("/api/`).
- Next.js equivalence: matched each path against `frontend/src/app/**/page.tsx` (29 live pages) + `frontend/src/widgets/sidebar/sidebar-menu.ts` nav map.
- Frontend cross-refs: `Grep frontend/src` for FastHTML path literals (excluding `/api/`) -> **0 hits**. Next.js never calls FastHTML HTML endpoints directly.
- Internal cross-refs (ALIVE signal): grep in `main.py` for `RedirectResponse\("/x"`, `hx_(get|post|put|delete|patch)=f?"/x"`, inline `fetch\("/x"`, `window.location='/x'`, `action=f"/x"`, `href=f?"/x"`.
- Caddy routing: `app.kvotaflow.ru` -> Next.js, `kvotaflow.ru` -> FastHTML (subdomain split, not path-based). Both subdomains share the `onestack` Docker container for FastHTML routes.

## Summary

| Classification | Routes | Approx LOC | % |
|----------------|--------|-----------|---|
| DEAD           | 0      | 0         | 0% |
| ALIVE          | 215    | ~38,000   | 93% |
| UNCERTAIN      | 17     | ~1,200    | 7% |
| **Total**      | 232    | ~40,000   | 100% |

**Top finding: nothing is DEAD in the strict sense yet.** Every route without a Next.js equivalent is ALIVE because no replacement exists. Every route with a Next.js equivalent is **also ALIVE**, because the FastHTML page it serves is still reachable at `kvotaflow.ru/{path}` and is linked by other FastHTML handlers (nav, breadcrumbs, HTMX tab panels).

**Path to DEAD requires one of:**
1. **Caddy cutover**: route `kvotaflow.ru/{path}` to Next.js container (not just `app.kvotaflow.ru`). At that point every FastHTML page served at `{path}` becomes unreachable via user navigation, and the FastHTML @rt handler is DEAD modulo bookmarks/external links.
2. **FastHTML nav removal**: strip `main.py`'s top-nav + dashboard cards of `href="/{path}"` and remove the parent HTML page. Child HTMX fragments (inline edits, tab panels) then become DEAD.

Recommended Phase 6C-2B strategy below reflects this: PRs archive **groups at a time**, each group anchored by a parent page removal.

## Classification Rules Applied

- **DEAD**: no Next.js equivalent AND no FastHTML cross-refs (0 such routes found).
- **ALIVE**: has Next.js equivalent OR has FastHTML cross-refs.
  - Any route reachable via FastHTML-rendered `href=`, `hx_*`, `action=`, `window.location=`, `onclick=`, or `RedirectResponse` stays ALIVE.
  - Auth gateway routes (`/login`, `/logout`, `/unauthorized`) stay ALIVE until FastHTML fully retires - they are the session fallback for legacy pages per `strangler-fig-auth.md`.
  - Container healthcheck hits `/login` (see `docker-compose.prod.yml`) — keep `/login` ALIVE until healthcheck is updated.
- **UNCERTAIN**: routes that might be orphaned (no nav entry, no internal redirect target, no HTMX caller) — likely archivable but need a production-traffic probe before delete.

## Feature Area Breakdown

### 0. Core auth + shell (ALIVE) — 7 routes, ~800 LOC

| Method | Path | Handler | Lines | Next.js? | Cross-refs | Notes |
|--------|------|---------|-------|----------|-----------|-------|
| GET | `/` | get (root) | 4542-4547 | `/app/page.tsx` | 98+ RedirectResponse from auth guards | Redirects to `/tasks` if session, `/login` otherwise. FastHTML-only shell. |
| GET | `/login` | get | 4549-4707 | `/app/login/page.tsx` | Healthcheck hits `/login`; 4+ RedirectResponse targets | Next.js has own /login but FastHTML /login is healthcheck target. |
| POST | `/login` | post | 4708-4934 | Next.js Supabase flow | - | Legacy session-cookie login; JWT path preferred. |
| GET | `/logout` | get | 4936-4940 | Next.js Supabase signOut | RedirectResponse target | Keep until FastHTML nav entirely gone. |
| GET | `/unauthorized` | get | 4942-? | n/a | 60+ RedirectResponse targets | Generic 403 page used by every guard in main.py. |
| GET | `/tasks` | get | 7757-7916 | no Next.js `/tasks` | Root redirects here, nav link | Primary FastHTML shell landing. |
| GET | `/dashboard` | get | 7918-8162 | `/app/(app)/dashboard/page.tsx` | `hx_get="/dashboard"` (line 5738), 2 RedirectResponse targets | Dual: both apps have a dashboard. Old HTMX flow still live at kvotaflow.ru. |

### 1. Quotes (ALIVE) — 39 routes, ~8,000 LOC

Next.js has `(app)/quotes/page.tsx` + `(app)/quotes/[id]/page.tsx` + `(app)/quotes/trash/page.tsx`. But the FastHTML quote detail page at `kvotaflow.ru/quotes/{id}` is STILL live, and all workflow transition POST handlers return `RedirectResponse("/quotes/{id}")` to the FastHTML page.

| Method | Path | Lines | Classification | Notes |
|--------|------|-------|----------------|-------|
| GET | `/quotes` | 8164-8850 | ALIVE | Next.js equivalent exists but FastHTML list still rendered; `onclick=window.location='/quotes/{id}'` (line 8424) |
| GET | `/quotes/{quote_id}` | 8852-10619 | ALIVE | 1768 LOC FastHTML detail view. 60+ RedirectResponse targets across the file land here. |
| POST | `/quotes/{quote_id}/submit-procurement` | 10621-10711 | ALIVE | Inline fetch from FastHTML page (line 10341) |
| POST | `/quotes/{quote_id}/submit-quote-control` | 10713-10744 | ALIVE | FastHTML workflow action |
| GET | `/quotes/{quote_id}/return-to-control` | 10746-10896 | ALIVE | FastHTML form |
| POST | `/quotes/{quote_id}/return-to-control` | 10898-10981 | ALIVE | FastHTML form submit |
| GET | `/quotes/{quote_id}/submit-justification` | 10983-11086 | ALIVE | FastHTML form |
| POST | `/quotes/{quote_id}/submit-justification` | 11088-11235 | ALIVE | FastHTML form submit |
| POST | `/quotes/{quote_id}/manager-decision` | 11237-11286 | ALIVE | Workflow action |
| GET+POST | `/quotes/{quote_id}/approval-return` | 11288-11491 | ALIVE | FastHTML form round trip |
| POST | `/quotes/{quote_id}/send-to-client` | 11493-11534 | ALIVE | Workflow action |
| POST | `/quotes/{quote_id}/client-change-request` | 11536-11613 | ALIVE | Workflow action |
| POST | `/quotes/{quote_id}/submit-spec-control` | 11615-11644 | ALIVE | Workflow action |
| POST | `/quotes/{quote_id}/client-rejected` | 11646-11711 | ALIVE | Workflow action |
| POST | `/quotes/{quote_id}/approve-department` | 11713-11760 | ALIVE | Workflow action |
| PATCH | `/quotes/{quote_id}/items/{item_id}` | 11762-11810 | ALIVE | HTMX inline edit hx_patch |
| POST | `/quotes/{quote_id}/items/bulk` | 11812-11880 | ALIVE | Inline fetch (line 9624) |
| PATCH | `/quotes/{quote_id}/inline` | 11882-11950 | ALIVE | HTMX inline edit hx_patch (12+ refs) |
| POST | `/quotes/{quote_id}/cancel` | 11952-11990 | ALIVE | Inline fetch (line 10595) |
| GET+POST | `/quotes/{quote_id}/edit` | 11992-12403 | ALIVE | FastHTML edit form |
| GET+POST | `/quotes/{quote_id}` | 12405-13051 | ALIVE | POST form handler for detail page |
| POST | `/quotes/{quote_id}/preview` | 13053-13226 | ALIVE | hx_post preview (line 13591, 13732) |
| GET+POST | `/quotes/{quote_id}/calculate` | 13228-14448 | ALIVE | 1220 LOC — calc engine entry |
| GET | `/quotes/{quote_id}/documents` | 14450-14831 | ALIVE | FastHTML docs tab |
| GET | `/quotes/{quote_id}/versions` | 14833-14978 | ALIVE | Version history tab |
| GET | `/quotes/{quote_id}/versions/{version_num}` | 14980-15166 | ALIVE | Version detail |
| GET | `/quotes/{quote_id}/export/specification` | 15168-15220 | ALIVE | xlsx export |
| GET | `/quotes/{quote_id}/export/invoice` | 15222-15264 | ALIVE | xlsx export |
| GET | `/quotes/{quote_id}/export/validation` | 15266-15306 | ALIVE | xlsx export |
| GET | `/quotes/{quote_id}/preview` | 13053 | (listed above) | ALIVE |
| GET | `/quotes/{quote_id}/chat` | 43331-43399 | ALIVE | HTMX chat panel for FastHTML detail |
| POST | `/quotes/{quote_id}/comments` | 43401-43474 | ALIVE | hx_post (line 43300) |
| GET | `/quotes/{quote_id}/cost-analysis` | 20107-? (@app.get) | ALIVE | Cost analysis tab |
| GET | `/quotes/{quote_id}/cost-analysis-json` | 20416-20428 (@app.get) | UNCERTAIN | JSON endpoint — if no caller remaining, archive. Probe needed. |

### 2. Procurement (ALIVE) — 3 routes, ~400 LOC

| Method | Path | Lines | Classification | Notes |
|--------|------|-------|----------------|-------|
| GET | `/procurement` | 16514-16605 | ALIVE | Registry page; nav link `href="/procurement"` (line 2559), `href="/procurement"` in dashboard (line 5271) |
| GET+POST | `/procurement/{quote_id}/return-to-control` | 16607-16845 | ALIVE | Form; internal redirect target |
| GET | `/procurement/{quote_id}/export` | 16847-16937 | ALIVE | xlsx export |

Note: `/procurement/{quote_id}` (workspace page) was archived to `legacy-fasthtml/procurement_workspace.py` in Phase 6C-1. However, `main.py` still has 6 `href="/procurement/{quote_id}"` anchors and 1 `RedirectResponse` to this now-404 path. **These are broken links that need cleanup during 6C-2.**

### 3. Logistics (ALIVE) — 5 routes, ~1,500 LOC

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET | `/logistics` | 16939-16953 | no | Registry; nav link + 3 redirect targets |
| GET | `/logistics/{quote_id}` | 16955-17587 | no | Workspace page |
| POST | `/logistics/{quote_id}` | 17589-17752 | no | Workspace form submit |
| GET+POST | `/logistics/{quote_id}/return-to-control` | 17754-17991 | no | Form |

### 4. Customs (ALIVE) — 10 routes, ~1,800 LOC

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET | `/customs` | 17993-18008 | no | Registry |
| GET | `/customs/declarations` | 18010-18141 | `(app)/customs/declarations/page.tsx` | Next.js has declarations list; FastHTML still live |
| GET+POST | `/customs/declarations/upload` | 18143-18249 | no | FastHTML upload flow |
| GET+POST | `/customs/declarations/upload/preview` | 18251-18360 | no | FastHTML wizard step 2 |
| POST | `/customs/declarations/upload/confirm` | 18362-18427 | no | FastHTML wizard step 3 |
| GET | `/customs/declarations/{declaration_id}/items` | 18429-18492 | no | HTMX fragment (hx_get line 18063) |
| GET+POST | `/customs/{quote_id}` | 18494-19604 | no | Workspace (1100 LOC) |
| POST | `/customs/{quote_id}/items/{item_id}` | 19606-19687 | no | Inline edit (inline fetch line 19280) |
| GET+POST | `/customs/{quote_id}/return-to-control` | 19689-19955 | no | Form |

### 5. Quote Control (ALIVE) — 9 routes, ~2,400 LOC

Not in Next.js sidebar. FastHTML-only workflow for quote_controller role.

| Method | Path | Lines | Notes |
|--------|------|-------|-------|
| GET | `/quote-control` | 20429-20791 | Registry |
| GET | `/quote-control/{quote_id}` | 20793-21482 | Workspace |
| GET | `/quote-control/{quote_id}/invoice-comparison` | 21484-21593 | HTMX fragment (hx_get line 21096) |
| GET | `/quote-control/{quote_id}/invoice/{invoice_id}/detail` | 21595-21706 | HTMX fragment (hx_get line 21582) |
| GET+POST | `/quote-control/{quote_id}/columns` | 21708-21849 | Form |
| GET | `/quote-control/{quote_id}/columns/preset/{preset_name}` | 21851-21895 | Preset selector |
| GET+POST | `/quote-control/{quote_id}/return` | 22046-22349 | Form |
| GET+POST | `/quote-control/{quote_id}/request-approval` | 22351-22612 | Form |
| GET+POST | `/quote-control/{quote_id}/approve` | 22614-22884 | Form |

### 6. Approvals (ALIVE) — 1 route, ~150 LOC

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET | `/approvals` | 21897-22044 | `(app)/approvals/page.tsx` | Dual exists; FastHTML still live. |

### 7. Spec Control (ALIVE) — 8 routes, ~1,900 LOC

| Method | Path | Lines | Notes |
|--------|------|-------|-------|
| GET | `/spec-control` | 22886-22900 | Registry; nav link + 10+ redirect targets |
| GET+POST | `/spec-control/create/{quote_id}` | 22902-23385 | Form |
| GET+POST | `/spec-control/{spec_id}` | 23387-24205 | Workspace |
| GET | `/spec-control/{spec_id}/preview-pdf` | 24207-24286 | PDF stream |
| GET | `/spec-control/{spec_id}/export-pdf` | 24288-24339 | PDF download |
| GET | `/spec-control/{spec_id}/export-docx` | 24341-24399 | DOCX download |
| POST | `/spec-control/{spec_id}/upload-signed` | 24401-24534 | File upload |
| POST | `/spec-control/{spec_id}/confirm-signature` | 24536-? | Finalize |

### 8. Deals / Finance (ALIVE) — 13 routes, ~3,800 LOC

Deals and finance are deeply coupled. Next.js has `(app)/finance/page.tsx` (deals/erps/payments tabs) and `(app)/payments/calendar/page.tsx`.

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET | `/deals` | 24823-24833 | no | Redirect to `/finance` — legacy shim, 1-line safe to keep |
| GET | `/payments/calendar` | 24835-24879 | `(app)/payments/calendar/page.tsx` | Dual exists |
| GET | `/finance` | 24881-26648 | `(app)/finance/page.tsx` | 1767 LOC FastHTML finance workspace; Next.js covers it — candidate for archive when nav cutover |
| GET | `/finance/{deal_id}` | 26650-26927 | no | Redirects to `/quotes/{id}?tab=finance_main` |
| GET+POST | `/finance/{deal_id}/payments/new` | 26929-27141 | no | HTMX payment form |
| GET+POST | `/finance/{deal_id}/payments` | 26992-27141 | no | Payment creation |
| DELETE | `/finance/{deal_id}/payments/{item_id}` | 27143-27182 | no | HTMX row delete |
| GET+POST | `/finance/{deal_id}/generate-plan-fact` | 27184-27449 | no | Plan-fact generator |
| PATCH+DELETE | `/finance/{deal_id}/plan-fact/{item_id}` | 27451-27909 | no | Plan-fact row ops |
| GET+POST+DELETE | `/finance/{deal_id}/logistics-expenses/new-form` `/logistics-expenses` `/logistics-expenses/{expense_id}` | 40706-41001 | no | Logistics expense HTMX CRUD |
| POST | `/finance/{deal_id}/generate-currency-invoices` | 41003-41082 | no | Generate CI batch |
| POST | `/finance/{deal_id}/stages/{stage_id}/expenses` | 40662-40672 | no | Redirect to `/finance/{id}?tab=logistics` |
| POST | `/finance/{deal_id}/stages/{stage_id}/status` | 40674-40704 | no | Stage status toggle |

### 9. Settings / Profile / Admin (MIXED) — 20 routes, ~3,500 LOC

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET+POST | `/settings` | 15308-15514 | `(app)/settings/page.tsx` | Dual exists |
| GET+POST | `/settings/telegram` | 15516-15524 | - | Redirect to `/telegram` (301) — legacy shim |
| GET+POST | `/profile` | 16173-16466 | `(app)/profile/page.tsx` | Dual exists |
| GET | `/profile/{user_id}` | 16468-16512, 35867-36179 | no | Admin view of other user |
| GET+POST+GET | `/profile/{user_id}/edit-field/{field_name}` `/update-field` `/cancel-edit` | 36181-36413 | no | HTMX inline edit trio |
| GET | `/admin/users` | 27911-27919 | `(app)/admin/users/page.tsx` | Redirect to `/admin` — likely UNCERTAIN |
| GET | `/admin` | 28166-28398 | no (Next.js uses `/admin/users` etc) | FastHTML admin hub |
| GET | `/admin/feedback` | 28400-28513 | `(app)/admin/feedback/page.tsx` | Dual exists |
| POST | `/admin/feedback/{short_id}/status` | 28515-28545 | - | HTMX (hx_post line 28696) |
| POST | `/admin/feedback/{short_id}/sync-clickup` | 28547-28589 | - | HTMX (hx_post line 28719) |
| GET | `/admin/feedback/{short_id}` | 28591-28771 | `(app)/admin/feedback/[id]/page.tsx` | Dual exists |
| GET+POST+GET | `/admin/users/{user_id}/roles/edit` `/update` `/cancel` | 28773-28992 | no | HTMX role editor trio |
| GET+POST | `/admin/users/{user_id}/roles` | 28994-29239 | no | Role assignment list |
| GET+POST | `/admin/brands` `/brands/new` `/{id}/edit` `/{id}/delete` | 29241-29921 | no | Brand-to-sales assignments |
| GET+POST | `/admin/procurement-groups` `/new` `/{id}/edit` `/{id}/delete` | 29923-30589 | no | Procurement group assignments |
| GET | `/admin/impersonate` | 30591-30607 | no | User-switching for admin |
| GET | `/admin/impersonate/exit` | 30609-30621 | - | Exit impersonation |

### 10. Suppliers (ALIVE) — 8 routes, ~1,400 LOC

| Method | Path | Lines | Next.js? | Notes |
|--------|------|-------|----------|-------|
| GET | `/suppliers` | 30622-30910 | `(app)/suppliers/page.tsx` | Dual |
| GET+POST | `/suppliers/new` | 30912-31115 | no | Create form |
| GET | `/suppliers/{supplier_id}` | 31117-31311 | `(app)/suppliers/[id]/page.tsx` | Dual |
| GET+POST+PATCH | `/suppliers/{supplier_id}/brands` `/brands/{id}` | 31313-31643 | no | HTMX brand CRUD |
| GET+POST | `/suppliers/{supplier_id}/edit` | 31645-31755 | no | Edit form |
| POST | `/suppliers/{supplier_id}/delete` | 31757-31787 | no | Delete |

### 11. Companies (buyer / seller) (ALIVE) — 11 routes, ~2,400 LOC

Next.js has `(app)/companies/page.tsx` (unified) — FastHTML split across buyer/seller/companies.

| Method | Path | Lines | Notes |
|--------|------|-------|-------|
| GET | `/companies` | 27921-28164 | `(app)/companies/page.tsx` covers; FastHTML still renders |
| GET | `/buyer-companies` | 31789-31793 | Redirects to `/companies?tab=buyer_companies` — legacy shim |
| GET+POST | `/buyer-companies/new` | 31795-31915 | Create form |
| GET | `/buyer-companies/{company_id}` | 31917-32334 | Detail workspace |
| GET+POST | `/buyer-companies/{company_id}/edit` | 32336-32482 | Edit form |
| POST | `/buyer-companies/{company_id}/delete` | 32484-32514 | Delete |
| GET | `/seller-companies` | 32516-32520 | Redirect to `/companies?tab=seller_companies` |
| GET+POST | `/seller-companies/new` | 32522-32635 | Create form |
| GET | `/seller-companies/{company_id}` | 32637-33029 | Detail |
| GET+POST | `/seller-companies/{company_id}/edit` | 33031-33169 | Edit |
| POST | `/seller-companies/{company_id}/delete` | 33171-33201 | Delete |

### 12. Customers (ALIVE) — 21 routes, ~2,700 LOC

Next.js has `(app)/customers/page.tsx` + `(app)/customers/[id]/page.tsx`. FastHTML page still live.

| Path pattern | Lines | Notes |
|--------------|-------|-------|
| `/customers` | 33203-33426 | Registry; Next.js dual |
| `/customers/{id}` | 33428-34453 | Detail page — FastHTML uses `hx_get="/customers/{id}?tab=X"` for 4 tabs (contacts/contracts/quotes/specifications). Dual with Next.js. |
| `/customers/{id}/manager` | 34455-34481 | hx_put manager change (line 33710) |
| Calls (5 routes): `/calls/new-form` `/calls` `/calls/{id}/edit-form` `/calls/{id}/edit` `/calls/{id}` | 34483-34823 | HTMX call CRUD |
| Field edits (3 routes): `/edit-field/{name}` `/update-field/{name}` `/cancel-edit/{name}` | 34825-34985 | HTMX inline edit trio |
| Notes (3 routes): `/edit-notes` `/update-notes` `/cancel-edit-notes` | 35028-35127 | HTMX notes trio |
| Contacts (8 routes): `/contacts/{id}/edit-field/{name}` `/contacts/{id}/update-field/{name}` `/contacts/{id}/cancel-edit/{name}` `/contacts/{id}/toggle-signatory` `/contacts/{id}/toggle-primary` `/contacts/{id}/toggle-lpr` `/contacts/new` (GET+POST) | 35236-35865 | HTMX contact CRUD |
| Warehouses (3 routes): `/warehouses/add` (GET+POST) `/warehouses/cancel-add` `/warehouses/delete/{index}` | 35537-35652 | HTMX warehouse CRUD |

### 13. Contracts / Locations (ALIVE) — 9 routes, ~1,400 LOC

| Path | Lines | Next.js? | Notes |
|------|-------|----------|-------|
| `/customer-contracts` | 36415-36710 | no | Registry |
| `/customer-contracts/new` (GET+POST) | 36712-36935 | no | Create form |
| `/customer-contracts/{id}` | 36937-37081 | no | Detail |
| `/locations` | 37083-37369 | `(app)/locations/page.tsx` | Dual |
| `/locations/new` (GET+POST) | 37371-37458 | no | Create form |
| `/locations/{id}` | 37460-37833 | no | Detail |
| `/locations/{id}/edit` (GET+POST) | 37835-37942 | no | Edit |
| `/locations/{id}/delete` | 37944-37970 | no | Delete |
| `/locations/seed` | 37972-38017 | no | Admin seed utility — UNCERTAIN, may be dev-only |

### 14. Supplier Invoices (ALIVE) — 3 routes, ~1,300 LOC

| Path | Lines | Notes |
|------|-------|-------|
| `/supplier-invoices` | 38019-38288 | Registry |
| `/supplier-invoices/{id}` | 38290-38838 | Detail |
| `/supplier-invoices/{id}/payments/new` (GET+POST) | 38840-39590 | Payment form |

### 15. Documents (ALIVE) — 5 routes, ~450 LOC

| Path | Lines | Notes |
|------|-------|-------|
| `/documents/upload/{entity_type}/{entity_id}` | 39592-39722 | File upload |
| `/documents/{id}/download` | 39724-39763 | Signed URL redirect |
| `/documents/{id}/view` | 39765-39804 | Inline view |
| `/documents/{id}` (DELETE) | 39806-39841 | hx_delete refs from 2 places (lines 39086, 39420) |
| `/documents/{entity_type}/{entity_id}` | 39843-39867 | HTMX document list fragment |

### 16. Currency Invoices (ALIVE) — 6 routes, ~1,100 LOC

| Path | Lines | Next.js? | Notes |
|------|-------|----------|-------|
| `/currency-invoices` | 41913-42118 | `(app)/currency-invoices/page.tsx` | Dual |
| `/currency-invoices/{ci_id}` (GET+POST) | 42120-42614 | `(app)/currency-invoices/[id]/page.tsx` | Dual |
| `/currency-invoices/{ci_id}/verify` | 42616-42710 | - | hx_post (line 42408) |
| `/currency-invoices/{ci_id}/download-docx` | 42712-42755 | - | DOCX download |
| `/currency-invoices/{ci_id}/download-pdf` | 42757-42864 | - | PDF download |
| `/currency-invoices/{ci_id}/regenerate` | 42866-? | - | Regenerate file |

### 17. Training (ALIVE) — 6 routes, ~800 LOC

| Path | Lines | Next.js? | Notes |
|------|-------|----------|-------|
| `/training` | 41084-41554 | `(app)/training/page.tsx` | Dual |
| `/training/videos` | 41556-41573 | - | HTMX fragment (hx_get lines 41104, 41114) |
| `/training/new-form` | 41575-41635 | - | HTMX form (hx_get line 41130) |
| `/training/new` | 41637-41679 | - | hx_post (line 41626) |
| `/training/{id}/edit-form` | 41681-41763 | - | HTMX (hx_get line 41534) |
| `/training/{id}/edit` | 41765-41806 | - | hx_post (line 41754) |
| `/training/{id}/delete` | 41808-? | - | hx_delete (line 41538) |

### 18. Deals / Deal Detail (ALIVE) — 1 route, ~800 LOC

| Path | Lines | Notes |
|------|-------|-------|
| `/deals/{deal_id}` | 39869-40660 | Redirects to `/finance/{id}` — can be thinned but likely ALIVE |

### 19. Calls (ALIVE) — 1 route, ~330 LOC

| Path | Lines | Notes |
|------|-------|-------|
| `/calls` | 43003-43329 | Standalone calls registry; no Next.js equivalent |

### 20. Chat / Comments / Changelog (ALIVE) — 3 routes, ~500 LOC

| Path | Lines | Next.js? | Notes |
|------|-------|----------|-------|
| `/quotes/{id}/chat` | 43331-43399 | - | Quote chat HTMX |
| `/quotes/{id}/comments` | 43401-43474 | - | hx_post (line 43300) |
| `/changelog` | 43476-43693 | `(app)/changelog/page.tsx` | Dual |

### 21. Telegram (ALIVE) — 4 routes, ~200 LOC

| Path | Lines | Next.js? | Notes |
|------|-------|----------|-------|
| `/telegram` | 43695-43722 | `(app)/telegram/page.tsx` | Dual; FastHTML settings shim redirects here |
| `/telegram/generate-code` | 43724-43793 | - | hx_post |
| `/telegram/disconnect` | 43795-43808 | - | hx_post (line 43649) |
| `/telegram/status` | 43810-? | - | HTMX poll (line 43685, 43785) |

## UNCERTAIN — 17 routes flagged

| Path | Lines | Reason |
|------|-------|--------|
| `/admin/users` | 27911-27919 | One-line redirect to `/admin`. Next.js has real `/admin/users/page.tsx`. Probe: is anything hitting `kvotaflow.ru/admin/users`? |
| `/admin/impersonate` + exit | 30591-30621 | Admin-only tool. No cross-refs found. May be intentionally hidden admin utility — keep until admin workflow migrated. |
| `/locations/seed` | 37972-38017 | Seed endpoint — dev-only utility, likely safe to remove. |
| `/quotes/{id}/cost-analysis` | 20107 (@app.get) | Check if Next.js proxies this or if any handler links to it. |
| `/quotes/{id}/cost-analysis-json` | 20416 (@app.get) | Same — probe needed. |
| `/admin/brands` cluster (4 routes) | 29241-29921 | No nav link in FastHTML top-nav, but may be linked from profile. Probe. |
| `/admin/procurement-groups` cluster (4 routes) | 29923-30589 | Next.js has `/admin/routing` — is this the replacement? Verify equivalence. |
| `/profile/{user_id}` | 16468-16512 + 35867-36179 | Resolved 2026-04-20: not a duplicate. FastHTML `@rt("/path")` infers HTTP method from function name (`get`/`post`). Line 16468 is the POST admin-save handler; line 35867 is the GET profile view. Standard FastHTML GET+POST pair idiom, same as `/quotes/{quote_id}/edit` at lines 11992+12330. Not archivable separately. |
| `/deals` | 24823-24833 | Thin legacy shim; safe, keep or remove. |
| `/settings/telegram` GET+POST (2) | 15516-15524 | Thin shim to `/telegram`. Safe to keep. |

## Recommended Archive PR Split (Phase 6C-2B)

Because 0 routes are strictly DEAD today, Phase 6C-2B requires a **cutover-then-archive** pattern per area:

1. **Infrastructure prep (PR 6C-2B-0)**: Update Caddy config to route `kvotaflow.ru/{path}` to Next.js for paths with confirmed Next.js equivalence. Update healthcheck from `/login` to Next.js page. ~50 LOC config.

2. **Customers archive (PR 6C-2B-1)**: After Caddy cutover, customers page is unreachable via nav. Archive 21 routes (~2,700 LOC). Preconditions: Next.js customer detail feature-complete, all inline-edit HTMX replaced with Next.js equivalents.

3. **Suppliers archive (PR 6C-2B-2)**: 8 routes (~1,400 LOC). Same precondition.

4. **Companies archive (PR 6C-2B-3)**: 11 routes (~2,400 LOC). Includes buyer-companies/seller-companies legacy split.

5. **Settings / Profile archive (PR 6C-2B-4)**: ~8 routes (~1,400 LOC).

6. **Training archive (PR 6C-2B-5)**: 6 routes (~800 LOC).

7. **Approvals / Changelog / Telegram archive (PR 6C-2B-6)**: 8 routes (~900 LOC). Small, mechanical.

8. **Dashboard / Tasks archive (PR 6C-2B-7)**: 2 routes (~750 LOC). Only after Next.js `/dashboard` covers all role tabs.

9. **Currency invoices archive (PR 6C-2B-8)**: 6 routes (~1,100 LOC).

10. **Locations archive (PR 6C-2B-9)**: 7 routes (~1,400 LOC).

11. **UNCERTAIN cleanup (PR 6C-2B-10)**: Probe production traffic, then delete `/admin/users` shim, `/locations/seed`, duplicate `/profile/{user_id}`, cost-analysis endpoints, etc. ~200 LOC.

**Not yet archivable (no Next.js equivalent):**
- Logistics (5 routes, ~1,500 LOC)
- Customs (10 routes, ~1,800 LOC) — partial Next.js only
- Quote-control (9 routes, ~2,400 LOC)
- Spec-control (8 routes, ~1,900 LOC)
- Customer-contracts (3 routes, ~500 LOC)
- Supplier-invoices (3 routes, ~1,300 LOC)
- Calls (1 route, ~330 LOC)
- Documents (5 routes, ~450 LOC)
- Deal/finance detail HTMX (~10 routes, ~2,000 LOC)
- Quote detail + all workflow transitions (~35 routes, ~7,500 LOC) — **biggest remaining chunk**

Total non-archivable-yet: **~89 routes, ~19,000 LOC**. These require Next.js features to be built before archival.

## Flagged ALIVE Surprises

1. **Every route marked "Next.js equivalent exists"** is still ALIVE because FastHTML `kvotaflow.ru` is served by the same container. Caddy only splits on subdomain, not path. This means shipping a Next.js page does not automatically retire the FastHTML page — explicit Caddy/DNS work is required.

2. **`/procurement/{quote_id}` dangling references**: The page was archived in Phase 6C-1, but `main.py` still has 6 `href="/procurement/{quote_id}"` anchors + 1 `RedirectResponse`. These currently 404 for users. **Bug to fix in 6C-2 cleanup.**

3. ~~**`/profile/{user_id}` double registration**~~ — **Resolved 2026-04-20 (PR #27):** both handlers are valid. FastHTML `@rt("/path")` with a function named `get` handles GET, function named `post` handles POST. This is the same idiom as `/quotes/{quote_id}/edit` (lines 11992+12330). No dead code. Audit was wrong on this item.

4. **FastHTML `/login` is the container healthcheck target** — any archival of /login requires updating `docker-compose.prod.yml` first, or moving healthcheck to FastAPI's `/api/health` (already live at `/api/health`).

5. **Thin redirect shims** (`/deals`, `/buyer-companies`, `/seller-companies`, `/settings/telegram`, `/admin/users`): cheap to keep as 301s for bookmark preservation, but easy wins if aggressive cleanup is desired.

## Open Questions for User Decision

1. Should Phase 6C-2 include Caddy route cutover, or is that a separate project?
2. Preserve 301 redirect shims (`/deals`, `/buyer-companies`, `/settings/telegram`) or archive them too?
3. Healthcheck path migration: move to `/api/health` (FastAPI) or keep `/login` until Phase 6C fully complete?
4. `/locations/seed` — dev-only utility. Delete now or flag for later?
5. ~~`/profile/{user_id}` duplicate handler at line 35867~~ — **Resolved 2026-04-20 (PR #27 investigation):** not a duplicate, it's a GET+POST pair via FastHTML function-name method inference.

## Footnotes

- **LOC estimates**: approximate, derived from handler spans (next `@rt` or `def` at module level). Precise measurement not required at this audit stage.
- **Caddy routing source**: `docs/superpowers/specs/2026-03-10-frontend-migration-design.md` lines 140-160 — subdomain-based split confirmed, not path-based.
- **Dual-auth context**: JWT (Next.js) + session cookie (FastHTML) continues per `.kiro/steering/strangler-fig-auth.md` until FastHTML pages gone.
- **Test coverage preservation**: Archival PRs must keep `tests/test_api_app_mount.py::TestLegacyRouteRegression` passing — ensures FastAPI /api/* mount still works after removing FastHTML pages.
