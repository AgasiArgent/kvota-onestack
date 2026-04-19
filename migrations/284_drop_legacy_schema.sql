-- migrations/284_drop_legacy_schema.sql
-- Phase 5c + 5d Group 6: drop the legacy per-item price/attribute schema
-- now that composition reads through invoice_items + invoice_item_coverage.
--
-- After this migration, quote_items carries only customer-side identity and
-- workflow columns; all supplier-specific pricing and attributes live on
-- invoice_items (migrations 281/282 + backfill 283).
--
-- Source of truth: .kiro/specs/phase-5c-invoice-items/design.md §1.2 + §6
--                  .kiro/specs/phase-5d-legacy-refactor/design.md §3
--                  .kiro/specs/phase-5d-legacy-refactor/main-py-classification.md
--
-- Drops (in order):
--   1. DROP VIEW kvota.positions_registry_view — PostgreSQL blocks column
--      drops while dependent views exist. The view is recreated at the end
--      of this migration to source price data from invoice_items (Pattern C
--      per phase-5d design.md §2.3).
--   2. Explicit index + FK cleanup on quote_items.purchase_currency and
--      quote_items.invoice_id. ALTER TABLE DROP COLUMN cascades these too,
--      but the explicit form documents intent and keeps the DROP COLUMN
--      list scoped to columns (not constraints/indexes).
--   3. ALTER TABLE kvota.quote_items DROP COLUMN (16 supplier-side columns
--      now owned by invoice_items).
--   4. DROP TABLE kvota.invoice_item_prices — fully replaced by
--      invoice_items + invoice_item_coverage. Backfill 283 copied every
--      row before we drop the table.
--   5. CREATE VIEW kvota.positions_registry_view — rewritten to JOIN
--      invoice_item_coverage + invoice_items, filtered by the quote_item's
--      composition_selected_invoice_id. Shape of the returned rows is
--      identical to the previous view so downstream entity/position/queries.ts
--      and the UI need no changes.
--
-- Idempotency: DROP COLUMN IF EXISTS / DROP TABLE IF EXISTS / DROP INDEX
-- IF EXISTS make this re-runnable. CREATE OR REPLACE VIEW at the tail
-- keeps recreation idempotent.

SET search_path TO kvota, public;

-- ---------------------------------------------------------------------------
-- Step 1: drop the dependent view so its columns become droppable
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS kvota.positions_registry_view;

-- ---------------------------------------------------------------------------
-- Step 2: explicit index + FK cleanup for dropped columns on quote_items
-- ---------------------------------------------------------------------------

-- Partial index on purchase_currency (created in migration 121)
DROP INDEX IF EXISTS kvota.idx_quote_items_purchase_currency;

-- Partial index on invoice_id (created in migration 123)
DROP INDEX IF EXISTS kvota.idx_quote_items_invoice_id;

-- FK constraint on invoice_id → invoices(id). ALTER TABLE DROP COLUMN
-- would cascade-drop the constraint, but naming it explicitly documents
-- the intent and protects against future column ordering changes.
ALTER TABLE kvota.quote_items
    DROP CONSTRAINT IF EXISTS quote_items_invoice_id_fkey;

-- ---------------------------------------------------------------------------
-- Step 3: drop the 16 legacy columns on quote_items
-- ---------------------------------------------------------------------------
-- All of these have equivalents on invoice_items, populated by migration 283.
-- See design.md §1.2 "columns dropped in migration 284" for per-column
-- rationale.

ALTER TABLE kvota.quote_items
    DROP COLUMN IF EXISTS invoice_id,
    DROP COLUMN IF EXISTS purchase_price_original,
    DROP COLUMN IF EXISTS purchase_currency,
    DROP COLUMN IF EXISTS base_price_vat,
    DROP COLUMN IF EXISTS price_includes_vat,
    DROP COLUMN IF EXISTS customs_code,
    DROP COLUMN IF EXISTS supplier_country,
    DROP COLUMN IF EXISTS weight_in_kg,
    DROP COLUMN IF EXISTS production_time_days,
    DROP COLUMN IF EXISTS min_order_quantity,
    DROP COLUMN IF EXISTS dimension_height_mm,
    DROP COLUMN IF EXISTS dimension_width_mm,
    DROP COLUMN IF EXISTS dimension_length_mm,
    DROP COLUMN IF EXISTS license_ds_cost,
    DROP COLUMN IF EXISTS license_ss_cost,
    DROP COLUMN IF EXISTS license_sgr_cost;

-- ---------------------------------------------------------------------------
-- Step 4: drop the invoice_item_prices table
-- ---------------------------------------------------------------------------
-- All rows have been copied to invoice_items by migration 283 (with 1:1
-- coverage rows). Phase 5b code paths that read this table have been
-- removed in Phase 5c + 5d refactors.

DROP TABLE IF EXISTS kvota.invoice_item_prices;

-- ---------------------------------------------------------------------------
-- Step 5: recreate positions_registry_view sourcing price from invoice_items
-- ---------------------------------------------------------------------------
-- Public contract of the view is unchanged:
--   columns:   brand, product_code, product_name,
--              latest_price, latest_currency,
--              last_moz_name, last_moz_id, last_updated,
--              entry_count, organization_id, availability_status
--
-- Rewrite approach (Pattern C per phase-5d design.md §2.3.3):
--   For each quote_item, its "canonical" price row is the invoice_item
--   whose invoice_id matches the quote_item's composition_selected_invoice_id.
--   If no composition is selected (legacy / pre-composition quote), there
--   is no price row — the item is effectively uncovered and its
--   availability_status collapses to "unavailable" (matches legacy view
--   behavior: NULL purchase_price_original → has_available = false).
--
-- Join shape:
--   quote_items  qi
--     LEFT JOIN invoice_item_coverage  iic ON iic.quote_item_id = qi.id
--     LEFT JOIN invoice_items          ii  ON ii.id = iic.invoice_item_id
--                                        AND ii.invoice_id = qi.composition_selected_invoice_id
--
-- The LEFT JOIN + filter-on-ON lets uncovered items flow through with
-- NULL price/currency, preserving the previous view's row set.

CREATE OR REPLACE VIEW kvota.positions_registry_view AS
WITH base AS (
  SELECT
    qi.brand,
    COALESCE(qi.product_code, '') AS product_code,
    qi.product_name,
    -- Price sourced from invoice_items via coverage, scoped to the
    -- quote_item's currently-selected invoice (composition pointer).
    ii.purchase_price_original,
    ii.purchase_currency,
    qi.is_unavailable,
    qi.updated_at,
    qi.assigned_procurement_user,
    qi.proforma_number,
    qi.quote_id,
    q.organization_id,
    q.idn AS quote_idn,
    up.full_name AS moz_name,
    ROW_NUMBER() OVER (
      PARTITION BY qi.brand, COALESCE(qi.product_code, '')
      ORDER BY qi.updated_at DESC
    ) AS rn,
    bool_or(NOT COALESCE(qi.is_unavailable, false)
            AND ii.purchase_price_original IS NOT NULL)
      OVER (PARTITION BY qi.brand, COALESCE(qi.product_code, '')) AS has_available,
    bool_or(COALESCE(qi.is_unavailable, false))
      OVER (PARTITION BY qi.brand, COALESCE(qi.product_code, '')) AS has_unavailable,
    COUNT(*) OVER (PARTITION BY qi.brand, COALESCE(qi.product_code, '')) AS entry_count
  FROM kvota.quote_items qi
  JOIN kvota.quotes q ON q.id = qi.quote_id
  LEFT JOIN kvota.invoice_item_coverage iic ON iic.quote_item_id = qi.id
  LEFT JOIN kvota.invoice_items ii
         ON ii.id = iic.invoice_item_id
        AND ii.invoice_id = qi.composition_selected_invoice_id
  LEFT JOIN kvota.user_profiles up ON up.user_id = qi.assigned_procurement_user
  WHERE qi.procurement_status = 'completed'
     OR COALESCE(qi.is_unavailable, false) = true
)
SELECT
  brand,
  product_code,
  product_name,
  purchase_price_original AS latest_price,
  purchase_currency AS latest_currency,
  moz_name AS last_moz_name,
  assigned_procurement_user AS last_moz_id,
  updated_at AS last_updated,
  entry_count,
  organization_id,
  CASE
    WHEN has_available AND has_unavailable THEN 'mixed'
    WHEN has_available THEN 'available'
    ELSE 'unavailable'
  END AS availability_status
FROM base
WHERE rn = 1;

COMMENT ON VIEW kvota.positions_registry_view IS
  'Phase 5d: aggregates quote_items by brand + product_code (supplier SKU). Price data sourced from invoice_items via invoice_item_coverage, filtered by quote_items.composition_selected_invoice_id. Replaces migration 228 view which read legacy quote_items.purchase_price_original / purchase_currency (dropped in migration 284).';
