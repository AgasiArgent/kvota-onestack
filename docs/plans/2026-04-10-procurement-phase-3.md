# Procurement Improvements — Phase 3

**Status:** Draft (awaiting approval)
**Date:** 2026-04-10
**Depends on:** Phase 1 (quick wins) ✅, Phase 2 (quotes filters) ✅
**Blocks:** Phase 4 (VAT auto-detection needs country codes)

## Goal

Ship the five procurement team asks grouped under "Phase 3" in the April 2026
feedback round, with the Country/City picker as the foundational shared
component so downstream work in Phase 4 can assume structured country data.

## Scope & Build Order

### 1. Shared Geo picker components (BLOCKER, foundational)

Build a reusable `@/shared/ui/geo` module with two components, both ISO-3166
code-aware. Everything else in Phase 3 and Phase 4 consumes them.

- **`CountryCombobox`** — searchable dropdown backed by a static
  ISO-3166 country list (~250 entries, shipped as JSON in the frontend
  bundle). Emits `{ code: "DE", name: "Германия" }`. No network calls.
- **`CityCombobox`** — typeahead input backed by a new JSON endpoint
  `GET /api/geo/cities/search?q=...&limit=10`. Debounced 300ms, emits
  `{ city, country_code, country_name, display }`. Falls back gracefully
  when HERE is unreachable or returns no results.

**Backend:**
- New endpoint `GET /api/geo/cities/search` in `main.py` that returns JSON
  (not FastHTML Option elements). Wraps `services/here_service.search_cities()`.
- Follow `api-first.md` — endpoint is called by the Next.js frontend AND
  usable by AI agents. Docstring with Path/Params/Returns/Roles.
- Keep legacy `/api/cities/search` (HTMX) untouched — still used by unmigrated
  FastHTML pages.

**Frontend:**
- `frontend/src/shared/ui/geo/countries.json` — static list (Russian labels
  for display, ISO-2 codes as values). Source: ISO 3166-1 alpha-2.
- `frontend/src/shared/ui/geo/country-combobox.tsx`
- `frontend/src/shared/ui/geo/city-combobox.tsx`
- `frontend/src/shared/ui/geo/index.ts` (barrel)
- Both components use the existing Base UI `Popover` wrapper
  (`components/ui/popover.tsx`) + the `Input` primitive so UI stays consistent
  with DataTable filters.

**Acceptance:**
- Plug `CountryCombobox` into the new-quote dialog's "Страна доставки" field
  and verify it saves the ISO code.
- Plug `CityCombobox` into the supplier invoice edit form and verify
  `pickup_city` + `pickup_country` save together.

---

### 2. Shipping country on quotes

Add a dedicated "страна отгрузки" field separate from delivery city — this is
the **origin** of the shipment, which VAT detection in Phase 4 will read.

- **Migration 263:** `ALTER TABLE kvota.quotes ADD COLUMN shipping_country_code CHAR(2);`
  (nullable; backfill in a later pass once users start populating it).
- **Frontend:** add `CountryCombobox` to the new-quote dialog and quote-edit
  form, below the existing "город доставки" block.
- **Types:** extend `QuoteDetail` in `frontend/src/entities/quote/types.ts`.

**Open question:** Does shipping country belong on the **quote** (one per
quote) or on the **supplier invoice / quote_item** (one per sourcing line)?
The memory note says "shipping country" in the singular — suggesting per-quote
— but in practice a single quote can source from multiple countries. **I'll
default to per-supplier-invoice (`supplier_invoices.pickup_country_code`, which
already exists as text) and add a per-quote rollup for display.**

---

### 3. Delivery terms on КП

**Needs clarification from user.** "Delivery terms" (условия поставки) is
ambiguous between:
- **Incoterms** (EXW/FCA/FOB/CIF/DAP/DDP) — already exists as
  `quotes.offer_incoterms` (free-text). Could be converted to a dropdown.
- **Delivery lead time** (срок поставки в днях) — already exists per item
  as `quote_items.production_time_days`.
- **Something new** — e.g., a "условия поставки" section on the printed КП
  PDF that the procurement team wants more visible.

**Default assumption pending confirmation:** Convert `offer_incoterms` to a
dropdown with the standard Incoterms 2020 list, render it prominently on the
quote overview, and include it in the КП PDF. No schema change needed.

---

### 4. MOQ field on quote items

Procurement needs a "минимальный заказ" column on quote items so sales sees
supplier MOQ before promising a quantity.

- **Migration 264:** `ALTER TABLE kvota.quote_items ADD COLUMN min_order_quantity NUMERIC;`
- **Procurement handsontable:** add `min_order_quantity` column between
  `quantity` and `unit`.
- **Validation:** when `quantity < min_order_quantity`, show a soft warning
  (not a hard block) on the item row and on the totals summary.
- **Calculation engine:** does NOT read this field. It's informational only.
  `calculation_mapper.py` stays untouched (protected file).

---

### 5. Extra currencies

Procurement team asked for more purchase currencies.

- **Current supported:** `['USD', 'EUR', 'RUB', 'CNY', 'TRY']`
  (see `services/currency_service.py:20`)
- **Needs clarification from user:** which currencies to add? Likely
  candidates based on OneStack's supplier geography: **AED** (UAE), **KZT**
  (Kazakhstan), **KRW** (South Korea), **INR** (India), **JPY** (Japan),
  **GBP** (UK), **CHF** (Switzerland).
- **CBR coverage:** CBR publishes rates for AED, KZT, JPY, GBP, CHF. KRW/INR
  need a secondary source (likely fallback to cross-rate via USD).
- **Default proposal pending confirmation:** Add `AED, KZT, JPY, GBP, CHF`
  (all CBR-supported). Defer KRW/INR until a supplier actually asks for them.

**Backend:**
- Update `SUPPORTED_CURRENCIES` list in `currency_service.py`.
- Update `CBR_CURRENCY_CODES` + `CBR_CHAR_CODES` with the new entries.
- Verify `currency_service.convert_to_usd()` handles them correctly
  (it should, since it goes via RUB).
- Write a regression test that converts 1000 AED → USD and sanity-checks the
  range.

**Frontend:**
- Currency dropdowns already read from a hardcoded list — update the
  frontend list to match backend.

---

## Decisions Needed from User

| # | Decision | Default if no answer |
|---|----------|---------------------|
| 1 | Shipping country: per-quote or per-supplier-invoice? | Per-supplier-invoice + quote rollup |
| 2 | "Delivery terms" = Incoterms dropdown? | Yes, convert `offer_incoterms` to dropdown |
| 3 | Extra currencies list | Add AED, KZT, JPY, GBP, CHF |
| 4 | Phase 3 test strategy | Unit tests on geo components + currency regressions; browser smoke test on prod after deploy |

## Non-Goals

- VAT auto-detection (Phase 4) — Phase 3 only provides the country data.
- PEO (ПЭО) rates table — Phase 4.
- Migrating FastHTML city inputs to the new React component — the legacy
  `/api/cities/search` HTMX endpoint stays for them.
- Kanban procurement sub-statuses (Phase 4).

## Rollout

1. Land Geo components + backend endpoint behind no feature flag (they're
   additive).
2. Land shipping country + MOQ + currencies in separate PRs so each can be
   rolled back independently.
3. Browser-test on localhost with prod Supabase before each deploy
   (per `reference_localhost_browser_test.md`).
4. Verify on prod `https://app.kvotaflow.ru/quotes/new` after deploy.

## Open Risks

- **HERE API rate limits** — the existing integration doesn't cache. If
  procurement users hammer the city search (many typeahead requests), we may
  hit the free tier ceiling. Mitigation: add an in-memory LRU cache
  (`functools.lru_cache`) on `search_cities` keyed by `(query, limit)`.
- **ISO country list localization** — if we ship Russian labels, we lock
  into RU locale. Acceptable for now; add English labels in Phase 4 when
  "English translation" lands.
- **CBR missing rates on weekends/holidays** — already handled by
  `currency_service` fallback. New currencies inherit the same behavior.
