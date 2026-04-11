# Requirements Document

## Introduction

Procurement Improvements Phase 3 for OneStack (Kvota quotation management system). This spec ships five related improvements that the procurement team submitted in the April 2026 feedback round. The foundational piece is a pair of shared Geo picker components (`CountryCombobox` + `CityCombobox`) in `frontend/src/shared/ui/geo/`, which unblocks downstream VAT auto-detection (planned for Phase 4) and replaces the current free-text country inputs across supplier invoices, quotes, and related forms.

The remaining four items are concrete data-model and UI changes: structured shipping country + delivery terms (Incoterms) per supplier invoice, a minimum-order-quantity (MOQ) column on quote items with a soft warning, and support for five additional currencies (AED, KZT, JPY, GBP, CHF) that the CBR already publishes rates for.

**Key principles:**

- **Shared, reusable components** — Geo pickers live in `shared/ui/`, obey Feature-Sliced Design layering, and are consumed by features without leaking into them.
- **Bilingual from day one** — every user-visible country label carries both Russian (primary) and English (secondary) text, sourced from the runtime's ICU data so there is no per-locale maintenance burden.
- **API-first** — the new cities search endpoint returns JSON and is callable by both the Next.js frontend and AI agents (per `api-first.md` steering).
- **Additive schema changes only** — no existing column is dropped or renamed; new columns coexist with legacy text fields so existing reads and today's customs/logistics fix continue to work untouched.
- **Calculation engine untouched** — MOQ is a display-layer warning, not a calculation input; the protected files (`calculation_engine.py`, `calculation_mapper.py`, `calculation_models.py`) are not modified.

**Out of scope (explicitly excluded):**

- VAT auto-detection based on shipping country (Phase 4).
- PEO (ПЭО) rates table (Phase 4).
- Migrating the legacy FastHTML `/api/cities/search` HTMX endpoint — it stays as-is for unmigrated pages.
- Swapping HERE for an alternative geocoder — only the two known HERE issues (hardcoded alpha3→alpha2 mapping, no caching) are fixed in Phase 3.
- Backfilling `invoices.pickup_country_code` from existing `pickup_country` text values — a future script.
- English UI translation beyond the bilingual country labels (Phase 4).
- Kanban procurement sub-statuses (Phase 4).
- Role-based column visibility enforcement for MOQ.

## Requirements

### Requirement 1: Shared CountryCombobox — Static Bilingual Country Picker

**Objective:** As a frontend developer building any form that captures a country, I want a single shared combobox component backed by zero-maintenance static data, so that every country input across OneStack looks and behaves identically and stays accurate as ICU data updates.

#### Acceptance Criteria

1. The CountryCombobox shall be importable from `@/shared/ui/geo` as a named export along with its props type.
2. When a consumer passes a `value` prop containing an ISO 3166-1 alpha-2 code, the CountryCombobox shall render a trigger button displaying the country's Russian name as the primary label.
3. When a consumer passes `value={null}`, the CountryCombobox shall render the trigger button with a configurable placeholder (default: `"Выберите страну…"`) in the muted foreground color.
4. When the user clicks the trigger, the CountryCombobox shall open a popover containing a search input and a scrollable list of all ISO 3166-1 alpha-2 countries.
5. When the user types in the search input, the CountryCombobox shall filter the list by case-insensitive substring match against the Russian name, the English name, and the ISO-2 code simultaneously.
6. When the user clicks a country in the list or presses Enter on a keyboard-focused row, the CountryCombobox shall invoke the `onChange` prop with the selected ISO-2 code and close the popover.
7. While the popover is open, the CountryCombobox shall support keyboard navigation — ArrowUp/ArrowDown move a virtual focus through the filtered list, Enter commits the focused option, and Escape closes the popover without changing the value.
8. Where the `clearable` prop is true and a value is selected, the CountryCombobox shall render a clear (X) affordance on the trigger that invokes `onChange(null)` without opening the popover.
9. The CountryCombobox shall render each list option as `{Russian name} · {English name}` followed by the uppercase ISO-2 code in a muted monospace tail, so users can identify countries by either locale.
10. The CountryCombobox shall source its country list from `Intl.supportedValuesOf("region")` filtered to two-uppercase-letter alpha-2 codes, using `Intl.DisplayNames` for both `"ru"` and `"en"` labels, and shall build this list once at module load (not per render).
11. If the runtime lacks `Intl.supportedValuesOf`, the CountryCombobox shall render an empty list with a "Страна не найдена" message rather than throwing.
12. The `@/shared/ui/geo` module shall export a `findCountryByName(name: string, locale?: "ru" | "en")` helper that resolves a human-readable country name (case-insensitive, whitespace-trimmed, accent-insensitive where feasible) to its matching ISO 3166-1 alpha-2 code, returning `undefined` when no match is found. This helper exists so that the `createInvoice` auto-derivation logic (which starts from `suppliers.country` as Russian text) can populate both `pickup_country` and `pickup_country_code` without requiring a schema change to the `suppliers` table.

### Requirement 2: Shared CityCombobox — HERE-Backed Typeahead City Picker

**Objective:** As a procurement user filling in a supplier invoice, I want to type the first letters of a city and see structured city+country matches, so that I can pick a canonical value in one action instead of typing free text and guessing the country separately.

#### Acceptance Criteria

1. The CityCombobox shall be importable from `@/shared/ui/geo` as a named export along with its props type.
2. When the user types in the CityCombobox search input, the CityCombobox shall wait 300ms after the last keystroke before issuing a network request (debounce).
3. When the user's typed query has fewer than 2 non-whitespace characters, the CityCombobox shall suppress network requests and show no results.
4. When the user's query has ≥ 2 characters and the debounce elapses, the CityCombobox shall fetch `GET /api/geo/cities/search?q={query}&limit=10` and render the returned cities in its popover.
5. Each rendered city option shall display the city name, the Russian country name, and the ISO-2 country code in a visually distinct layout.
6. When the user selects a city, the CityCombobox shall invoke the `onChange` prop with a structured object `{ city: string, country_code: string, country_name_ru: string, country_name_en: string, display: string }`.
7. When the backend returns an empty result set, the CityCombobox shall display an "Ничего не найдено" empty-state message rather than an error.
8. When the backend request fails (network error, 5xx response), the CityCombobox shall display a non-blocking "Поиск недоступен" message in the popover and not invoke `onChange`.
9. While a request is in flight, the CityCombobox shall render a loading indicator in the popover header.
10. The CityCombobox shall accept an `onCountryChange` optional callback and, when provided, shall invoke it with the selected city's ISO-2 country code so a sibling CountryCombobox can stay in sync.

### Requirement 3: Cities Search API Endpoint

**Objective:** As a frontend consumer or an AI agent, I want a single JSON endpoint to search cities by partial name, so that both the Next.js UI and any agent-driven workflow can look up structured city data through the same documented contract.

#### Acceptance Criteria

1. The backend shall expose a new endpoint `GET /api/geo/cities/search` that accepts query parameters `q` (string, required, minimum 2 non-whitespace characters) and `limit` (integer, optional, default 10, maximum 25).
2. When `q` is missing, empty, or shorter than 2 characters, the endpoint shall return HTTP 400 with a structured error body `{ "success": false, "error": { "code": "INVALID_QUERY", "message": "..." } }`.
3. When `limit` is outside the allowed range, the endpoint shall clamp it to the valid range (1–25) silently rather than returning an error.
4. When called with a valid query, the endpoint shall return HTTP 200 and a JSON body shaped as `{ "success": true, "data": [{ "city": "...", "country_code": "DE", "country_name_ru": "Германия", "country_name_en": "Germany", "display": "..." }, ...] }`.
5. When the HERE Geocode API returns zero results, the endpoint shall return HTTP 200 with `"data": []` — an empty list is not an error.
6. When the HERE Geocode API fails or times out, the endpoint shall return HTTP 200 with `"data": []` and log the error server-side (graceful degradation — the caller sees no cities, not a broken endpoint).
7. The endpoint shall require authentication (Supabase JWT via Bearer header or legacy session cookie) and return HTTP 401 when called unauthenticated.
8. The endpoint handler shall carry a structured docstring with `Path`, `Params`, `Returns`, `Side Effects`, and `Roles` sections per the `api-first.md` steering convention.
9. The existing legacy HTMX endpoint `GET /api/cities/search` (returning FastHTML `Option` elements) shall remain untouched and functional for unmigrated FastHTML pages.

### Requirement 4: HERE Service Resilience Fixes

**Objective:** As an operator, I want the HERE integration to avoid hitting the free-tier rate ceiling under typeahead load and to return correct ISO-2 country codes for all countries, so that the new CityCombobox is usable in production without causing 429s or misattributed VAT data downstream.

#### Acceptance Criteria

1. The `services/here_service.search_cities` function shall cache results for identical `(query, limit)` argument pairs for the duration of the process lifetime using an in-memory LRU cache with a capacity of at least 256 entries.
2. When the same `(query, limit)` pair is requested a second time before eviction, the cache shall return the prior result without calling the HERE API.
3. The `_normalize_item` helper shall resolve ISO 3166-1 alpha-3 country codes to alpha-2 codes using a complete mapping source (e.g., `pycountry`) rather than the current hardcoded 28-country dictionary.
4. Where `pycountry` is unavailable at runtime, the helper shall fall back to the hardcoded dictionary without crashing (backward compatibility).
5. Where a HERE response has no parseable country code at all, the helper shall return an empty string for `country_code` rather than raising.
6. The Python regression test suite shall include a test that asserts `_normalize_item` produces correct alpha-2 codes for at least five countries not in the current hardcoded dictionary (e.g., BR, EG, NG, PK, AR).
7. The Python regression test suite shall include a test that calling `search_cities` twice with the same arguments results in only one HERE API call (verified via mocking).

### Requirement 5: Shipping Country and Delivery Terms on Supplier Invoices

**Objective:** As a procurement user creating a КП поставщика (supplier invoice), I want to record the structured shipping origin country and the Incoterms agreed with the supplier directly on that invoice, so that downstream VAT detection, logistics routing, and quote documents all read the same canonical values.

#### Acceptance Criteria

1. A new database migration numbered 263 shall add the column `pickup_country_code CHAR(2)` to `kvota.invoices` as nullable, with a comment describing it as the ISO 3166-1 alpha-2 code of the pickup country.
2. The same migration 263 shall add the column `supplier_incoterms TEXT` to `kvota.invoices` as nullable, with a comment naming the Incoterms 2020 standard as the expected vocabulary.
3. The migration shall preserve the existing `pickup_country` text column without modification.
4. The migration shall include a CHECK constraint enforcing `pickup_country_code ~ '^[A-Z]{2}$'` when not null, so that only valid ISO alpha-2 codes are accepted at the database level.
5. After the migration is applied, the frontend TypeScript types generated from `database.types.ts` shall expose `pickup_country_code` and `supplier_incoterms` as `string | null` on `invoices` Row/Insert/Update.
6. The `invoice-create-modal.tsx` form shall render a CountryCombobox labeled "Страна отгрузки" that writes to both `pickup_country` (the legacy text column, for backward compatibility) and `pickup_country_code` (the new ISO column) simultaneously on submit.
7. When the user selects a country in the modal, the CountryCombobox shall set `pickup_country` to the country's Russian display name and `pickup_country_code` to its ISO-2 code.
8. The `invoice-create-modal.tsx` form shall render a dropdown labeled "Условия поставки" containing the full Incoterms 2020 list (EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF) plus a leading "— не указано —" option, and shall save the selected value to `invoices.supplier_incoterms` on submit.
9. The `createInvoice` mutation in `frontend/src/entities/quote/mutations.ts` shall continue to derive `pickup_country` from `suppliers.country` at creation time when the user did not pick a country explicitly in the modal — the Phase 3 work must not regress the 2026-04-10 customs/logistics fix.
10. When the user explicitly picks a country in the CountryCombobox, the explicit choice shall take precedence over the supplier-derived default for both `pickup_country` and `pickup_country_code`.
11. The `invoice-card.tsx` component shall display `pickup_country_code` (or the Russian country name resolved from it) and `supplier_incoterms` in the supplier invoice summary card when those fields are populated.

### Requirement 6: Minimum Order Quantity on Quote Items

**Objective:** As a procurement user entering supplier data for a quote, I want to record each item's minimum order quantity, so that the sales team sees an immediate visual warning when a customer's requested quantity is below what the supplier will actually ship.

#### Acceptance Criteria

1. A new database migration numbered 264 shall add the column `min_order_quantity NUMERIC` to `kvota.quote_items` as nullable, with a comment describing it as the supplier's minimum order quantity (informational only).
2. After the migration is applied, the frontend TypeScript types shall expose `min_order_quantity` as `number | null` on `quote_items` Row/Insert/Update.
3. The procurement handsontable (`procurement-handsontable.tsx`) shall render a new column labeled "МИН. ЗАКАЗ" positioned immediately after the existing "Кол-во" (quantity) column.
4. When the user enters a numeric value in the MOQ column, the handsontable shall save it to `quote_items.min_order_quantity` on cell commit.
5. When a row's `min_order_quantity` is not null and is greater than its `quantity`, the handsontable shall render a warning icon in the MOQ cell and show a tooltip "Количество ниже минимального заказа поставщика" on hover.
6. The procurement step header or totals area shall display a count badge showing the number of rows whose quantity is below their MOQ, formatted as "⚠ MOQ: {N}" when N > 0 and hidden otherwise.
7. The MOQ warning shall be purely informational — the save action, the approval action, and the calculation engine shall not block on MOQ violations.
8. The protected calculation engine files (`calculation_engine.py`, `calculation_mapper.py`, `calculation_models.py`) shall not be modified by this feature.
9. When a row has `min_order_quantity = null` or `min_order_quantity ≤ quantity`, the handsontable shall render the MOQ cell without the warning icon.

### Requirement 7: Extended Currency Support

**Objective:** As a procurement user working with suppliers in the Middle East, Central Asia, Japan, the UK, and Switzerland, I want to record and convert prices in AED, KZT, JPY, GBP, and CHF alongside the existing USD/EUR/RUB/CNY/TRY, so that I do not have to do manual FX conversions before entering supplier prices.

#### Acceptance Criteria

1. The `SUPPORTED_CURRENCIES` constant in `services/currency_service.py` shall be extended to include `AED`, `KZT`, `JPY`, `GBP`, and `CHF`, producing a list of ten entries total.
2. The `CBR_CURRENCY_CODES` and `CBR_CHAR_CODES` mappings in `services/currency_service.py` shall be extended with the CBR identifiers for all five new currencies.
3. The `convert_to_usd` function shall correctly convert amounts in AED, KZT, JPY, GBP, and CHF to USD using the CBR `→ RUB` rates as an intermediate, matching the existing pattern for EUR/CNY/TRY.
4. A new database migration numbered 265 shall alter the `deal_logistics_expenses_currency_check` constraint on `kvota.deal_logistics_expenses` to drop the hardcoded `IN ('USD','EUR','RUB','CNY','TRY')` list and replace it with a format-only regex check `currency ~ '^[A-Z]{3}$'`.
5. After migration 265 is applied, inserts into `kvota.deal_logistics_expenses` with currency values AED, KZT, JPY, GBP, or CHF shall succeed without constraint violation.
6. Every hardcoded frontend currency list (e.g., the `CURRENCIES` array in `invoice-create-modal.tsx`) shall be updated to include the five new currencies in the same display order as `SUPPORTED_CURRENCIES`.
7. The Python regression test suite shall include a test that converts 1000 AED to USD and asserts the result is a positive finite number within a plausible range (e.g., 100–500 USD).
8. The Python regression test suite shall include a test that verifies migration 265's constraint accepts AED, KZT, JPY, GBP, CHF and rejects an invalid code like `XX` or `usd` (lowercase).

### Requirement 8: Bilingual Labels Throughout the Geo Module

**Objective:** As a future user operating the OneStack UI in English, I want country labels to already carry English translations, so that when Phase 4 ships the English locale there is no per-country label work to do.

#### Acceptance Criteria

1. Every country returned by the `COUNTRIES` export from `@/shared/ui/geo` shall carry both `nameRu` and `nameEn` fields populated from `Intl.DisplayNames`.
2. The CountryCombobox search shall match against both `nameRu` and `nameEn` simultaneously in a single typed query.
3. The CountryCombobox dropdown shall display both labels side by side (Russian primary, English secondary, ISO-2 code tail).
4. Where the CountryCombobox is passed a `displayLocale` prop of `"en"`, the trigger button shall display `nameEn` as the primary label instead of `nameRu` (enabling future locale switching without a component rewrite).
5. The new `/api/geo/cities/search` endpoint shall return both `country_name_ru` and `country_name_en` fields in each city result.

### Requirement 9: Backward Compatibility and Non-Regression

**Objective:** As an operator of an already-running OneStack production instance, I want Phase 3 to add capability without changing the meaning of any existing field or breaking any existing code path, so that rollback is a simple schema revert and no data needs to be migrated.

#### Acceptance Criteria

1. The `invoices.pickup_country` text column shall retain its current meaning and all existing code that reads it shall continue to receive the same values after Phase 3 lands.
2. The `createInvoice` mutation in `frontend/src/entities/quote/mutations.ts` shall continue to derive and write `pickup_country` from `suppliers.country` when the user has not explicitly chosen one, preserving the behavior added on 2026-04-10 in commits `08a56ae` and `cc29010` for tickets FB-260410-110450-4b85 and FB-260410-123751-4b94.
3. The logistics auto-assignment logic (`assign_logistics_to_invoices`) shall continue to match rates by `pickup_country` (text) — Phase 3 shall not require the logistics service to read `pickup_country_code`.
4. The calculation engine files (`calculation_engine.py`, `calculation_mapper.py`, `calculation_models.py`) shall not be modified.
5. The legacy `/api/cities/search` HTMX endpoint shall remain untouched and continue to serve FastHTML pages as before.
6. Existing migration files (including migration 190) shall not be modified — migration 265 shall drop and recreate the constraint cleanly rather than edit the historical migration.
7. Existing rows in `kvota.invoices`, `kvota.quote_items`, and `kvota.deal_logistics_expenses` shall remain valid after all three Phase 3 migrations are applied (no backfill required, nullable columns only).
8. The full existing test suite shall pass after Phase 3 changes, with at most mechanical updates to literal count assertions that track the size of `SUPPORTED_CURRENCIES` (the only known coupling is `tests/test_logistics_expense_service.py` which asserts `len(SUPPORTED_CURRENCIES) == 5`). No existing test's semantic coverage shall be weakened or removed.

### Requirement 10: Incoterms 2020 Shared Constant

**Objective:** As a frontend developer, I want one canonical source of truth for the Incoterms 2020 list so that every dropdown that lets a user pick Incoterms shows the same complete set and is consistent as the standard evolves.

#### Acceptance Criteria

1. A new module `frontend/src/shared/lib/incoterms.ts` shall export a constant `INCOTERMS_2020` containing all eleven Incoterms 2020 codes in the conventional order (`EXW, FCA, CPT, CIP, DAP, DPU, DDP, FAS, FOB, CFR, CIF`), each with an optional short human-readable label.
2. The module shall export a typed helper `isValidIncoterm(code: string): boolean` that returns true for any entry in the constant and false otherwise.
3. The new supplier Incoterms dropdown on the invoice create modal (Requirement 5.8) shall consume `INCOTERMS_2020` rather than defining its own inline array.
4. The existing quote-level Incoterms dropdown in `frontend/src/features/quotes/ui/create-quote-dialog.tsx` (currently hardcoded to the 5-value subset `DDP/DAP/CIF/FOB/EXW`) shall be rewritten to consume `INCOTERMS_2020`, so that users creating a quote can select any of the 11 terms.
5. The existing calculation-form Incoterms dropdown in `frontend/src/features/quotes/ui/calculation-step/calculation-form.tsx` (same 5-value subset) shall also consume `INCOTERMS_2020`.
6. Values already stored in existing quotes (from the previous 5-value subset) shall remain valid — the expansion is strictly additive, no existing value becomes invalid.
7. The module shall have a vitest unit test asserting that `INCOTERMS_2020.length === 11` and that `isValidIncoterm("DDP")` returns true while `isValidIncoterm("XXX")` returns false.

### Requirement 11: Delivery Country on Quote Creation

**Objective:** As a sales user creating a new quote, I want to pick the delivery country from a structured picker instead of typing free text, so that downstream reports and VAT detection can work from canonical country codes consistent with the supplier invoice flow.

#### Acceptance Criteria

1. The new quote dialog (`frontend/src/features/quotes/ui/create-quote-dialog.tsx`) shall replace its existing plain-text `deliveryCountry` input with the shared `CountryCombobox` component from `@/shared/ui/geo`.
2. When the user picks a delivery country, the dialog shall store the selected ISO-2 code in local state and pass the country's Russian display name to the `createQuote` mutation in the existing `delivery_country` string field (no schema change required for this form — the column already accepts text).
3. Where the existing `quotes.delivery_country` column is text-typed, the `create-quote-dialog` shall write the Russian display name (matching historical values) so existing rows and reads remain consistent — there is no new column added to `kvota.quotes` in Phase 3.
4. The delivery city input shall remain as a plain text input for now — migrating city inputs to `CityCombobox` across the quote creation flow is out of Phase 3 scope and deferred to a future task.
5. When the user loads an existing quote into the dialog for edit (if that code path exists), the CountryCombobox shall seed its value by looking up the historical `delivery_country` text against `findCountryByName(...)` and displaying "Страна не найдена" in the trigger if no match is found, so users see immediate signal when legacy data does not round-trip cleanly.
