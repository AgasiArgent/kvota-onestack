# Requirements Document

## Introduction

Phase 5b extends OneStack's quoting system with a multi-supplier composition engine. Procurement can now collect competing supplier invoices (КП поставщика) against the same quote, each holding its own prices for overlapping line items. Sales composes the final customer quote by picking, per item, which supplier invoice's price to use. The selected combination is fed into the existing calculation engine via an adapter layer — the engine itself (`calculation_engine.py`, `calculation_models.py`, `calculation_mapper.py`) is locked and never modified.

**Scope reference:** `docs/plans/2026-04-10-phase-5b-quote-composition-engine.md` (user-approved 2026-04-10)
**Research context:** `.planning/research/SUMMARY.md`

**Key terminology used in requirements below:**
- **Quote Item** — a row in `kvota.quote_items`
- **Supplier Invoice** — a row in `kvota.invoices` (procurement workflow grouping; NOT `supplier_invoices` which is a finance table)
- **Composition** — the per-item selection of which supplier invoice's price to use in the final customer quote
- **Junction** — `kvota.invoice_item_prices`, the new table holding per-item prices from each supplier invoice
- **Composition Service** — new Python module `services/composition_service.py`, the adapter between junction data and `build_calculation_inputs()`

---

## Requirements

### Requirement 1: Multi-Supplier Invoice Collection

**Objective:** As a procurement user, I want to create multiple supplier invoices covering overlapping quote items, so that competing supplier offers can be collected for the same line items.

#### Acceptance Criteria

1. The Procurement API shall allow creating a new `invoices` row that references quote items already referenced by another invoice on the same quote.
2. When a new supplier invoice is created, the Invoice Creation Flow shall insert a row into `invoice_item_prices` for every quote_item the new invoice covers, capturing `purchase_price_original`, `purchase_currency`, `base_price_vat`, and `price_includes_vat` from the supplier offer.
3. The Invoice Creation Flow shall leave `quote_items.invoice_id` pointing to the most-recently-assigned invoice, preserving the legacy 1:1 pointer for backward compatibility (Decision #1).
4. Each `invoice_item_prices` row shall persist `created_by = current_user_id` and `created_at = now()`.
5. When two invoices on the same quote reference the same quote_item, the Composition Service shall treat them both as available alternatives — neither overrides the other silently.

---

### Requirement 2: Per-Item Supplier Selection

**Objective:** As a sales user, I want to pick per-item which supplier invoice's price to use in the final quote, so that I can compose the best multi-supplier combination for the client.

#### Acceptance Criteria

1. When the sales user opens the calculation step for a quote, the Composition API (`GET /api/quotes/{id}/composition`) shall return all quote_items with their available supplier offers, joined from `invoice_item_prices`.
2. The Composition API GET response shall include, for each quote_item: the currently-selected invoice_id (from `quote_items.composition_selected_invoice_id`), the list of available invoice alternatives with their prices and currencies, and the supplier name and country for each alternative.
3. The CompositionPicker component shall render a table with one row per quote_item, showing all available supplier invoices as selectable radio options.
4. The CompositionPicker shall display the currently-selected invoice per item; when `composition_selected_invoice_id IS NULL`, it shall fall back to displaying `quote_items.invoice_id` as selected (legacy path — Decision #1).
5. When the sales user picks a different supplier for an item, the CompositionPicker shall call `POST /api/quotes/{id}/composition` with the mapping `{ quote_item_id: invoice_id, ... }`.
6. The Composition API POST shall validate that every selected `invoice_id` has a matching row in `invoice_item_prices` for the specified `quote_item_id`; if validation fails, it shall return HTTP 400 listing which items have invalid selections and shall NOT persist any partial composition state.
7. When validation passes, the Composition API POST shall update `quote_items.composition_selected_invoice_id` for all affected items in a single transaction.
8. The CompositionPicker shall render as a new card within the CalculationStep component, positioned between `CalculationForm` and `CalculationResults`, above the Calculate button (Decision #2).

---

### Requirement 3: Calculation Engine Adapter

**Objective:** As the quote calculation pipeline, I want to receive item data already resolved against the active composition, so that the locked calculation engine sees "one chosen price per item" exactly as it does today.

#### Acceptance Criteria

1. The Composition Service module shall expose `get_composed_items(quote_id: str, supabase_client) -> List[Dict]` returning item dictionaries in the exact shape the current `quote_items` SELECT at `main.py:13303-13306` returns.
2. For each quote_item where `composition_selected_invoice_id IS NOT NULL`, the Composition Service shall overlay `purchase_price_original`, `purchase_currency`, `base_price_vat`, and `price_includes_vat` from the corresponding `invoice_item_prices` row.
3. For each quote_item where `composition_selected_invoice_id IS NULL`, the Composition Service shall fall back to the row's existing `quote_items` values (legacy path — Decision #1).
4. The Composition Service shall preserve all non-price fields from `quote_items` unchanged, including `customs_code`, `weight_in_kg`, `quantity`, `supplier_country`, `is_unavailable`, `import_banned`, and license cost fields.
5. The Calculation Pipeline shall call `composition_service.get_composed_items(...)` at all three calculation entry points (currently `main.py:13303`, `main.py:14188`, and a third site to be verified at `main.py:14846`) instead of reading `quote_items` directly.
6. The Composition Service shall execute the join with a single SQL query; the calculation path shall not issue N+1 reads.
7. The Composition Service shall never read from or import `calculation_engine.py`, `calculation_models.py`, or `calculation_mapper.py`.

---

### Requirement 4: Calculation Engine Immutability

**Objective:** As a system safeguard, I want the calculation engine files to remain untouched throughout Phase 5b, so that the calculation contract is demonstrably stable.

#### Acceptance Criteria

1. The Phase 5b merge commit range shall show zero modifications to `calculation_engine.py`.
2. The Phase 5b merge commit range shall show zero modifications to `calculation_models.py`.
3. The Phase 5b merge commit range shall show zero modifications to `calculation_mapper.py`.
4. A regression test shall compute calculations on at least 5 representative existing quotes using data captured before Phase 5b migrations ran, and shall assert the post-migration outputs are bit-identical for every monetary field and item-level result.

---

### Requirement 5: Invoice Verification State

**Objective:** As a procurement user, I want to explicitly mark a supplier invoice as "verified" (ready for composition), so that subsequent direct edits are gated behind an approval.

#### Acceptance Criteria

1. Migration 264 shall add `verified_at TIMESTAMPTZ NULL` and `verified_by UUID NULL REFERENCES auth.users(id)` to the `kvota.invoices` table.
2. The Procurement API shall expose `POST /api/invoices/{id}/verify` to stamp `verified_at = now()` and `verified_by = current_user_id`.
3. Only users with roles `procurement`, `procurement_senior`, `head_of_procurement`, or `admin` shall be able to call the verify endpoint.
4. While an invoice has `verified_at IS NOT NULL`, direct updates to price-carrying fields via the existing invoice update endpoint (at `main.py:19100`) shall be rejected with HTTP 409 unless the request carries an approved `approval_id`.
5. Migration 265 shall mark all existing `invoices` with `status = 'completed'` as verified by setting `verified_at = updated_at` and `verified_by = (a designated system user id or NULL — implementation decides)`.

---

### Requirement 6: Edit Verified Invoice Approval Flow

**Objective:** As a procurement user, I want to request head_of_procurement approval to edit a verified invoice, so that the organization has an audit trail for late-stage supplier price changes.

#### Acceptance Criteria

1. The Procurement API shall expose `POST /api/invoices/{id}/edit-request`, which creates a row in `kvota.approvals` via the existing `approval_service.request_approval()` function, targeting the `head_of_procurement` role.
2. The edit-request payload shall include the proposed changes as a JSON diff so reviewers see exactly what will change before approving.
3. The Procurement API shall expose `POST /api/invoices/{id}/edit-approval/{approval_id}/approve` and `POST /api/invoices/{id}/edit-approval/{approval_id}/reject`, callable only by users with the `head_of_procurement` role.
4. When an approval is approved, the Procurement API shall apply the proposed changes atomically by reading the JSON diff from the approvals row and applying it to the invoice and the relevant `invoice_item_prices` rows in a single transaction.
5. When an approval is rejected, the Procurement API shall mark the approval row as rejected and shall not modify the invoice.
6. The Next.js edit flow shall display a "Requires approval" modal when the user attempts to edit a verified invoice, collecting a reason and triggering the edit-request.
7. Edit-request, approval, and rejection events shall each produce an entry in the existing `kvota.approvals` audit trail, reusing the approval_service infrastructure (Decision #5).

---

### Requirement 7: Invoice Creation Bypass Logic

**Objective:** As a procurement user, I want the invoice creation form to skip re-asking for fields I've already provided for the same supplier on this quote, so that adding a second invoice from the same supplier is fast.

#### Acceptance Criteria

1. When a procurement user creates an invoice and the chosen `supplier_id` already has another invoice on the same `quote_id`, the Invoice Creation API shall NOT pre-fill `pickup_country`, `pickup_location_id`, `total_weight_kg`, `total_volume_m3`, or customs-related fields (Decision #6, same-supplier bypass).
2. When a procurement user creates an invoice and the chosen `supplier_id` is new to this quote, the Invoice Creation API shall pre-fill `pickup_country` from `suppliers.country` (existing Phase 5a behavior) and shall NOT pre-fill customs-related fields (Decision #6, new-supplier bypass).
3. The Invoice Creation API response shall include a `bypass_reason` field with value `"same_supplier"`, `"new_supplier"`, or `null`, indicating which bypass rule was applied.
4. The Next.js invoice creation form shall display a visual indicator when pre-fill is skipped due to same-supplier bypass, explaining the reason in Russian (e.g., "Уже есть КП от этого поставщика — поля не предзаполнены").
5. The bypass logic shall not affect validation — `pickup_country` remains required for all invoice creations (Phase 5a invariant).

---

### Requirement 8: KP Version Freeze on Send

**Objective:** As a procurement user, I want the current composition to be frozen (immutable) at the moment a KP is sent, so that sent KP data cannot be retroactively altered without creating a new version.

#### Acceptance Criteria

1. The Composition Service shall expose `freeze_composition(quote_id: str, user_id: str, supabase_client) -> int` returning the count of rows frozen.
2. When `freeze_composition` is called, it shall stamp `frozen_at = now()` and `frozen_by = user_id` on every `invoice_item_prices` row that is currently selected via `quote_items.composition_selected_invoice_id` for the given quote.
3. Frozen `invoice_item_prices` rows shall be immutable — UPDATE attempts to `purchase_price_original`, `purchase_currency`, `base_price_vat`, or `price_includes_vat` shall be rejected by a row-level check constraint or service-layer guard.
4. To edit a frozen row, the caller shall insert a new `invoice_item_prices` row with `(invoice_id, quote_item_id, version = previous_version + 1)` and `frozen_at = NULL`; the frozen row remains in the table as history.
5. The freeze hook shall be invoked from the existing KP-send flow if such a flow exists in the codebase at implementation time; if no send flow is implemented yet, the Phase 5b scope shall include a manual "Freeze composition" admin action accessible from the quote detail page for users with `head_of_procurement` or `admin` role (scope adjustment decided when this task starts, based on actual codebase state).

---

### Requirement 9: Backward Compatibility

**Objective:** As a system operator, I want all quotes that existed before Phase 5b's migrations to calculate identically after the migrations run, so that no historical data is perturbed by the schema change.

#### Acceptance Criteria

1. Migration 265 (backfill) shall be idempotent — running it twice shall have no side effects beyond the first run.
2. Migration 265 shall insert one `invoice_item_prices` row per existing `(quote_item_id, invoice_id)` pair where `quote_items.invoice_id IS NOT NULL`, copying `purchase_price_original`, `purchase_currency`, `base_price_vat`, and `price_includes_vat` from `quote_items`.
3. Migration 265 shall set `quote_items.composition_selected_invoice_id = quote_items.invoice_id` for every existing item with a non-null `invoice_id`.
4. After backfill completes, the regression test from Requirement 4 AC#4 shall pass — 5 representative existing quotes calculate bit-identically.
5. If the Composition Service encounters a quote_item with `composition_selected_invoice_id IS NULL` AND no matching `invoice_item_prices` row, it shall fall back to `quote_items` legacy values without raising an error.

---

### Requirement 10: Access Control & RLS

**Objective:** As a security safeguard, I want the composition feature to inherit the existing invoice and quote visibility rules, so that users never see composition data for quotes outside their access tier.

#### Acceptance Criteria

1. The `kvota.invoice_item_prices` table shall have Row Level Security enabled with SELECT policies mirroring `kvota.invoices` visibility rules per `.kiro/steering/access-control.md`.
2. The `kvota.invoice_item_prices` table shall have INSERT/UPDATE/DELETE policies restricted to roles `procurement`, `procurement_senior`, `head_of_procurement`, and `admin`.
3. The Composition API (GET and POST) shall apply the same quote-visibility filter as existing quote APIs — a user who cannot see a quote shall not see or modify its composition.
4. The Composition API shall return HTTP 404 (not 403) when a user attempts to access composition data for a quote they cannot see, per the `access-control.md` "404 on denial" rule.
5. Every query inside the Composition Service shall filter by `organization_id` as the outer boundary before applying any other filter.
6. The CompositionPicker component shall be rendered only for user tiers that include quote visibility AND edit-composition permission — at minimum `sales` (own quotes), `head_of_sales` (group quotes), `head_of_procurement` (all quotes), and `admin`.

---

## Coverage note

Cross-reference to the 6 locked design decisions from the scope doc:

| Decision | Requirements that encode it |
|---|---|
| #1 Legacy pointer + junction supplement | R1 AC3, R2 AC4, R3 AC3, R9 AC5 |
| #2 Composition picker inside calculation step, above Calculate | R2 AC8 |
| #3 Logistics per-invoice, customs per-item | R1 AC1-2 (invoice-level), R3 AC4 (customs_code on quote_items unchanged) |
| #4 KP versions frozen on send | R8 (all ACs) |
| #5 Edit verified requires head_of_procurement approval | R5, R6 |
| #6 Bypass logic for same/new supplier | R7 (all ACs) |

All 6 decisions are covered. The open decision from Phase 2 (migration 264 contents) is resolved and encoded in R5 AC1 (`verified_at` + `verified_by`) and R2 AC4/R3 AC3 (`composition_selected_invoice_id`).
