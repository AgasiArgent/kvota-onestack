# Research Log — Procurement Phase 3

**Date:** 2026-04-10
**Status:** Discovery complete; informs `design.md`.

## Summary

Integration-focused discovery (this is an Extension of an existing system, not greenfield). Discovery sources:

1. Plan doc `docs/plans/2026-04-10-procurement-phase-3.md` — user-authored scope and locked decisions.
2. Code intelligence report from a general-purpose subagent that scanned `frontend/src/`, `main.py`, `services/`, `migrations/`, and `tests/` for integration points, current fields, and test patterns.
3. Steering docs in `.kiro/steering/` — `api-first.md`, `database.md`, `access-control.md`, `structure.md`, `tech.md`.
4. Today's prior session work: customs/logistics fix (`tmp/sessions/session_2026-04-10.md`, commits `08a56ae`, `cc29010`) that added `pickup_country` auto-derivation.

No external WebSearch was needed — all dependencies (`Intl.DisplayNames`, `Intl.supportedValuesOf`, `pycountry`, HERE Geocode API, CBR daily XML) are already in use or are standardized platform APIs.

---

## Research Log

### Topic 1: Country data source for CountryCombobox

**Question:** Where do we get the country list and bilingual labels from?

**Findings:**

- **Correction (discovered during implementation, Wave 1 §1):** `Intl.supportedValuesOf` is NOT a universal enumerator. Per the ECMA-402 spec (and MDN), it accepts only these keys: `"calendar"`, `"collation"`, `"currency"`, `"numberingSystem"`, `"timeZone"`, `"unit"`. `"region"` is NOT a valid key. V8 (Node 25.9 / V8 13.x) throws `RangeError: Invalid key : region` when called. Earlier discovery notes claimed `"region"` was supported — this was incorrect.
- There is an active ECMA-402 proposal to add `"region"` (and `"language"`, `"script"`), but no runtime has shipped it yet as of 2026-04.
- `Intl.DisplayNames` with `type: "region"` DOES work and returns locale-appropriate display names for any ISO 3166-1 alpha-2 code from the ICU data bundled with the runtime. This is the only piece of the Intl API we can rely on today.
- Node 20+ and Chromium 99+ both ship full ICU, so server-rendered pages and hydrated client pages produce identical output (no hydration mismatch).
- Candidate library alternatives (`i18n-iso-countries` ~40KB with one locale, `world-countries` ~180KB) add dependency burden for no meaningful benefit.
- ICU's historical region codes (e.g. `DD` → "Germany" for East Germany, `SU` → "Russia", `YU` → "Serbia") are still recognised by `Intl.DisplayNames`, which would produce duplicate entries sharing the same name but different codes. `Intl.getCanonicalLocales("und-XX")` canonicalises deprecated codes to their current form, so comparing the input code to the canonicalised form filters historical codes out.

**Decision:** Two-tier enumeration implemented in `frontend/src/shared/ui/geo/countries.ts`:

1. **Preferred path:** Attempt `Intl.supportedValuesOf("region")` inside a `try/catch`. If a future V8/Node ships the ECMA-402 proposal, this becomes the active path automatically with no code change. Filter results to `/^[A-Z]{2}$/`.
2. **Fallback path (today's reality):** Enumerate every two-letter pair AA..ZZ (676 codes), pass each through `Intl.DisplayNames({ type: "region" }).of(code)`, and keep only the ones whose return value differs from the input code (ICU returns the code unchanged for non-regions). Then drop codes that `Intl.getCanonicalLocales` rewrites to something different (removes the DD/SU/YU family of deprecated codes that would otherwise duplicate existing countries).

Both paths feed the same `buildCountries()` loop, which produces two `Intl.DisplayNames` instances (`"ru"`, `"en"`) and sorts by Russian name via `localeCompare(..., "ru")`. The resulting `COUNTRIES` list contains ~264 entries (above the 200-country sanity floor), all canonical ISO 3166-1 alpha-2 codes with bilingual labels. Zero dependencies, zero maintenance.

**Implication for design:** Country data is a static module export, not a query. No loading state, no cache, no network. The enumeration cost is paid once at module load (~676 `DisplayNames.of` calls plus a constant-time canonicalisation check per code) and amortised across every render.

**Cross-reference:** Implementation lives at `frontend/src/shared/ui/geo/countries.ts`. The `enumerateRegionCodes()` helper contains both the preferred and fallback paths; `isCanonicalRegionCode()` drops deprecated codes. See test coverage in `frontend/src/shared/ui/geo/__tests__/countries.test.ts`.

**Sources:** MDN `Intl.supportedValuesOf` (documents accepted keys), ECMA-402 spec §18.3.1, Wave 1 §1 V8 `RangeError` reproduction, Node.js 20 ICU bundling docs.

### Topic 2: HERE Geocode API — existing integration state

**Question:** What is the current state of `services/here_service.py` and what are its known flaws?

**Findings:**

- `services/here_service.py` is 124 lines. Structure: `_call_here_api` → `_normalize_item` → `search_cities`.
- **Flaw 1 — alpha3→alpha2 mapping:** lines 78–85 contain a hardcoded dict covering only 28 countries (EU core + major Asia/ME). Unmapped countries fall back to `country_code[:2]` at line 86, which silently produces wrong codes (e.g., "BR" instead of empty for Brazil alpha-3 "BRA" by accident of string slicing).
- **Flaw 2 — no caching:** every `search_cities` call hits the HERE API. Under typeahead load this will hit the free-tier ceiling fast.
- **Flaw 3 (intentional, not a flaw):** filters HERE result types to `"locality"` only at line 117, dropping neighborhoods and districts. Correct for a city picker.
- Error handling is robust: any exception caught and returns `[]` (graceful degradation — callers see empty list, not a crash).
- Existing tests: `tests/test_city_autocomplete.py` + `tests/test_city_autocomplete_here.py` — these test the FastHTML `/api/cities/search` HTMX endpoint, not the underlying service directly. Phase 3 should add service-level tests for the cache + alpha3/alpha2 correctness.

**Decision:** Keep HERE; fix both flaws in place.

1. For alpha3→alpha2, use `pycountry` (ISO 3166 standard library) when available, falling back to the hardcoded dict. `pycountry` is already not installed — need to add to `requirements.txt`.
2. For caching, wrap `search_cities` with `functools.lru_cache(maxsize=256)`. LRU is process-local and ephemeral, which is correct — stale city data over process lifetime is not a concern at OneStack's scale.

**Implication for design:** Adding `pycountry` is a new backend dependency. Size impact: ~8MB installed (includes all ISO databases). Acceptable for a Python backend.

**Sources:** Code-intelligence report, `services/here_service.py` direct read, pycountry PyPI docs.

### Topic 3: Invoice create modal — integration strategy

**Question:** How does the new CountryCombobox integrate with `invoice-create-modal.tsx` without regressing today's 2026-04-10 customs/logistics fix?

**Findings:**

- Canonical table for procurement КП is `kvota.invoices` (NOT `kvota.supplier_invoices`, which is a finance-only payment tracking table — per steering `database.md`).
- Current modal at `frontend/src/features/quotes/ui/procurement-step/invoice-create-modal.tsx`:
  - Line 60: `const [city, setCity] = useState("")` — free text only, no country field.
  - Line 136: `pickup_city: city || undefined` — only city goes in.
  - Line 25: `const CURRENCIES = ["USD", "EUR", "CNY", "RUB"]` — already drifted from backend (missing TRY).
- `createInvoice` mutation at `frontend/src/entities/quote/mutations.ts` lines 355–412:
  - Lines 373–387 auto-derive `pickupCountry` from `suppliers.country` when `supplier_id` is set. This is the 2026-04-10 customs/logistics fix that must not regress.
  - Line 399 onwards: insert into `invoices` table.
  - Supplier is queried via `supabase.from("suppliers").select("country")`.
- `suppliers.country` is free-text Russian (e.g., "Турция"), not an ISO code. There is no `suppliers.country_code` column.
- Existing regression tests: `frontend/src/entities/quote/__tests__/mutations.test.ts` lines 115–200 cover the supplier-country derivation in 3 cases.

**Decision:** The new dual-write pattern:

- When the user explicitly picks a country via CountryCombobox, the modal passes BOTH `pickup_country` (Russian display name) AND `pickup_country_code` (ISO-2) to `createInvoice`.
- When the user does NOT pick a country (supplier is selected but country input is empty), `createInvoice` still runs its existing supplier-country derivation AND ALSO calls the new `findCountryByName(supplier.country, "ru")` helper to resolve an ISO-2 code. If the helper returns `undefined` (name not in the ICU dictionary), `pickup_country_code` stays null — graceful degradation.
- User's explicit choice always wins over supplier-derived default (for both fields).

**Implication for design:**

- `findCountryByName` is a name→code helper exported from `@/shared/ui/geo` — Requirement 1.12. It iterates `COUNTRIES` once and matches case-insensitively against `nameRu` or `nameEn` depending on the locale argument. This is O(n) over 250 entries — negligible cost.
- `createInvoice` signature adds a new optional `pickup_country_code?: string` parameter. When absent, the function still derives via supplier country name → `findCountryByName`.
- Existing regression tests at lines 115–200 are extended to assert `pickup_country_code` is populated correctly in all three scenarios.

**Sources:** Code-intel report section 2, `frontend/src/entities/quote/mutations.ts` direct spot-read, steering `database.md` two-invoice-table rule.

### Topic 4: Incoterms shared constant — current drift

**Question:** Where are Incoterms defined today and how do we consolidate without breaking existing data?

**Findings:**

- Two places currently hardcode Incoterms as dropdown options with only 5 values:
  1. `frontend/src/features/quotes/ui/create-quote-dialog.tsx` line 52: `["DDP","DAP","CIF","FOB","EXW"]`
  2. `frontend/src/features/quotes/ui/calculation-step/calculation-form.tsx` line 20: same 5 values.
- These dropdowns write to `quotes.incoterms` (text column, `database.types.ts` line 3655) and `quote_versions.offer_incoterms` (text column, line 3441).
- There's also a pre-existing field-name inconsistency: `QuoteDetail.offer_incoterms` in `frontend/src/entities/quote/types.ts` vs `quote.incoterms` in `frontend/src/features/quotes/ui/pdf/kp-document.tsx:376`. This is pre-existing tech debt and is explicitly out of Phase 3 scope.
- Incoterms 2020 standard defines eleven terms: EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF. The "D" group (DAP, DPU, DDP) covers delivery-at-destination; the "F" and "C" groups cover free-carrier and cost-and-freight variants; "EXW" is ex-works. "DPU" replaced the legacy "DAT" in 2020.
- Existing stored values are all within the 5-value subset — expansion from 5 to 11 is strictly additive, no stored value becomes invalid.

**Decision:**

- Create `frontend/src/shared/lib/incoterms.ts` with a typed `INCOTERMS_2020` constant (11 entries, each `{ code, label }`) and an `isValidIncoterm` guard.
- Both existing dropdowns consume `INCOTERMS_2020` — their stored values remain valid because the subset is preserved.
- The new supplier Incoterms dropdown on the invoice create modal consumes the same constant.

**Implication for design:** Single source of truth. If Incoterms 2030 ships with new terms, we edit one file and every dropdown updates.

**Sources:** Code-intel report section 7, ICC Incoterms 2020 public summary, direct reads of `create-quote-dialog.tsx` and `calculation-form.tsx`.

### Topic 5: Procurement handsontable column insertion

**Question:** Where does the MOQ column fit in the procurement handsontable structure?

**Findings:**

- `frontend/src/features/quotes/ui/procurement-step/procurement-handsontable.tsx` has 12 data columns + 1 unassign button column. The plan's wording ("insert between quantity and unit") is wrong because `unit` is NOT one of the rendered columns. Actual order:
  `brand | product_code | supplier_sku | manufacturer_product_name | product_name | quantity (col 5) | purchase_price_original (col 6) | production_time_days | weight_in_kg | dimensions | is_unavailable | supplier_sku_note | [unassign]`
- User confirmed Decision 3: insert MOQ immediately after `quantity` and before `purchase_price_original` so the eye compares requested qty against MOQ before the price line.
- Column is editable (not locked — informational field only).
- No existing `min_order_quantity` or `moq` references in the codebase outside of the plan doc itself (greenfield DB column).
- The handsontable `handleAfterChange` hook at lines 208–275 parses numeric strings; MOQ needs to join the `purchase_price_original | weight_in_kg | production_time_days` numeric-parse branch at lines 245–251.

**Decision:** Insert MOQ as the 6th data column (index 5 in `COLUMN_KEYS`, shifting `purchase_price_original` and everything downstream by one). Header label "МИН. ЗАКАЗ". Numeric parsing on cell commit. Warning icon renderer via a custom Handsontable `renderer` function that fires when `row.min_order_quantity != null && row.quantity < row.min_order_quantity`.

**Implication for design:** Column-index-based code (lockedColIndices at lines 277–284, any hardcoded indices in tests) needs updating for the +1 shift. Need a code-intel pass over `procurement-handsontable.tsx` during implementation to catch all index dependencies.

**Sources:** Code-intel report section 3, `procurement-handsontable.tsx` structure outline.

### Topic 6: Currency system — backend/frontend drift

**Question:** How many places need to change when we expand SUPPORTED_CURRENCIES?

**Findings:**

**Backend (`services/currency_service.py`):**

- Line 20: `SUPPORTED_CURRENCIES = ['USD', 'EUR', 'RUB', 'CNY', 'TRY']` — single source of truth.
- Lines 23–28: `CBR_CURRENCY_CODES` dict (keyed by alpha-3).
- Lines 31–36: `CBR_CHAR_CODES` dict.
- Line 135: `required_currencies = ['USD', 'EUR', 'CNY', 'TRY']` — rate-fetch validation.
- Line 301: same literal again.

**Backend (other services that independently hardcode the same list):**

- `services/logistics_expense_service.py:34`
- `services/supplier_invoice_payment_service.py:67`
- `services/supplier_invoice_service.py:72`

These should all import from `currency_service.SUPPORTED_CURRENCIES` rather than redefine.

**Frontend hardcoded (already drifted — missing TRY):**

- `invoice-create-modal.tsx:25` → `["USD", "EUR", "CNY", "RUB"]`
- `additional-expenses.tsx:15` → `["USD", "EUR", "CNY", "RUB"]`
- `route-segments.tsx:9` → `["USD", "EUR", "CNY", "RUB"]`

**Database:**

- Migration 190 (`deal_logistics_expenses`) line 18: `CHECK (currency IN ('USD','EUR','RUB','CNY','TRY'))` — only hardcoded CHECK constraint on currency values in the entire migrations dir. All other tables use format-only regex checks.

**Brittle tests:**

- `tests/test_logistics_expense_service.py:366–368` asserts `len(SUPPORTED_CURRENCIES) == 5`. Will break on expansion.
- `tests/test_logistics_service.py:998` contains `['USD','EUR','RUB','CNY','GBP']` (GBP already present in a different test context — unrelated to our expansion, but worth a glance).

**CBR coverage of new currencies:**

- AED: published (char code `AED`, num `784`).
- KZT: published (`KZT`, `398`).
- JPY: published (`JPY`, `392`).
- GBP: published (`GBP`, `826`).
- CHF: published (`CHF`, `756`).

All five are in the CBR daily XML feed — no additional rate source needed.

**Decision:**

- Extend `SUPPORTED_CURRENCIES` to 10 entries.
- Extend `CBR_CURRENCY_CODES` and `CBR_CHAR_CODES` with the 5 new entries (CBR uses the same alpha-3 → num codes as ISO).
- Migration 265 drops the `deal_logistics_expenses_currency_check` constraint and replaces it with a format-only `currency ~ '^[A-Z]{3}$'` regex check (matching all other currency-bearing tables).
- Consolidate frontend currency lists into `frontend/src/shared/lib/currencies.ts` as a new shared module that mirrors `SUPPORTED_CURRENCIES`. The three drifted frontend arrays get replaced with an import.
- Brittle test `tests/test_logistics_expense_service.py:366` updated to `== 10`.

**Implication for design:** The "extra currencies" task becomes a minor consolidation pass in addition to the data change. The frontend gets a new `shared/lib/currencies.ts` module. All existing currency reads continue to work unchanged.

**Sources:** Code-intel report section 4, `currency_service.py` direct read, `migrations/190_create_deal_logistics_expenses.sql` read, CBR XML daily rates public documentation.

### Topic 7: Parallelization planning

**Question:** Which tasks can run in parallel and where are the file-conflict points?

**Findings:**

**T1 (Geo + Incoterms + HERE + endpoint)** creates new files and touches `services/here_service.py` (in-place edit). No downstream file conflicts.

**T2 (shipping country + delivery terms + delivery country on quote + Incoterms dropdown upgrades)** touches:

- `migrations/263_*.sql` (new)
- `frontend/src/features/quotes/ui/procurement-step/invoice-create-modal.tsx` (edit)
- `frontend/src/features/quotes/ui/procurement-step/invoice-card.tsx` (edit)
- `frontend/src/entities/quote/mutations.ts` (edit — dual-write)
- `frontend/src/entities/quote/__tests__/mutations.test.ts` (edit)
- `frontend/src/features/quotes/ui/create-quote-dialog.tsx` (edit — delivery country + Incoterms dropdown)
- `frontend/src/features/quotes/ui/calculation-step/calculation-form.tsx` (edit — Incoterms dropdown)

**T3 (MOQ)** touches:

- `migrations/264_*.sql` (new)
- `frontend/src/features/quotes/ui/procurement-step/procurement-handsontable.tsx` (edit)
- `frontend/src/entities/quote/types.ts` (edit — `QuoteItem.min_order_quantity`)

**T4 (currencies)** touches:

- `services/currency_service.py` (edit)
- `services/logistics_expense_service.py` (edit — import from currency_service)
- `services/supplier_invoice_payment_service.py` (edit)
- `services/supplier_invoice_service.py` (edit)
- `main.py` (minor — already imports SUPPORTED_CURRENCIES, no change needed if the list expands)
- `migrations/265_*.sql` (new)
- `frontend/src/shared/lib/currencies.ts` (new)
- Three frontend currency-array files (edit — import from new shared module) — **COLLISION WITH T2** on `invoice-create-modal.tsx`.
- `tests/test_logistics_expense_service.py` (edit — count assertion)
- `requirements.txt` (edit — add `pycountry` for T1's HERE fix) — **COLLISION WITH T1**.

**Collision resolution:**

- `invoice-create-modal.tsx` is touched by both T2 (new country+Incoterms fields) and T4 (currency list import). Resolution: T2 owns the file. T4's currency consolidation for this file happens as part of T2 rather than T4. T4 still owns the two other files (`additional-expenses.tsx`, `route-segments.tsx`) without collision.
- `requirements.txt` is touched by both T1 (add pycountry) and not really T4 (T4 doesn't add deps). Not a real collision.
- `main.py`: T1 adds a new route handler, T4 doesn't need to touch it (already imports from currency_service). No collision.

**Decision:** T2, T3, T4 can run parallel after T1 completes. Resolution notes above go into each task's description.

**Implication for design:** Task sequencing confirmed — T1 is a hard serial blocker, T2/T3/T4 parallel, T5 serial tail.

**Sources:** Code-intel report + cross-referenced with requirements.md file touches.

---

## Architecture Pattern Evaluation

**Options considered:**

1. **Separate kiro specs per task** — Would force 5 independent design/tasks/impl flows. Rejected: all 5 items share scope and the foundational T1 is consumed by T2/T3 — splitting into 5 specs duplicates context and hurts coherence.

2. **Monolithic feature module under `features/procurement-phase-3/`** — Would put all new code in one place. Rejected: violates FSD. `CountryCombobox` is a cross-feature primitive and belongs in `shared/ui/`. `INCOTERMS_2020` is a cross-feature constant and belongs in `shared/lib/`. Forcing them into `features/` would block reuse from other registries.

3. **Extension with layered new code (chosen)** — New modules added to `shared/ui/`, `shared/lib/`, `services/`, `migrations/`; existing files edited in place where integration is needed. Follows the project's strangler-fig migration pattern and respects FSD strictly.

**Chosen pattern:** Extension with layered additions. Shared primitives go in the shared layer; feature edits are surgical and preserve existing behavior.

## Design Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | `Intl.DisplayNames` + `Intl.supportedValuesOf` for country data | Zero dependency, zero maintenance, always current with ICU data, platform-standard |
| D2 | Add `pycountry` to Python deps for HERE alpha3→alpha2 fix | Exhaustive ISO coverage beats any hand-maintained dict; fallback to existing dict if import fails |
| D3 | `functools.lru_cache(maxsize=256)` on `search_cities` | Process-local LRU is correct — city typeahead repeats are frequent; stale data across process lifetime is not a concern |
| D4 | Dual-write `pickup_country` (text) and `pickup_country_code` (ISO-2) on invoices | Preserves 2026-04-10 customs fix; `pickup_country_code` canonicalizes for Phase 4 VAT detection without breaking logistics auto-assignment |
| D5 | `findCountryByName` helper in `shared/ui/geo` | Allows supplier-country auto-derivation to populate both fields without schema change to `suppliers` table |
| D6 | Shared `INCOTERMS_2020` constant in `shared/lib/incoterms.ts` | Single source of truth; both existing dropdowns and the new supplier dropdown use the same 11-entry list |
| D7 | MOQ is informational only — not a calculation input | Protected file list (`calculation_engine.py` et al.) stays untouched; MOQ is a UX warning, not a blocker |
| D8 | Migration 265 loosens constraint to regex-only | Aligns `deal_logistics_expenses` with all other currency-bearing tables; eliminates the last hardcoded currency CHECK |
| D9 | Consolidate frontend currency lists into `shared/lib/currencies.ts` | Reduces drift risk (already drifted: TRY missing from 3 files); imports from new module |
| D10 | `CountryCombobox` is a single-select controlled component | Matches existing DataTable `column-filter.tsx` pattern; reuses Base UI Popover primitive; keyboard navigation built in |
| D11 | Keyboard navigation on `CountryCombobox` search input (ArrowUp/Down/Enter/Escape) | Matches shadcn Combobox UX expectations; existing DataTable filter popovers don't have keyboard nav — Phase 3 raises the UX bar |

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | HERE API free-tier rate limit hit under typeahead load | Medium | Medium (degraded UX, not outage) | LRU cache (D3) reduces duplicate calls; graceful fallback already in place (returns `[]` on error) |
| R2 | Regression of 2026-04-10 customs/logistics fix | High if careless | High (breaks logistics auto-assignment) | R9.2 explicit non-regression AC; extend existing `mutations.test.ts` regression tests; dual-write preserves `pickup_country` field |
| R3 | Brittle test `tests/test_logistics_expense_service.py:366` | Certain to fire | Low (mechanical fix) | R9.8 explicitly calls this out; update the assertion in the same commit as the `SUPPORTED_CURRENCIES` expansion |
| R4 | Handsontable column index shift breaks unknown test | Low | Medium | Code-intel scan during T3 implementation for any hardcoded column indices; sub-task: verify `lockedColIndices` updated |
| R5 | `findCountryByName` returns undefined for suppliers with legacy/misspelled country names | Medium | Low (pickup_country_code stays null; pickup_country text still written) | Graceful degradation is the design; data cleanup for misnamed suppliers is future work |
| R6 | `pycountry` install bloats Docker image | Low | Low (~8MB) | Acceptable; documented in `requirements.txt` |
| R7 | Frontend tests are limited (only 2 files exist) | Certain | Medium (first-time test infra work) | T1 absorbs ~15m first-test setup time; patterns copied from existing `mutations.test.ts` |

## Parallelization Considerations

- **T1 is a hard serial blocker.** Nothing in T2/T3/T4 can start before T1's exports are stable.
- **T2, T3, T4 can run in parallel.** Resolved the one file collision (`invoice-create-modal.tsx` currency import) by making T2 own that file; T4 keeps the other two currency-array files.
- **T5 is a serial tail.** Cannot start until all four implementation tasks are merged locally.
- **Migrations 263, 264, 265** must apply in numeric order but can be authored in parallel across T2/T3/T4.
- **`database.types.ts` regeneration** is a single action after all three migrations are applied (not per migration). T5's browser-test phase should start from a freshly regenerated types file.
- **`requirements.txt`** is touched only by T1 (adds `pycountry`). No collision.
