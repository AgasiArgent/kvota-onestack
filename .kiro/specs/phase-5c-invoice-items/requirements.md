# Requirements Document — Phase 5c: Invoice Items

## Introduction

Phase 5c completes the multi-supplier composition architecture started in Phase 5b. It replaces the `kvota.invoice_item_prices` junction with a dedicated `kvota.invoice_items` table (per-invoice positions with their own name/sku/qty/price/weight/customs_code/supplier_country) and a new `kvota.invoice_item_coverage` M:N junction to `quote_items` with a `ratio` column. This enables local-to-invoice split/merge — one supplier can give "bolt + washer" for a "fastener assembly" quote_item (split), another can give "fastener assembly" as-is (no split), without mutating the customer's original quote_items.

Phase 5c also moves the invoice edit-gate from `invoices.sent_at` to `quotes.procurement_completed_at`. In OneStack, `sent_at` means "request for pricing sent to supplier" — the middle of the procurement workflow. Blocking edits at that moment contradicts the natural flow (send → wait for reply → edit with prices). The correct gate is when the procurement stage ends and the quote transitions to logistics/customs.

**Scope reference:** `project_phase_5c_invoice_items.md` memory (planned 2026-04-18), builds on `.kiro/specs/phase-5b-quote-composition/` (shipped 2026-04-11).
**Migration approach:** One-shot (not expand-contract). Rationale: calc engine is locked; regressions surface immediately in testing.

## Terminology

- **Quote Item** — a row in `kvota.quote_items`; represents the customer's request as originally submitted. Preserved as source-of-truth; never mutated by procurement.
- **Invoice Item** — a row in the new `kvota.invoice_items`; represents a single position within one supplier КП. May have a different name/SKU than the quote_item it covers (split/merge/substitution).
- **Coverage** — a row in the new `kvota.invoice_item_coverage`; links an invoice_item to the quote_item(s) it fulfills, with a `ratio` coefficient.
- **Ratio** — `invoice_item_units per quote_item_unit`. Example: 2 washers per 1 fastener → ratio = 2. Invariant: `invoice_item.quantity = quote_item.quantity × ratio` for each coverage row.
- **Composition Pointer** — `quote_items.composition_selected_invoice_id`; unchanged from Phase 5b. Points to the invoice whose prices are used for this quote_item in the final calc.
- **Procurement Lock** — new semantic gate on `quotes.procurement_completed_at IS NOT NULL`. Replaces the Phase 4a `sent_at`-based gate.

---

## Requirements

### Requirement 1: Invoice Items Table

**Objective:** As the procurement workflow, I want per-invoice positions with their own attributes, so that one supplier can propose a decomposition that differs from the customer's original request without mutating that request.

#### Acceptance Criteria

1. Migration 281 shall create `kvota.invoice_items` with columns: `id`, `invoice_id` (FK → invoices, ON DELETE CASCADE), `organization_id` (FK → organizations), `position INT`, `product_name TEXT NOT NULL`, `supplier_sku TEXT`, `brand TEXT`, `quantity NUMERIC CHECK > 0`, `purchase_price_original NUMERIC(18,4)`, `purchase_currency TEXT NOT NULL`, `base_price_vat NUMERIC(18,4)`, `price_includes_vat BOOLEAN DEFAULT false`, `vat_rate NUMERIC(5,2)`, `weight_in_kg NUMERIC`, `customs_code TEXT`, `supplier_country TEXT`, `production_time_days INTEGER`, `minimum_order_quantity INTEGER`, `dimension_height_mm INT`, `dimension_width_mm INT`, `dimension_length_mm INT`, `license_ds_cost NUMERIC`, `license_ss_cost NUMERIC`, `license_sgr_cost NUMERIC`, `supplier_notes TEXT`, versioning (`version INT CHECK >= 1`, `frozen_at TIMESTAMPTZ`, `frozen_by UUID`), audit (`created_at`, `updated_at`, `created_by UUID`).
2. Migration 281 shall add UNIQUE constraint `(invoice_id, position, version)` and indexes `idx_invoice_items_invoice (invoice_id)`, `idx_invoice_items_organization (organization_id)`, `idx_invoice_items_active (invoice_id, position) WHERE frozen_at IS NULL`.
3. Migration 281 shall enable RLS with SELECT policy for 10 roles (admin, top_manager, procurement, procurement_senior, head_of_procurement, sales, head_of_sales, finance, quote_controller, spec_controller), WRITE policy for 4 roles (admin, procurement, procurement_senior, head_of_procurement), DELETE policy for 2 roles (admin, head_of_procurement). Pattern mirrors `invoice_item_prices` from migration 263.

### Requirement 2: Invoice Item Coverage Junction

**Objective:** As the composition layer, I want M:N linkage between invoice_items and quote_items with a ratio coefficient, so that split and merge are representable without schema-level branching.

#### Acceptance Criteria

1. Migration 282 shall create `kvota.invoice_item_coverage(invoice_item_id UUID FK → invoice_items ON DELETE CASCADE, quote_item_id UUID FK → quote_items ON DELETE CASCADE, ratio NUMERIC NOT NULL DEFAULT 1 CHECK (ratio > 0), PRIMARY KEY (invoice_item_id, quote_item_id))`.
2. Migration 282 shall add indexes `idx_coverage_invoice_item (invoice_item_id)` and `idx_coverage_quote_item (quote_item_id)`.
3. Migration 282 shall enable RLS with the same 10/4/2 role pattern as invoice_items, org-scoped via JOIN to invoice_items.
4. `ratio` semantics: `invoice_item_units per quote_item_unit`. Validation rule for application layer: for each coverage row, `invoice_item.quantity ≈ quote_item.quantity × ratio` (within floating-point tolerance).

### Requirement 3: Backfill from invoice_item_prices

**Objective:** As the deployment process, I want existing Phase 5b composition data migrated losslessly into the Phase 5c schema, so that all 124+ backfilled quotes continue to calculate identically.

#### Acceptance Criteria

1. Migration 283 shall INSERT one `invoice_items` row per `invoice_item_prices` row, copying `invoice_id`, `organization_id`, `purchase_price_original`, `purchase_currency`, `base_price_vat`, `price_includes_vat`, `production_time_days`, `minimum_order_quantity`, `supplier_notes`, `version`, `frozen_at`, `frozen_by`, `created_at`, `updated_at`, `created_by`.
2. Migration 283 shall copy `product_name`, `supplier_sku`, `brand`, `weight_in_kg`, `customs_code`, `supplier_country`, `vat_rate`, `dimension_*_mm`, `license_*_cost`, `quantity` from the linked `quote_items` row into the new invoice_items row. (One-shot means invoice_items absorb these supplier-side fields from quote_items at backfill time.)
3. Migration 283 shall INSERT one `invoice_item_coverage` row per new invoice_items row, with `ratio=1` and `quote_item_id` from the original iip.quote_item_id.
4. Migration 283 shall assign `invoice_items.position` as a 1-based ordinal within each invoice (ORDER BY source iip.created_at).
5. Migration 283 shall be idempotent — re-running is a no-op (use `ON CONFLICT DO NOTHING` on new inserts).
6. A Python regression test shall compute `calculate_multiproduct_quote()` on 5+ representative pre-Phase-5c quotes using data snapshots taken before migration 283, then again after. Outputs shall be bit-identical for every monetary field and item-level result.

### Requirement 4: Legacy Schema Drop

**Objective:** As code hygiene, I want legacy invoice/price pointers removed from `quote_items` after Phase 5c, so that the single-source-of-truth pattern is enforced at the DB level.

#### Acceptance Criteria

1. Migration 284 shall DROP `kvota.invoice_item_prices` table.
2. Migration 284 shall DROP columns from `kvota.quote_items`: `invoice_id`, `purchase_price_original`, `purchase_currency`, `base_price_vat`, `price_includes_vat`, `customs_code`, `supplier_country`, `weight_in_kg`, `production_time_days`, `minimum_order_quantity`, `dimension_height_mm`, `dimension_width_mm`, `dimension_length_mm`, `license_ds_cost`, `license_ss_cost`, `license_sgr_cost`.
3. Migration 284 shall PRESERVE on `quote_items`: `id`, `quote_id`, `idn_sku`, `product_name`, `brand`, `quantity`, `composition_selected_invoice_id`, `is_unavailable`, `import_banned`, `markup`, `supplier_discount`, `vat_rate`, `supplier_sku`, `supplier_sku_note`, `manufacturer_product_name`, `name_en`, `position`, `created_at`, `updated_at`. These represent the customer's request + sales-side markups + substitution metadata.
4. All code referencing dropped columns shall be updated to read from `invoice_items` via `composition_service.get_composed_items()` BEFORE migration 284 runs. Pre-check: grep for dropped column names returns zero matches in `main.py`, `services/`, `frontend/src/` at the commit migration 284 ships on.

### Requirement 5: Composition Service Rewrite

**Objective:** As the calculation pipeline, I want `composition_service.get_composed_items()` to produce calc-ready items from the new schema, so that the locked calculation engine sees "one chosen price per applicable item" exactly as today.

#### Acceptance Criteria

1. `services/composition_service.py` shall retain the public API: `get_composed_items(quote_id, supabase)`, `get_composition_view(quote_id, supabase, user_id=None)`, `apply_composition(quote_id, selection_map, supabase, user_id, quote_updated_at)`, `validate_composition(quote_id, selection_map, supabase)`, `freeze_composition(quote_id, user_id, supabase)`.
2. `get_composed_items()` shall read `quote_items` (for customer-side fields: `is_unavailable`, `import_banned`, `markup`, `supplier_discount`, `quantity`, `vat_rate`) and JOIN `invoice_item_coverage` → `invoice_items` where `coverage.quote_item_id = qi.id AND invoice_items.invoice_id = qi.composition_selected_invoice_id`.
3. For each quote_item with `composition_selected_invoice_id IS NOT NULL`, `get_composed_items()` shall return one result dict per covering invoice_item (split produces multiple results for one quote_item; merge produces one result covering multiple quote_items — the result is emitted once per distinct invoice_item, not per coverage row).
4. For each quote_item with `composition_selected_invoice_id IS NULL`, `get_composed_items()` shall emit a single result dict using defaults for now-dropped columns (e.g., `purchase_price_original=None`, `weight_in_kg=None`) — calc engine already tolerates missing values for non-composed items.
5. Result dicts shall contain all fields `build_calculation_inputs()` reads: `is_unavailable`, `import_banned`, `purchase_currency`, `purchase_price_original`, `quantity` (from invoice_item), `weight_in_kg` (from invoice_item), `customs_code` (from invoice_item), `supplier_country` (from invoice_item), `price_includes_vat` (from invoice_item), `markup` (from quote_item), `supplier_discount` (from quote_item), `license_ds_cost`, `license_ss_cost`, `license_sgr_cost` (from invoice_item). Customer-side identity fields (product_name, brand, idn_sku) come from the invoice_item when composed, quote_item when not.
6. `get_composed_items()` shall execute in ≤3 SQL queries total regardless of item count (no N+1). Pattern: 1 query for quote_items, 1 query for coverage with JOIN to invoice_items, 1 optional lookup for invoice metadata.

### Requirement 6: Calculation Engine Immutability (Unchanged from Phase 5b)

**Objective:** As a system safeguard, `calculation_engine.py`, `calculation_models.py`, and `calculation_mapper.py` shall remain untouched through Phase 5c.

#### Acceptance Criteria

1. The Phase 5c merge commit range shall show zero modifications to the three locked files.
2. `services/composition_service.py` shall not import from any locked file.
3. Regression test in Requirement 3.6 shall pass on 5+ representative quotes.

### Requirement 7: Edit-Gate Migration from sent_at to procurement_completed_at

**Objective:** As a procurement user, I want to freely edit invoices while awaiting supplier quotes (after clicking "Отправить"), so that the natural send → wait → receive-prices → edit flow works without approval bureaucracy.

#### Acceptance Criteria

1. `services/invoice_send_service.check_edit_permission(invoice_id, user_roles)` shall check `quote.procurement_completed_at IS NOT NULL` instead of `invoice.sent_at IS NOT NULL`. Signature accepts `invoice_id` as today; function internally looks up invoice.quote_id → quote.procurement_completed_at.
2. `services/invoice_send_service._EDIT_OVERRIDE_ROLES = {"admin", "head_of_procurement"}` shall remain unchanged — those roles bypass the gate regardless of procurement_completed_at.
3. `api/invoices.py` `request_edit_approval` endpoint shall be renamed to `request_procurement_unlock`. The `approval_type` field on the created approvals row shall change from `"edit_sent_invoice"` to `"edit_completed_procurement"`. Existing DB rows with the old approval_type are left as-is (historical).
4. Error code returned by blocked mutations shall change from `EDIT_REQUIRES_APPROVAL` to `PROCUREMENT_LOCKED`.
5. `invoices.sent_at` column and its setter code shall remain. Writing to `sent_at` shall have no blocking effect on subsequent edits.
6. Frontend `EditApprovalButton` component shall be renamed to `ProcurementUnlockButton`. Its render condition shall change from `invoice.sent_at != null` to `quote.procurement_completed_at != null`.
7. Frontend `invoice-card.tsx` variable `isSent` shall be renamed to `isLocked`. The green "Отправлено [date]" badge remains (derived from sent_at) as pure metadata, NOT as a gate indicator.

### Requirement 8: Non-Destructive Positions List UI

**Objective:** As a procurement user, I want to see all quote items at all times and assign them to multiple invoices without removing them from previous assignments, so that I can build up competing supplier offers with simple clicks.

#### Acceptance Criteria

1. `frontend/src/features/quotes/ui/procurement-step/unassigned-items.tsx` shall be renamed to `quote-positions-list.tsx` (or similar). The component shall remove the `items.filter(i => i.invoice_id == null)` filter and render ALL quote_items of the quote.
2. The section header shall change from "Нераспределённые позиции (N)" to "Позиции заявки (N)".
3. Each row shall display an additional column/badge "В КП" showing the count and list of invoices covering this quote_item (joined via `invoice_item_coverage` → `invoice_items` → `invoices`). Format: chip list like `INV-01, INV-02`; clicking a chip scrolls to the corresponding invoice-card below.
4. The "Назначить в КП" dropdown shall list ALL invoices of the quote (including non-empty ones), plus an option "➕ Создать новый КП". Assigning items via this dropdown shall be non-destructive: the quote_items retain coverage rows in previously-assigned invoices.
5. Assigning items shall insert new `invoice_items` rows (one per selected quote_item, with defaults copied from quote_items but mutable within the target invoice) and new `invoice_item_coverage` rows (`ratio=1`). Re-assigning to the same (invoice, quote_item) pair shall be a no-op (ON CONFLICT DO NOTHING).
6. The invoice-card items list shall be derived from `invoice_items` via coverage, NOT from the dropped legacy FK `quote_items.invoice_id`.

### Requirement 9: Split UI

**Objective:** As a procurement user, I want to split a quote_item into N invoice_items within a specific invoice when a supplier proposes a decomposed offer, so that the customer's original request remains intact while the supplier's structure is faithfully captured.

#### Acceptance Criteria

1. Invoice-card header shall include a "⚡ Разделить позицию" button (visible only when `!procurementCompleted` AND invoice is not frozen). Clicking opens a SplitModal.
2. SplitModal shall: (a) let user pick a source quote_item from invoice-card's current coverage; (b) define N ≥ 2 child positions, each with `name`, `sku`, `brand`, `quantity_ratio` (invoice_item_units per 1 quote_item_unit), `purchase_price_original`, `purchase_currency`, `weight_in_kg` (optional), `customs_code` (optional); (c) on submit, delete the source invoice_item (or its coverage rows with the picked quote_item), create N new invoice_items, and create N coverage rows each `(new_invoice_item_id, source_quote_item_id, ratio=quantity_ratio)`.
3. SplitModal shall validate `invoice_item.quantity = quote_item.quantity × ratio` for each child before submit. Submit is disabled until all validations pass.
4. Split shall NOT affect other invoices covering the same quote_item — split is local to the invoice where the action is triggered.
5. Split shall be irreversible through UI (no "undo split" button). Rollback is manual via admin UI or DB edit.
6. Split shall be disabled when `quote.procurement_completed_at IS NOT NULL` (gated by ProcurementUnlockButton flow).

### Requirement 10: Merge UI

**Objective:** As a procurement user, I want to merge multiple quote_items into one invoice_item within a specific invoice when a supplier bundles them into a single product, so that supplier consolidation is captured without losing the customer's itemized request.

#### Acceptance Criteria

1. Invoice-card header shall include a "⚡ Объединить позиции" button (visibility conditions mirror Split button).
2. MergeModal shall: (a) let user select N ≥ 2 source quote_items via checkbox on the invoice-card's current coverage; (b) define a single merged invoice_item with `name`, `sku`, `brand`, `quantity`, `purchase_price_original`, `purchase_currency`, `weight_in_kg`, `customs_code`; (c) on submit, delete the source invoice_items (those with 1:1 coverage to the selected quote_items), create one new merged invoice_item, and create N coverage rows each `(merged_invoice_item_id, source_quote_item_id, ratio=1)`.
3. MergeModal shall validate that each selected quote_item is 1:1 covered in the current invoice (no chain-merge of already-merged items in the same flow). If a selected quote_item is part of a split or existing merge, the modal blocks with a clear error.
4. Merge shall be local to the invoice and irreversible through UI (same rules as split).
5. The merged invoice_item's `quantity` shall default to the max of the source quote_items' quantities, editable by user before submit.

### Requirement 11: Migration Numbering and Rollout

**Objective:** As the deployment process, Phase 5c ships as migrations 281-284 in a single coordinated release.

#### Acceptance Criteria

1. Migrations ship in numeric order: 281 (create invoice_items), 282 (create coverage), 283 (backfill), 284 (drop iip + legacy columns).
2. The migration SQL files are committed in the same PR as the application code that reads from the new schema. Code and schema change land atomically.
3. A feature flag `NEXT_PUBLIC_INVOICE_ITEMS_UI` (default: off in prod, on in staging) gates the SplitModal and MergeModal UI surfaces during rollout. The non-destructive positions list and composition-service rewrite are unconditional (can't be flagged).
4. Rollback strategy: git revert the migrations commit + deploy. No formal `down` migrations are written (not maintained pattern in OneStack).
5. Pre-deploy checklist shall include: (a) bit-identity regression test (Requirement 3.6) passes on prod-data snapshot; (b) RLS policy test passes for all 10 SELECT roles on invoice_items; (c) browser smoke-test on staging: multi-supplier invoice creation, split, merge, calc, export.
