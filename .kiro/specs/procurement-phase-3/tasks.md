# Implementation Plan — Procurement Phase 3

Tasks grouped by architectural boundary to maximize parallel-capable work. Parallel-capable tasks are marked with `(P)`.

**Wave structure** (high-level task dependencies):

- **Wave 1** (parallel): Sections 1, 2, 3 — foundational shared modules. Nothing below them in the codebase, so all three can be implemented simultaneously by independent workers.
- **Wave 2** (parallel, blocked on Wave 1): Sections 4, 5, 6, 7 — concrete feature integration. All four consume primitives from Wave 1 but touch mostly disjoint file sets (single collision: `invoice-create-modal.tsx` is owned by Section 4, not Section 7, to resolve the currency import overlap).
- **Wave 3** (serial): Section 8 — verification, commit, deploy, post-deploy smoke. Runs after Wave 2 lands locally.

---

## 1. Shared Geo Module — Countries and Country Picker

- [ ] 1.1 Implement the `countries.ts` module with Intl-backed bilingual data
  - `frontend/src/shared/ui/geo/countries.ts`
  - Build `COUNTRIES` at module load from `Intl.supportedValuesOf("region")` filtered to alpha-2 codes, with `Intl.DisplayNames` for `"ru"` and `"en"` labels; sort by Russian name via `localeCompare`
  - Export `Country` interface, `COUNTRIES` readonly list, `findCountryByCode(code)`, `findCountryByName(name, locale?)` helpers
  - Graceful empty-list fallback when `Intl.supportedValuesOf` is missing
  - Vitest unit tests for all helpers + bilingual lookup + unknown-code handling
  - _Requirements: 1.10, 1.11, 1.12, 8.1, 8.2_

- [ ] 1.2 Implement the `CountryCombobox` component
  - `frontend/src/shared/ui/geo/country-combobox.tsx`
  - Single-select controlled component over `@base-ui/react` Popover + Input; matches `shared/ui/data-table/column-filter.tsx` visual pattern
  - Features: search filter (matches Russian name, English name, ISO-2 code), keyboard navigation (ArrowUp/ArrowDown/Enter/Escape), virtual focus with `scrollIntoView`, clearable, disabled, `displayLocale` override
  - Dropdown option layout: `{nameRu} · {nameEn}` with ISO-2 code as muted monospace tail
  - Vitest tests for trigger rendering, search filter, keyboard navigation, clear affordance, `displayLocale` switch, empty-state message
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 8.3, 8.4_

- [ ] 1.3 Create the `geo/index.ts` barrel export
  - `frontend/src/shared/ui/geo/index.ts`
  - Re-export `CountryCombobox`, `CountryComboboxProps`, `CityCombobox`, `CityComboboxProps`, `CityComboboxValue`, `COUNTRIES`, `Country`, `findCountryByCode`, `findCountryByName`
  - Public API only — no internal helper leakage
  - _Requirements: enables downstream imports for Sections 4, 5, 7_

---

## 2. Cities Search API and CityCombobox

- [ ] 2.1 (P) Harden `services/here_service.py` with LRU cache and pycountry-backed alpha-3→alpha-2 mapping
  - Add `functools.lru_cache(maxsize=256)` on an inner cached helper so repeated typeahead calls are de-duplicated per process
  - Replace hardcoded 28-country alpha-3 dict with `pycountry.countries.get(alpha_3=...)` lookup; fall back to the existing dict when `pycountry` import fails
  - Add `pycountry>=24.6.1` to `requirements.txt`
  - Python regression tests: (a) LRU cache verified via mocked HERE client seeing only one call across two identical invocations; (b) alpha-3→alpha-2 correct for at least five countries outside the existing dict (BR, EG, NG, PK, AR); (c) graceful fallback when `pycountry` absent
  - Must not regress the legacy `/api/cities/search` HTMX endpoint — existing tests in `tests/test_city_autocomplete_here.py` continue to pass
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [ ] 2.2 (P) Add the `GET /api/geo/cities/search` JSON endpoint in `main.py`
  - New `@rt("/api/geo/cities/search")` handler wrapping `services.here_service.search_cities`
  - Query params: `q` (required, min 2 chars after strip), `limit` (optional, default 10, clamped 1..25)
  - Returns structured JSON `{success, data: [{city, country_code, country_name_ru, country_name_en, display}, ...]}`
  - Auth: Supabase JWT (primary) or legacy session cookie (fallback) per `feedback_dual_auth_api.md` — 401 on missing auth
  - Graceful degradation: HERE errors return empty data array with 200 status and server-side log (not a 500)
  - Structured docstring with Path/Params/Returns/Side Effects/Roles per `api-first.md` convention
  - Python tests for all response codes (200 valid, 200 empty, 400 invalid query, 401 unauth)
  - Legacy `/api/cities/search` HTMX endpoint remains untouched
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 8.5_

- [ ] 2.3 Implement the `CityCombobox` component
  - `frontend/src/shared/ui/geo/city-combobox.tsx`
  - Typeahead input with 300ms debounce, minimum 2-character query, fetches `/api/geo/cities/search` via the existing shared `api-browser` helper
  - Renders loading spinner in popover header during request, "Ничего не найдено" on empty result, "Поиск недоступен" on network/5xx error
  - On selection, invokes `onChange` with structured `CityComboboxValue` and optional `onCountryChange` with the ISO-2 code so a sibling CountryCombobox can stay in sync
  - Vitest tests for debounce, min query length, success path, empty result, error path, loading state
  - Depends on 2.2 for the endpoint contract
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10_

---

## 3. Shared Constants — Incoterms and Currencies

- [ ] 3.1 (P) Create the `INCOTERMS_2020` shared constant and helper
  - `frontend/src/shared/lib/incoterms.ts`
  - Export `Incoterm` interface, readonly `INCOTERMS_2020` array containing all 11 codes in conventional order (`EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF`) with short human labels
  - Export `isValidIncoterm(code)` type guard
  - Vitest unit test asserting `INCOTERMS_2020.length === 11`, validation helper, and list completeness against Incoterms 2020 standard
  - _Requirements: 10.1, 10.2, 10.7_

- [ ] 3.2 (P) Create the `shared/lib/currencies.ts` frontend currency module
  - `frontend/src/shared/lib/currencies.ts`
  - Export `SUPPORTED_CURRENCIES` readonly array mirroring `services/currency_service.py` after Section 7 expansion (all 10 codes: USD, EUR, RUB, CNY, TRY, AED, KZT, JPY, GBP, CHF)
  - Export `CURRENCY_LABELS` map for display purposes and `isSupportedCurrency` type guard
  - Vitest unit test asserting length and membership
  - _Requirements: 7.6_

---

## 4. Supplier Invoice Schema and Integration

_Depends on Sections 1 and 3._

- [ ] 4.1 Write migration 266 for `invoices.pickup_country_code` and `invoices.supplier_incoterms`
  - `migrations/266_add_shipping_country_and_incoterms_to_invoices.sql`
  - Additive: `ALTER TABLE kvota.invoices ADD COLUMN IF NOT EXISTS pickup_country_code CHAR(2)` and `supplier_incoterms TEXT`
  - CHECK constraint: `pickup_country_code IS NULL OR pickup_country_code ~ '^[A-Z]{2}$'`
  - Column comments describing purpose, nullable, no default
  - Append row to `kvota.schema_migrations`
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 4.2 Apply migration 266 on the dev VPS and regenerate frontend types
  - Run `./scripts/apply-migrations.sh 266` over SSH to beget-kvota
  - `cd frontend && npm run db:types` locally to regenerate `frontend/src/shared/types/database.types.ts`
  - Verify `pickup_country_code?: string | null` and `supplier_incoterms?: string | null` are present on `invoices.Row/Insert/Update`
  - _Requirements: 5.5_

- [ ] 4.3 (P) Extend the `createInvoice` mutation with dual-write logic
  - `frontend/src/entities/quote/mutations.ts`
  - Add `pickup_country_override`, `pickup_country_code`, `supplier_incoterms` to the input contract as optional
  - Preserve the 2026-04-10 `pickup_country` supplier-country auto-derive (lines ~373-387); extend the same code path to ALSO resolve `pickup_country_code` via `findCountryByName(pickup_country, "ru")`
  - Explicit user choice (override/code from the form) takes precedence over supplier-derived defaults for both fields
  - Insert writes BOTH `pickup_country` (text) and `pickup_country_code` (ISO-2) together
  - Extend `frontend/src/entities/quote/__tests__/mutations.test.ts` with 3 new cases covering: (a) explicit user choice wins; (b) supplier-derived default populates both fields via `findCountryByName`; (c) supplier country unknown to ICU — text written, code stays null; plus regression that existing supplier-country derivation tests still pass
  - _Requirements: 5.6, 5.7, 5.9, 5.10, 9.1, 9.2, 9.3_

- [ ] 4.4 (P) Wire `CountryCombobox`, Incoterms dropdown, and shared currencies into the invoice create modal
  - `frontend/src/features/quotes/ui/procurement-step/invoice-create-modal.tsx`
  - Add `CountryCombobox` labeled "Страна отгрузки" above the city input; store both the ISO-2 code and the Russian display name in local state
  - Add "Условия поставки" dropdown consuming `INCOTERMS_2020` with a leading "— не указано —" null option
  - Replace the local `CURRENCIES = [...]` constant at line 25 with an import from `@/shared/lib/currencies`
  - Submit payload passes `pickup_country_override`, `pickup_country_code`, `supplier_incoterms` to `createInvoice`
  - _Requirements: 5.6, 5.7, 5.8, 7.6, 10.3_

- [ ] 4.5 (P) Update `invoice-card.tsx` to display pickup country code and Incoterms
  - `frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx`
  - Show `pickup_country_code` (resolved to Russian name via `findCountryByCode`) and `supplier_incoterms` in the summary row when populated
  - _Requirements: 5.11_

---

## 5. Quote-Level Incoterms Upgrade and Delivery Country Picker

_Depends on Sections 1 and 3._

- [ ] 5.1 (P) Upgrade the new-quote dialog with the delivery country picker and 11-entry Incoterms dropdown
  - `frontend/src/features/quotes/ui/create-quote-dialog.tsx`
  - Replace the plain-text `deliveryCountry` input with the `CountryCombobox`; store Russian display name in the existing `delivery_country` text column (no schema change for quotes)
  - On edit-mode seeding, resolve historical `delivery_country` via `findCountryByName("...", "ru")`; display placeholder when no match (graceful legacy-data signal)
  - Rewrite the hardcoded 5-value Incoterms `<select>` at line 52 to consume `INCOTERMS_2020` — users can now pick any of the 11 terms
  - Delivery city input remains plain text (out of Phase 3 scope)
  - _Requirements: 10.4, 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 5.2 (P) Upgrade the calculation form Incoterms dropdown
  - `frontend/src/features/quotes/ui/calculation-step/calculation-form.tsx`
  - Rewrite the hardcoded 5-value Incoterms `<select>` at line 20 to consume `INCOTERMS_2020`
  - No other changes to the form
  - _Requirements: 10.5_

---

## 6. MOQ on Quote Items

_Independent of Sections 1, 2, 3, 4, 5 — can run fully parallel in Wave 2._

- [ ] 6.1 Write migration 267 for `quote_items.min_order_quantity`
  - `migrations/267_add_min_order_quantity_to_quote_items.sql`
  - Additive: `ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS min_order_quantity NUMERIC`, nullable, no default
  - Column comment noting informational-only status (not a calculation engine input)
  - Append row to `kvota.schema_migrations`
  - _Requirements: 6.1_

- [ ] 6.2 Apply migration 267 and regenerate frontend types
  - Run `./scripts/apply-migrations.sh 267` over SSH
  - Regenerate `database.types.ts`; verify `min_order_quantity?: number | null` is present on `quote_items.Row/Insert/Update`
  - Extend the `QuoteItem` interface in `frontend/src/entities/quote/types.ts` (handsontable consumer) with `min_order_quantity: number | null`
  - _Requirements: 6.2_

- [ ] 6.3 Add the MOQ column, warning renderer, and totals badge to the procurement handsontable
  - `frontend/src/features/quotes/ui/procurement-step/procurement-handsontable.tsx`
  - Insert `"min_order_quantity"` into `COLUMN_KEYS` immediately after `"quantity"` (index 6); extend `RowData` interface; update `itemToRow` mapper
  - Insert header label `"МИН. ЗАКАЗ"` in the headers array after "Кол"
  - Insert numeric column descriptor with a custom cell renderer that draws a warning icon + tooltip "Количество ниже минимального заказа поставщика" when `row.min_order_quantity != null && row.quantity < row.min_order_quantity`
  - Extend `handleAfterChange` numeric-parse branch to include `"min_order_quantity"`
  - Verify every hardcoded column index after position 6 is shifted correctly (particularly `lockedColIndices` — do NOT lock MOQ, it is editable)
  - Add a count badge "⚠ MOQ: {N}" in the procurement step totals area, computed via a `useMemo` over the rows where `quantity < min_order_quantity`; hidden when N is zero
  - Warning is non-blocking — save, approve, and calculation all continue to work normally
  - Calculation engine files (`calculation_engine.py`, `calculation_mapper.py`, `calculation_models.py`) stay untouched
  - Vitest test for the warning-detection logic in isolation (pure function extracted from the renderer)
  - _Requirements: 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 9.4_

---

## 7. Extra Currencies — Backend and Drift Fix

_Depends on Section 3 (frontend currency module). Independent of Sections 4, 5, 6._

- [ ] 7.1 (P) Write migration 268 loosening the `deal_logistics_expenses` currency constraint
  - `migrations/268_loosen_deal_logistics_expenses_currency_check.sql`
  - Drop the existing `deal_logistics_expenses_currency_check` constraint
  - Re-add it with a format-only regex check: `currency ~ '^[A-Z]{3}$'`
  - Constraint name preserved for operational continuity
  - Append row to `kvota.schema_migrations`
  - Migration 190 file is not modified — new migration drops and re-adds cleanly
  - _Requirements: 7.4, 7.5, 9.6_

- [ ] 7.2 Apply migration 268 on the dev VPS
  - Run `./scripts/apply-migrations.sh 268` over SSH
  - Verify the new constraint accepts AED/KZT/JPY/GBP/CHF via a direct psql smoke test
  - _Requirements: 7.5_

- [ ] 7.3 Extend `services/currency_service.py` with AED, KZT, JPY, GBP, CHF
  - `services/currency_service.py`
  - Extend `SUPPORTED_CURRENCIES` (line 20) to 10 entries
  - Extend `CBR_CURRENCY_CODES` (line 23-28) and `CBR_CHAR_CODES` (line 31-36) with the 5 new mappings (AED→R01230, KZT→R01335, JPY→R01820, GBP→R01035, CHF→R01775)
  - Update `required_currencies` list at line 135 and line 301 if they hardcode the first-five subset (review during implementation)
  - Ensure JPY `Nominal=100` handling works through `convert_to_usd` (CBR publishes JPY rate per 100 units) — verify with a test case
  - Python regression tests: (a) `SUPPORTED_CURRENCIES` length is 10; (b) `convert_to_usd(1000, 'AED')` in plausible range (~100-500 USD); (c) JPY handling correct; (d) CBR mappings complete
  - _Requirements: 7.1, 7.2, 7.3, 7.7_

- [ ] 7.4 (P) Switch sibling Python services to import `SUPPORTED_CURRENCIES` from `currency_service`
  - `services/logistics_expense_service.py` (line 34), `services/supplier_invoice_payment_service.py` (line 67), `services/supplier_invoice_service.py` (line 72)
  - Replace local hardcoded literal `["USD", "EUR", "RUB", "CNY", "TRY"]` with `from services.currency_service import SUPPORTED_CURRENCIES`
  - No semantic change — these modules already use the list the same way
  - _Requirements: 7.1_

- [ ] 7.5 (P) Update remaining frontend currency arrays to import from `shared/lib/currencies`
  - `frontend/src/features/quotes/ui/logistics-step/additional-expenses.tsx` (line 15)
  - `frontend/src/features/quotes/ui/logistics-step/route-segments.tsx` (line 9)
  - Replace local `CURRENCIES = [...]` with `import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies"`
  - Fixes the pre-existing drift (both files were missing TRY) as a free side effect
  - Note: `invoice-create-modal.tsx` currency array is owned by Section 4 (4.4) to avoid file collision
  - _Requirements: 7.6_

- [ ] 7.6 Write the migration 268 constraint regression test and update the brittle count assertion
  - `tests/test_migration_268_currency_constraint.py` (new): asserts that inserts into `kvota.deal_logistics_expenses` with AED/KZT/JPY/GBP/CHF succeed, and that inserts with `xx`/`usd`/`X3`/empty fail the format check
  - `tests/test_logistics_expense_service.py:366` (extend): update `assert len(SUPPORTED_CURRENCIES) == 5` → `== 10`
  - Review `tests/test_logistics_service.py:998` to confirm its hardcoded `['USD','EUR','RUB','CNY','GBP']` is a pre-existing unrelated subset and not broken by expansion
  - _Requirements: 7.8, 9.8_

---

## 8. Verification, Commit, Deploy, Handoff

_Serial tail. Depends on Sections 1-7 landing locally._

- [ ] 8.1 Run the full Python test suite locally
  - `pytest -v` from repo root
  - Expect: all existing tests pass + new tests from 2.1, 2.2, 7.3, 7.6 pass
  - Fix any collateral regressions before proceeding
  - _Requirements: 9.8_

- [ ] 8.2 Run the full frontend test suite locally
  - `cd frontend && npm test`
  - Expect: all 5 new vitest files pass (countries, country-combobox, city-combobox, incoterms, currencies) plus extended mutations.test.ts
  - _Requirements: 9.8_

- [ ] 8.3 Browser-test Phase 3 on localhost:3000 with prod Supabase
  - Phase 5e of lean-tdd: generate test manifest from requirements.md REQ IDs + git diff, run against `http://localhost:3000` with login `admin@test.kvota.ru` / `Mb2026Beta!`
  - Manifest coverage: new-quote dialog (delivery country picker + 11-entry Incoterms), supplier invoice create modal (country picker writes both fields, Incoterms dropdown, currency dropdown shows 10), procurement handsontable (MOQ column renders, warning icon fires, totals badge shows count), calculation form Incoterms dropdown
  - Smoke: no console errors, all tested pages load under 3s
  - Fix any blocker-priority failures before commit
  - _Requirements: all UI-facing REQs_

- [ ] 8.4 Commit, push, and monitor GitHub Actions deploy
  - Git commits split by section if it makes review easier; one PR bundling all sections of Phase 3
  - `/code-review` run on the PR; resolve CRITICAL findings via fix loop if any
  - Watch CI for green, then auto-deploy to beget-kvota
  - _Requirements: rollout plan from design §Rollout_

- [ ] 8.5 Post-deploy smoke test on https://app.kvotaflow.ru
  - Light verification per lean-tdd Phase 7b: navigate each unique URL from the Phase 5e manifest, confirm HTTP 200, no console errors, load time under 5s
  - Record any console errors as non-blocker warnings in the session file
  - _Requirements: rollout plan verification_

- [ ] 8.6 Add v0.5.0 changelog entry and close ClickUp 86afua0qb
  - Add a changelog entry noting the five Phase 3 improvements (geo pickers, shipping country, Incoterms, MOQ, extra currencies)
  - Close ClickUp task `86afua0qb` with a link to https://app.kvotaflow.ru/quotes (or the invoice-create flow) so the reporter can verify the bug is fixed
  - Append final event line to `tmp/sessions/session_2026-04-10.md` marking Phase 3 complete
  - _Requirements: session tracking_
