# Requirements Document — Procurement Bugs Fix (April 2026)

## Introduction

Batch fix for 5 bugs reported in the procurement flow that currently make core Phase 5b/5c functionality unusable. Root cause analysis surfaced a cross-cutting issue: **country-data normalization is absent**, so VAT lookup, buyer/supplier matching, and pickup-location logic all silently drift. This spec bundles the 5 surface bugs with the infrastructure fix (country + city normalization) they share.

**Bugs in scope:**

1. **Empty KP silent fail** — "Создать КП поставщику" does nothing when 0 positions are selected (no toast, no modal).
2. **VAT 20% hardcoded everywhere** — `fetchVatRate` returns 20% for nearly every country because the `vat_rates_by_country` table seed conflates "Russian import VAT" with "country domestic VAT" and lacks the buyer-match rule.
3. **Multi-KP creation silently fails** — creating a second KP for positions already in another KP in status "Ожидает цены" or "Отправлено к поставщику" fails without feedback. Phase 5b REQ-1 AC#1 explicitly guarantees this scenario must work.
4. **Unassigned-positions KP silently fails** — same symptom as #3 but for positions not in any prior KP. Likely same root cause.
5. **Split/Merge invisible for sent KP** — users report Split + Merge buttons missing on KP in "Отправлено к поставщику" status. Phase 5c Task 12/13 says these actions should be available until `procurement_completed_at` is set.

**Supporting infrastructure to build (cross-cutting):**

- Country field normalization (ISO alpha-2 code alongside free-text name) on `suppliers` and `buyer_companies`.
- Backfill migration for existing junk (e.g., "Германия"/"Germany"/"Turkey"/"Türkiye" → canonical `DE`/`TR`).
- City autocomplete (RU via DaData, international via HERE) — already partially exists, enforce.
- Error-propagation refactor: replace `catch {}` swallowers in procurement mutations + modal with structured logging + user-visible messages.

**Reference specs (prerequisite reading):**

- `.kiro/specs/phase-5b-quote-composition/requirements.md` — multi-supplier invoice semantics, `invoice_item_coverage`, `composition_selected_invoice_id`.
- `.kiro/specs/phase-5c-invoice-items/requirements.md` — split/merge, edit gate decoupled from `sent_at`.
- `migrations/269_create_vat_rates_by_country.sql` — current seed, to be updated.

**Business rule (user-confirmed 2026-04-24):**

VAT rate application = **country match between buyer company and supplier**.
- If `buyer_company.country === supplier.country` (normalized) → apply that country's domestic VAT.
- Else → 0% (export zero-rated).
- EAEU logic falls out naturally: KZ → RU is no-match → 0% (VAT via declaration, not customs).

---

## Requirements

### Requirement 1: Country Normalization on Suppliers and Buyer Companies

**Objective:** As a procurement user, I want country fields to be stored as canonical ISO codes, so that buyer↔supplier matching, VAT resolution, and pickup-location logic produce reliable results regardless of how a human typed the country name.

#### Acceptance Criteria

1. Migration `295_add_country_code_to_suppliers_and_buyers.sql` shall add `country_code CHAR(2) NULL` to `kvota.suppliers` and `kvota.buyer_companies`, with a CHECK constraint `country_code IS NULL OR country_code ~ '^[A-Z]{2}$'`.
2. The migration shall backfill `country_code` for every row whose free-text `country` value matches a known country via `findCountryByName(value, "ru")` OR `findCountryByName(value, "en")`. Unmatched rows (e.g., "Test", "ААААА", empty) shall get `country_code = NULL`.
3. The migration shall log unmatched country values to `stdout` during migration with the row id and original text, so a human can triage edge cases.
4. The Supplier Create/Edit form shall replace the free-text country input with `CountryCombobox` (already exists in `shared/ui/geo`). The form shall write both `country` (Russian display name from the picker) and `country_code` (ISO alpha-2) in a single transaction.
5. The Buyer Company Create/Edit form shall mirror Requirement 1.4 — use `CountryCombobox`, write both fields.
6. The VAT resolver (Requirement 3) shall read `country_code` only, never the free-text `country` column.
7. A regression query in test `test_country_code_backfill.py` shall assert: (a) every row with non-null `country_code` matches a valid country per the ICU catalog; (b) the set of unmatched rows after backfill is explicitly listed (to prevent silent drift).

---

### Requirement 2: City Normalization with Autocomplete

**Objective:** As a procurement user, I want city fields to be filled from an autocomplete widget (DaData for RU, HERE for international), so that pickup-location and address data is consistent across suppliers and buyer companies.

#### Acceptance Criteria

1. The Supplier and Buyer Company forms shall use an existing or new `CityAutocomplete` component that accepts `country_code` as input and filters city suggestions accordingly.
2. When `country_code === "RU"`, the autocomplete shall call DaData (existing integration — `DADATA_API_KEY` in env).
3. When `country_code !== "RU"`, the autocomplete shall call HERE Geocode API (existing integration — `HERE_API_KEY` in env). The call shall use the Geocode endpoint with `qq=country:<country_code>` filter (Autosuggest is invalid per prior MEMORY note).
4. The autocomplete shall accept input in both Russian and English and return canonical display names in the form's active locale (assume `ru` by default).
5. The invoice-create-modal `pickup_city` field shall use the same `CityAutocomplete`, filtered by the modal's `countryCode` state.
6. No migration of existing `city` values is required — city data is less structured than country, and stale free-text is acceptable. Forward-only enforcement.

---

### Requirement 3: VAT Rate Resolver with Buyer-Supplier Match Rule

**Objective:** As the invoice creation flow, I want VAT rate to be computed by comparing buyer and supplier country codes, so that domestic-trade VAT is applied exactly when both parties are registered in the same country, and export trade gets 0% (zero-rated).

#### Acceptance Criteria

1. The Python API shall expose `GET /api/geo/vat-rate?supplier_country_code=XX&buyer_company_id=UUID`, fully replacing the Phase 4a endpoint `GET /api/geo/vat-rate?country_code=XX`. All callers shall be updated atomically in this change — no deprecation period. Old endpoint is removed from `api/geo.py` + `api/routers/geo.py`, and every frontend call site migrated.
2. The new endpoint shall return `{ "success": true, "data": { "rate": number, "reason": "domestic" | "export_zero_rated" | "unknown" } }`.
3. When the resolver determines `buyer_country_code === supplier_country_code`, it shall return `rate = vat_rates_by_country[country_code].rate` and `reason = "domestic"`.
4. When the two codes differ, the resolver shall return `rate = 0` and `reason = "export_zero_rated"`.
5. When either code is NULL or unknown, the resolver shall return `rate = 0` and `reason = "unknown"` (fail-closed to zero, not 20%).
6. The resolver shall validate both inputs: invalid `supplier_country_code` (not matching `^[A-Z]{2}$`) returns HTTP 400. Unknown `buyer_company_id` returns HTTP 404.
7. The resolver shall require authentication (`_get_authenticated_user`) and be callable by any authenticated user (same roles as existing endpoint).
8. The frontend `fetchVatRate` helper (in `entities/invoice/queries.ts`) shall be renamed `fetchSupplierVatRate` and call the new endpoint. The invoice-create-modal shall replace its `useEffect` on `countryCode` with a `useEffect` that depends on `[buyerCompanyId, countryCode]` and fires only when both are set.
9. The modal's VAT input shall display `reason` as a subtle inline badge next to the rate: "Россия внутр." / "Экспорт (0%)" / "Неизвестно" (muted text).

---

### Requirement 4: VAT Rates by Country — Complete European Coverage

**Objective:** As a VAT administrator, I want the `vat_rates_by_country` table to contain correct domestic VAT rates for every country Kvota trades with or might trade with, so that Requirement 3's resolver returns meaningful values.

#### Acceptance Criteria

1. Migration `296_update_vat_rates_by_country.sql` shall replace the seed from Migration 269 with:
   - **EAEU**: RU=22, KZ=12, BY=20, AM=20, KG=12 (note: RU=22% current 2026 rate, user-confirmed. Under Rule B, applies only when buyer AND supplier are both RU)
   - **EU-27 + UK + EEA**: DE=19, FR=20, IT=22, ES=21, NL=21, BE=21, CZ=21, PL=23, AT=20, PT=23, GR=24, SE=25, DK=25, FI=24, IE=23, LU=17, RO=19, BG=20, HU=27, HR=25, SI=22, SK=23, LT=21, LV=21, EE=22, MT=18, CY=19, GB=20, NO=25, IS=24, CH=7.7, LI=7.7
   - **Asia**: CN=13, TR=20, JP=10, KR=10, IN=18, VN=10, TH=7, ID=11, MY=10, SG=9, PH=12, HK=0, TW=5
   - **Middle East / Africa**: AE=5, SA=15, IL=17, EG=14, ZA=15
   - **Americas**: US=0, CA=5, MX=16, BR=17, AR=21, CL=19
   - **Oceania**: AU=10, NZ=15
2. The migration shall be idempotent: an `ON CONFLICT (country_code) DO UPDATE SET rate = EXCLUDED.rate, notes = EXCLUDED.notes` clause handles re-application.
3. Each row shall have a `notes` field explaining the rate (e.g., "Германия — стандартная ставка 19%", "США — нет федерального НДС").
4. Comment on the `vat_rates_by_country` table shall be updated to read: `"Domestic VAT rates per country. Applied only when buyer and supplier countries match (see VAT resolver)."`.

---

### Requirement 5: No Silent Failures in Procurement Mutations

**Objective:** As a developer (and as a user reporting bugs), I want every failure in the procurement creation flow to surface with a specific, actionable message, so that silent `catch {}` blocks never hide a backend validation error or RLS rejection.

#### Acceptance Criteria

1. The file `invoice-create-modal.tsx` shall replace the bare `catch { toast.error("Не удалось создать КП поставщику"); }` at line ~196 with:
   ```ts
   catch (err) {
     console.error("[invoice-create-modal] submit failed:", err);
     toast.error(extractErrorMessage(err) ?? "Не удалось создать КП поставщику");
   }
   ```
2. A helper `extractErrorMessage(err: unknown): string | null` shall live in `shared/lib/errors.ts` and extract human-readable messages from (a) Supabase `PostgrestError` (reads `message` + `details` + `hint`), (b) Next.js Server Action errors, (c) Fetch responses with `{success: false, error: {message}}` shape, (d) native `Error` instances. Unknown shapes return `null`.
4. The mutations `createInvoice`, `assignItemsToInvoice`, `unassignItemFromInvoice`, `deleteInvoice` in `entities/quote/mutations.ts` shall re-throw Supabase errors with `details` preserved (currently they throw `itemsErr` as-is which is fine, but any wrapped `throw new Error(generic)` paths shall be removed).
5. No silent swallowers (`catch {}` or `catch (e) {}` with no body) shall remain in any `.tsx`/`.ts` file under `frontend/src/features/quotes/ui/procurement-step/`.
6. A lint rule or grep-based CI check shall enforce Requirement 5.5 going forward (e.g., `! grep -rn 'catch {\\|catch (\\w*) {\\s*}' ...`).

---

### Requirement 6: Multi-KP Creation Works for Overlapping Positions

**Objective:** As a procurement user, I want to create a second, third, or Nth supplier KP for positions that are already in another KP on the same quote, so that I can collect competing bids from multiple suppliers — per Phase 5b's multi-supplier composition design.

#### Acceptance Criteria

1. Given a quote with 10 positions and an existing KP (Invoice A) in status "Ожидает цены" covering positions 1-5, the procurement user shall be able to create a second KP (Invoice B) covering positions 1-5 (same positions) and have Invoice B appear in the UI with all 5 positions.
2. Given the same setup, the user shall be able to create a third KP (Invoice C) covering positions 6-10 (unassigned positions) regardless of Invoice A's status.
3. Given the same setup but Invoice A in status "Отправлено к поставщику" (sent_at is set), Requirements 6.1 and 6.2 shall still hold — sent status does not lock overlapping creation.
4. On successful multi-KP creation, the database state shall include:
   - A new row in `kvota.invoices` for Invoice B.
   - N rows in `kvota.invoice_items` for Invoice B (one per covered position).
   - N rows in `kvota.invoice_item_coverage` linking Invoice B's invoice_items to the shared quote_items (ratio=1 each).
   - `quote_items.composition_selected_invoice_id` updated to point to Invoice B (per Phase 5b REQ-1 AC#3 — most-recently-assigned wins).
5. If the backend rejects a multi-KP creation for a legitimate business reason (e.g., quote is locked), the error shall surface to the user via Requirement 5's error-extraction pipeline with the specific reason.
6. A Playwright regression test `procurement-multi-kp.spec.ts` shall reproduce Requirement 6.1 against a seeded quote and assert all 4 database-state bullets in 6.4.

---

### Requirement 7: Empty KP Creation Workflow

**Objective:** As a procurement user, I want to create an empty KP first and add positions to it later, so that I can set up the supplier+buyer+boxes infrastructure without needing to pre-select positions.

#### Acceptance Criteria

1. The "Создать КП поставщику" trigger (wherever it lives in the procurement page — handsontable toolbar or procurement-step.tsx) shall not be disabled based on `selectedItems.length`. The modal shall open regardless.
2. The modal shall accept submission with `selectedItems = []` — the `invoice_items` assignment step shall be skipped (code path already exists at line 176 of `invoice-create-modal.tsx`, guarded by `if (selectedItems.length > 0)`).
3. An empty KP shall appear on the quote page as an expanded `InvoiceCard` with the existing `isEmpty` branch active. The delete-KP button (trash icon) is already shown in this branch.
4. Per Requirement 7.3's `isEmpty` branch, an additional affordance shall be added: a prominent "Добавить позиции" button that opens a position-picker (candidate list = positions not yet in any KP OR already in another KP — both allowed per Requirement 6).
5. The position-picker shall call `assignItemsToInvoice(selectedIds, invoice.id)` and close. On success, the InvoiceCard shall re-render as non-empty.
6. Validation messages in the modal shall explicitly name missing fields when the user tries to submit incomplete data (currently already works via `errors` state — verify and extend to cover supplier/buyer/boxes error highlighting per validation UX rules).

---

### Requirement 8: Split/Merge Buttons Visible for "Sent" KP

**Objective:** As a procurement user, I want Split and Merge actions to remain available on a KP even after it has been sent to the supplier (status "Отправлено к поставщику"), as long as procurement for the overall quote has not been completed, per Phase 5c's edit-gate rule.

#### Acceptance Criteria

1. Given a KP with `sent_at IS NOT NULL` and `quote.procurement_completed_at IS NULL`, the Split button shall be visible when ≥1 quote_item on the KP is 1:1-covered.
2. Given the same state, the Merge button shall be visible when ≥2 quote_items on the KP are 1:1-covered.
3. Given `quote.procurement_completed_at IS NOT NULL`, both buttons shall be hidden (replaced by `ProcurementUnlockButton` per existing code).
4. A Playwright test shall reproduce Requirement 8.1 and 8.2 against a seeded KP with `sent_at` set.
5. If the test reveals the buttons already render correctly (our hypothesis), no UI change is required — the test becomes a regression guard and the bug is closed as "not reproducible, candidate count issue" with investigation notes.
6. If the test reveals buttons are hidden incorrectly, the outer ternary in `invoice-card.tsx` (around line 500) shall be audited and the guard corrected to use `!isLocked` exclusively (not `sent_at`).

---

### Requirement 9: Backward Compatibility & Migration Safety

**Objective:** As a system operator, I want all existing quotes, invoices, and VAT-dependent calculations to continue producing consistent results after these migrations run, so that no historical data is perturbed.

#### Acceptance Criteria

1. Migration 295 (country_code backfill) shall be idempotent — re-running is a no-op after successful first application.
2. Migration 296 (VAT rates update) shall use `INSERT ... ON CONFLICT DO UPDATE`, leaving manually-adjusted rates (where a human `updated_by` is non-null) alone unless the new rate is numerically different — log those for manual review instead.
3. The old `GET /api/geo/vat-rate?country_code=XX` endpoint shall be removed in the same change, with all frontend callers migrated atomically. No deprecation period (user decision 2026-04-24).
4. No calculation engine files (`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`) shall be modified — invariant from Phase 5b REQ-4.
5. A smoke regression shall compute calculations on 5 representative existing quotes before and after migration 295+296+feature code merge; monetary fields shall be bit-identical (the calculation engine reads from `quote_items.vat_rate`, which is seeded at item-assignment time and is not affected by these changes).

---

## Out of Scope

- Rewriting the calculation engine to consume country_code directly (future phase).
- Migrating `city` free-text to a normalized form (new entries only, per Requirement 2.6).
- Cross-organization VAT rules (all Kvota buyer_companies are single-organization for now).
- HS-code-based VAT reduction (food, books, children's goods at 10% vs 20%) — deferred; current scope treats VAT as country-uniform, which is acceptable per user decision 2026-04-24.

## Decision Log

- **2026-04-24 (user):** VAT rule is country-match, not HS-code-based. Non-match = 0%.
- **2026-04-24 (user):** Add all European countries to seed, plus existing 15 from migration 269.
- **2026-04-24 (user):** Backend-resolver, not frontend-resolver. Single source of truth for AI agents + UI.
- **2026-04-24 (user):** City autocomplete must work in English input too.
- **2026-04-24 (user):** Use /lean-tdd workflow; task ordering at implementor's discretion.
- **2026-04-24 (user):** RU VAT = 22% (current 2026 rate).
- **2026-04-24 (user):** No deprecation period — migrate VAT endpoint + all callers atomically.
- **2026-04-24 (user):** One PR vs split — indifferent; one PR chosen.
- **2026-04-24 (planner):** Fix catch handlers first (Step 0) because it unblocks browser-repro for bugs #3/#4/#1.
- **2026-04-24 (planner):** Ship all 5 bugs + normalization in one PR — they share the modal + mutation surface and splitting would require ugly feature flags.
