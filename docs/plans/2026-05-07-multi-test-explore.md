# Exploration — 2026-05-07

Read-only mapping of the 8 bugs from `2026-05-07-multi-test-triage.md`.
Cross-checks code on `chore/harden-routing-api` (current branch) against `main`.

---

## Bug 1 — РОП KP #24 (P5) — head_of_sales cannot «Отправить в закупку»

**Status:** **ALREADY FIXED on main, needs re-test only.**

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/services/workflow_service.py:174` — DRAFT → PENDING_PROCUREMENT now lists `["sales", "head_of_sales", "admin"]`. Same widening in 35 other transitions.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/tests/test_workflow_head_of_sales.py:46` — full regression suite (TestHeadOfSalesCanDoSalesTransitions). Coverage test asserts every `"sales"` transition also accepts `"head_of_sales"`.
  - Closing PR: **#119** (commit `3727d1aa`, 2026-05-06) — "fix(workflow,customers): grant head_of_sales access to subordinate quotes + customers (РОП-1, РОП-24)".
- **Likely root cause:** Pre-fix, `ALLOWED_TRANSITIONS` hard-coded `["sales", "admin"]` on every sales-owned transition. `head_of_sales` was added later but never wired into the matrix. РОП test was run against pre-#119 deployment.
- **Dependencies / RLS / migrations needed:** none — pure in-memory matrix.
- **Test approach:** unit test already lives at `tests/test_workflow_head_of_sales.py`. Browser re-test under `kravtsova.e@masterbearing.ru`: open subordinate's draft KP → «Отправить в закупку» → expect transition to `pending_procurement`.
- **Estimated complexity:** XS (verify deployment + browser smoke).

---

## Bug 2 — РОП Cust #1 (P4) — head_of_sales cannot enter subordinate's customer profile

**Status:** **ALREADY FIXED on main, needs re-test only.**

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/app/(app)/customers/[id]/page.tsx:47-59` — `salesGroupId` is now `await`-resolved BEFORE `canAccessCustomer`, then passed to it explicitly. Comment in file (line 41-46) explains the prior bug.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/customer/queries.ts:129-143` — `canAccessCustomer` short-circuits to `true` for any non-sales-only role, otherwise computes assigned ids via `getAssignedCustomerIds`.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/customer/__tests__/can-access-head-of-sales.test.ts` — 5 vitest cases guarding the contract.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/shared/lib/access.ts` — `getAssignedCustomerIds` expands `head_of_sales` via the `sales_group_id` join (verified by tests).
  - Closing PR: **#119** (same as bug 1).
- **Likely root cause:** prior shape ran `canAccessCustomer` in parallel with the salesGroupId fetch, so the access check always saw `salesGroupId=undefined` → fell through to the "just self" branch. Confirmed in commit message.
- **Dependencies / RLS / migrations needed:** none. NB: `kvota.customers` has no RLS (PR-119 commit message confirms — "Adding RLS would require parallel service-role bypass, scoped out as follow-up"). Access control is application-layer only.
- **Test approach:** vitest suite already in place. Browser re-test under `kravtsova.e`: click on a customer assigned to her subordinate → expect detail page (no 404).
- **Estimated complexity:** XS (verify deployment + browser smoke).

---

## Bug 3 — СтМоз C3 (P4) — `/customers` "Все статусы" dropdown does nothing for procurement_senior

**Status:** likely **NOT a code bug**, more a test-data limitation. Needs developer triage with browser repro.

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/customers/ui/customers-table.tsx:148-162` — Select is wired to `pushParams({ status })`, only meaningful values are `"active"` / `"inactive"`. "all" deletes the param.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/customer/queries.ts:69-70` — `if (status === "active") query = query.eq("status", "active"); if (status === "inactive") query = query.neq("status", "active");`
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/app/(app)/customers/page.tsx:1-47` — server page; no role-based gating on the filter param.
  - No write path for customer.status in code (no edit UI exists; status is read-only Badge in `customer-header.tsx:41` and `customers-table.tsx:253`).
- **Likely root cause:** the tester said «не могу проверить, так как не могу изменить статус» — they wanted to verify the filter by toggling a customer's status, but no edit affordance exists for any role. The dropdown itself is functional. The bug is that the test scenario can't be executed, NOT that the dropdown is broken.
  - Possible alternate: dropdown is a base-ui `Select` and relies on `defaultValue` — under some hydration paths the "all" option may not visibly reset. Browser-test needed.
- **Dependencies / RLS / migrations needed:** none (no edit path to gate).
- **Test approach:** browser-test with `procurement_senior` user — flip filter through Активные/Неактивные/Все статусы on existing data, assert URL + row counts change.
- **Estimated complexity:** S (likely a documentation/UX clarification, not a code change). Defer.

---

## Bug 4 — СтМоз C9 (P4) — Customer "Подробно" extra columns empty for procurement_senior

**Status:** likely **data-readiness, not a real visibility bug.**

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/customers/ui/customers-table.tsx:241-266` — expanded view renders `fin?.quotes_count ?? customer.quotes_count`, `fin?.revenue_usd`, `fin?.specs_count`, `fin?.profit_usd` from the `financials` Map.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/customer/queries.ts:574-591` — `fetchCustomerFinancials` calls RPC `get_customer_financials(p_org_id)` with all-org scope.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/migrations/222_add_customer_financials_rpc.sql:4-26` — RPC is `LANGUAGE sql STABLE SECURITY DEFINER` aggregating from `kvota.quotes`. RLS bypassed by definer.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/.kiro/steering/access-control.md` — **PROCUREMENT_STAGE_ONLY** tier explicitly documents that `procurement_senior` only sees quotes where `workflow_status = 'pending_procurement'`. Quotes at that early stage have no `total_amount_usd` / `total_profit_usd` (calc engine hasn't run).
- **Likely root cause:** No filtering by role for procurement_senior at the customer-financials level (RPC is org-scoped). Empty cells for procurement_senior reflect that procurement-stage quotes don't yet have totals/specs computed — not an RLS gap.
- **Dependencies / RLS / migrations needed:** none unless product wants to extend procurement_senior's financial view (would need a separate spec — outside steering doc's PROCUREMENT_STAGE_ONLY contract).
- **Test approach:** browser-test under `ekaterina.pl` — expand a customer that has finalized quotes; if rows still empty, then it's a real bug. Otherwise, mark as "expected per access-control.md".
- **Estimated complexity:** S (probably a no-op + UX message; large M if product decides to widen scope).

---

## Bug 5 — СтМоз Q6 (P3) — `/quotes` ВЕРСИЯ/СУММА/ПРИБЫЛЬ empty for procurement_senior

**Status:** **expected behavior per access-control.md contract** — same root as Bug 4.

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/quote/queries.ts:69-71` — `else if (isProcurementSeniorOnly(user.roles)) { query = query.eq("workflow_status", "pending_procurement"); }`. Confines list to procurement-stage only.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/quote/queries.ts:34` — query selects `total_amount_quote, total_profit_usd, version_count, current_version` directly from row. No column-level redaction.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/quotes-table-client.tsx:240-283` — Версия / Сумма / Прибыль columns rendered for everyone; no role filter applied to columns.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/shared/lib/roles.ts:125` — `isProcurementSeniorOnly` def.
- **Likely root cause:** at `pending_procurement` stage `total_amount_quote`, `total_profit_usd`, and `version_count` are all unset (calc engine + version flow hasn't run). The columns render `—`. This is the inverse of "they can't see it" — they can, but the data isn't computed yet.
- **Dependencies / RLS / migrations needed:** none. Possibly hide these columns for procurement_senior to remove confusion (add a `hideColumnsFor` map keyed by role).
- **Test approach:** browser-test as `ekaterina.pl`; if a quote has totals filled at procurement stage and they STILL render empty → real bug. Otherwise UX-only fix (hide columns or show «—» tooltip "Доступно после расчёта").
- **Estimated complexity:** XS-S (hide columns for the role) or close as not-a-bug.

---

## Bug 6 — МОЗ #58 (P3) — МОЗ can edit «Контакт» field on quote profile

**Status:** **REAL BUG** — both client + server unprotected.

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/context-panel/context-panel.tsx:127-141` — renders `<ContactDropdownSelect>` unconditionally; `userRoles` is in scope (line 52, passed by `quote-detail-shell.tsx:123`) but not used to gate this control.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/context-panel/context-panel.tsx:147-157` — same applies to `<AddressDropdownSelect>` (sibling, identical mutation pattern).
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/context-panel/contact-dropdown-select.tsx:96-109,111-122` — `handleSelect` / `handleClear` call `patchQuote(quoteId, { contact_person_id })` directly via Supabase JS, no server-side role check.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/entities/quote/mutations.ts:1885-1901` — `patchQuote` is a thin Supabase update; no auth/role enforcement, no `/api/*` endpoint.
- **Likely root cause:** the Контакт dropdown was built for sales-side editing but never gated. Procurement (МОЗ) sees the same panel and can write `contact_person_id` (and `delivery_address`).
- **Dependencies / RLS / migrations needed:**
  - Frontend: gate `<ContactDropdownSelect>` and `<AddressDropdownSelect>` behind a role check (sales / head_of_sales / admin). Render read-only `<span>` otherwise. Pattern already used in `quote-detail-shell.tsx`.
  - Backend (defense in depth): per `.claude/rules/api-first.md`, this should be a Python `/api/quotes/{id}` PATCH endpoint with role-allowlist; bypass via direct Supabase write is the architectural smell. Short-term: add an RLS UPDATE policy on `kvota.quotes` restricting `contact_person_id` / `delivery_address` writes to sales+admin.
- **Test approach:** vitest dom-test on `context-panel.tsx` — render with `userRoles=['procurement']` → assert no `<button>` for contact, plain text. Plus integration: as МОЗ, attempt patchQuote → expect 403/RLS denial.
- **Estimated complexity:** S (frontend gate) + S (Python endpoint or RLS UPDATE policy on `kvota.quotes`). Combined M.

---

## Bug 7 — МОЗ #93 (P3) — «Создать КП поставщику» modal too wide, buttons unreachable

**Status:** **needs browser repro to confirm.** Code looks reasonable.

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/procurement-step/invoice-create-modal.tsx:253` — `<DialogContent className="sm:max-w-lg z-[200]">`. `max-w-lg` = 32rem.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/procurement-step/invoice-create-modal.tsx:262-524` — modal body has 10+ form sections (supplier, buyer, country, city, incoterms, currency, VAT, boxes (multi-row), file, items list).
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/components/ui/dialog.tsx:42-67` — `DialogContent` has `max-h-[calc(100dvh-2rem)] overflow-y-auto`, footer is `sticky bottom-0` (line 99 of dialog.tsx). On paper, footer should always be reachable.
- **Likely root cause:** unclear from code. Hypotheses (in order of likelihood):
  1. **Combobox dropdown overflows the viewport** — `<SearchableCombobox>` for Поставщик/Buyer renders below the input; in some screen sizes its menu pushes layout. Inspect `searchable-combobox.tsx` in browser.
  2. **`sticky bottom-0` not honoring `overflow-y-auto`** in some Safari/iOS rendering — base-ui Popup uses `position: fixed`, and `sticky` inside a fixed-positioned scrollable container is fragile.
  3. **`fixed top-1/2 left-1/2 -translate-y-1/2`** with tall content on small screens (laptop in split-screen, ~720px height) — the centered popup can extend past viewport top, footer pushed below visible area despite sticky (base-ui issue).
- **Dependencies / RLS / migrations needed:** none (pure CSS/layout).
- **Test approach:** browser-test the actual viewport reported. Use `mcp__plugin_playwright_playwright__browser_take_screenshot` at typical viewport (1366×768, 1280×720). If footer is visible in screenshots, bug is environmental — escalate to tester for screen-size reproduction.
- **Estimated complexity:** S (likely a CSS tweak — switch popup from `top-1/2 + translate` centering to flex-centered overlay, or make modal body max-height dynamic). Could also consider `sm:max-w-md` (28rem) since most fields are short.

---

## Bug 8 — МОЗ #94 (P4) — КПП header data duplicates content below

**Status:** **ALREADY FIXED on main, needs re-test only.**

- **Files:**
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx:826-880` — header chips `pickup_location` / `incoterms` / `weight` / `cargo_places` are now gated on `!expanded`. When the card is expanded, the full editable form below replaces them.
  - `/Users/andreynovikov/workspace/tech/projects/kvota/onestack/frontend/src/features/quotes/ui/procurement-step/__tests__/invoice-card-header-dup.dom.test.tsx` — 4 vitest dom tests pinning the contract.
  - Closing PR: **#110** (commit `0ddde9eb`) — "fix(procurement): hide redundant header chips when invoice-card expanded (РОЗ-107/108, МОЗ-94)".
- **Likely root cause:** chips and form duplicated the same fields. Fix: hide chips on expand.
- **Dependencies / RLS / migrations needed:** none.
- **Test approach:** vitest already in place. Browser re-test: open КПП card → verify chips disappear when card is expanded; chips return when collapsed.
- **Estimated complexity:** XS (verify only).

---

## Cross-cutting observations

1. **3 of 8 bugs are already fixed** (Bugs 1, 2, 8 — PRs #119 and #110). Likely the test was conducted against a pre-merge environment. Action: confirm prod deployment timestamp of PR #119 (2026-05-06) and PR #110, ask tester to re-run on current prod.

2. **2 of 8 are "expected behavior"** (Bugs 4, 5 — `procurement_senior` PROCUREMENT_STAGE_ONLY contract per `.kiro/steering/access-control.md`). Either close as not-a-bug or do UX work to hide unavailable columns for that role.

3. **Bug 6 (МОЗ Контакт edit) is the highest-value real bug** — it's a write-permission gap with a clean fix at two layers (component gate + RLS policy on `kvota.quotes` UPDATE for sensitive columns). The same gap applies to `delivery_address` via `<AddressDropdownSelect>`.

4. **Bug 3 (С3 status filter) needs tester clarification** — the dropdown works in code; the tester just couldn't construct a test case because no role can edit customer.status. This may be product-design feedback ("we want a way to suspend a customer") rather than a defect.

5. **Bug 7 (modal width)** — code review didn't reveal a smoking gun; needs in-browser reproduction at the user's viewport. Recommend developer agent dives in with Playwright at multiple viewport sizes.

6. **Common pattern: direct Supabase writes from frontend skip role enforcement.** `patchQuote` is one example; per `.claude/rules/api-first.md` such mutations should go through Python `/api/*` endpoints. This is a recurring architectural weakness — multiple bug clusters likely trace to it. Worth a dedicated tracking ticket.
