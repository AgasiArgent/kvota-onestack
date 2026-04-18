-- migrations/283_backfill_invoice_items.sql
-- Phase 5c Task 3: Backfill invoice_items + invoice_item_coverage from
-- existing Phase 5b data (invoice_item_prices + quote_items).
--
-- Contract (design.md §1.2, requirements.md REQ 3):
--   For every invoice_item_prices row, insert one invoice_items row. Supplier-
--   side fields (product_name, brand, weight, customs_code, supplier_country,
--   dimensions, licenses, vat_rate, quantity) are copied from the linked
--   quote_items row at backfill time — Phase 5b stored them on quote_items;
--   Phase 5c relocates them to invoice_items. Pricing fields (purchase_price_*,
--   base_price_vat, price_includes_vat, production_time_days, minimum_order_quantity,
--   supplier_notes) come from the iip row itself. Versioning + audit fields
--   (version, frozen_at, frozen_by, created_at, updated_at, created_by) are
--   carried over verbatim.
--
--   For every invoice_items row created, insert one invoice_item_coverage row
--   with ratio = 1 (every Phase 5b composition was 1:1 — split/merge is a
--   Phase 5c-only affordance). Coverage.quote_item_id = the original
--   iip.quote_item_id.
--
--   position assigned per-invoice as ROW_NUMBER() ORDER BY iip.created_at, iip.id.
--
-- Design choice: a single CTE does both inserts atomically. The CTE's RETURNING
-- clause carries the source iip.quote_item_id into the subsequent coverage
-- insert — no separate lookup or position-based join needed. This is the
-- "simpler alternative" called out in tasks.md Task 3 GREEN note.
--
-- Idempotency: both INSERTs use ON CONFLICT DO NOTHING. Re-running is a no-op
-- because UNIQUE(invoice_id, position, version) on invoice_items and
-- PK(invoice_item_id, quote_item_id) on coverage both block duplicates.
--
-- Source of truth: .kiro/specs/phase-5c-invoice-items/design.md §1.2 + §7.2 + §7.3
--                  .kiro/specs/phase-5c-invoice-items/requirements.md REQ 3

SET search_path TO kvota, public;

-- Single CTE: insert invoice_items and coverage in one pass.
--
--   backfill_src   — collects each iip row with its derived position and the
--                    quote_items fields to carry over
--   inserted_items — performs the INSERT into invoice_items and RETURNs the
--                    generated id plus the original iip.quote_item_id so
--                    coverage can be wired up without a second lookup
WITH backfill_src AS (
    SELECT
        iip.id                      AS src_iip_id,
        iip.invoice_id,
        iip.organization_id,
        ROW_NUMBER() OVER (
            PARTITION BY iip.invoice_id
            ORDER BY iip.created_at, iip.id
        )                           AS position,
        -- Identity from quote_items (Phase 5b had no per-iip product_name;
        -- the canonical customer-side name was on quote_items)
        qi.product_name             AS product_name,
        qi.supplier_sku             AS supplier_sku,
        qi.brand                    AS brand,
        -- Pricing from iip (Phase 5b overlay semantics)
        qi.quantity                 AS quantity,
        iip.purchase_price_original AS purchase_price_original,
        iip.purchase_currency       AS purchase_currency,
        iip.base_price_vat          AS base_price_vat,
        iip.price_includes_vat      AS price_includes_vat,
        qi.vat_rate                 AS vat_rate,
        -- Supplier-specific attributes (these are quote_items columns today;
        -- migration 284 drops them after all readers move to invoice_items)
        qi.weight_in_kg             AS weight_in_kg,
        qi.customs_code             AS customs_code,
        qi.supplier_country         AS supplier_country,
        -- production_time_days + minimum_order_quantity live on BOTH iip and
        -- quote_items in Phase 5b. Prefer iip (per-supplier value); fall back
        -- to quote_items for pre-Phase-5b data where iip may not have them.
        COALESCE(iip.production_time_days, qi.production_time_days)
                                    AS production_time_days,
        COALESCE(iip.minimum_order_quantity, CAST(qi.min_order_quantity AS INTEGER))
                                    AS minimum_order_quantity,
        qi.dimension_height_mm      AS dimension_height_mm,
        qi.dimension_width_mm       AS dimension_width_mm,
        qi.dimension_length_mm      AS dimension_length_mm,
        qi.license_ds_cost          AS license_ds_cost,
        qi.license_ss_cost          AS license_ss_cost,
        qi.license_sgr_cost         AS license_sgr_cost,
        iip.supplier_notes          AS supplier_notes,
        -- Version/freeze/audit straight from iip
        iip.version                 AS version,
        iip.frozen_at               AS frozen_at,
        iip.frozen_by               AS frozen_by,
        iip.created_at              AS created_at,
        iip.updated_at              AS updated_at,
        iip.created_by              AS created_by,
        -- quote_item_id stays on the coverage side
        iip.quote_item_id           AS quote_item_id
    FROM kvota.invoice_item_prices iip
    JOIN kvota.quote_items qi ON qi.id = iip.quote_item_id
),
-- Guard against the re-run case: skip rows whose (invoice_id, position, version)
-- already exists in invoice_items. UNIQUE(invoice_id, position, version) would
-- catch it via ON CONFLICT DO NOTHING too, but filtering upfront keeps the
-- RETURNING set clean (no silently dropped rows to handle downstream).
filtered AS (
    SELECT s.*
    FROM backfill_src s
    WHERE NOT EXISTS (
        SELECT 1
        FROM kvota.invoice_items ii
        WHERE ii.invoice_id = s.invoice_id
          AND ii.position   = s.position
          AND ii.version    = s.version
    )
),
inserted_items AS (
    INSERT INTO kvota.invoice_items (
        invoice_id,
        organization_id,
        position,
        product_name,
        supplier_sku,
        brand,
        quantity,
        purchase_price_original,
        purchase_currency,
        base_price_vat,
        price_includes_vat,
        vat_rate,
        weight_in_kg,
        customs_code,
        supplier_country,
        production_time_days,
        minimum_order_quantity,
        dimension_height_mm,
        dimension_width_mm,
        dimension_length_mm,
        license_ds_cost,
        license_ss_cost,
        license_sgr_cost,
        supplier_notes,
        version,
        frozen_at,
        frozen_by,
        created_at,
        updated_at,
        created_by
    )
    SELECT
        invoice_id,
        organization_id,
        position,
        -- invoice_items.product_name is NOT NULL; fall back to a stable
        -- placeholder for backfill rows where quote_items.product_name is NULL
        -- (extremely rare in practice but the CHECK would otherwise fail)
        COALESCE(product_name, 'Imported position'),
        supplier_sku,
        brand,
        -- invoice_items.quantity is NOT NULL CHECK (> 0); fall back to 1
        -- for any degenerate source rows
        COALESCE(quantity, 1),
        purchase_price_original,
        -- invoice_items.purchase_currency is NOT NULL; fall back to USD for
        -- any Phase 5b rows missing currency (iip.purchase_currency was NOT
        -- NULL so this is defensive only)
        COALESCE(purchase_currency, 'USD'),
        base_price_vat,
        COALESCE(price_includes_vat, false),
        vat_rate,
        weight_in_kg,
        customs_code,
        supplier_country,
        production_time_days,
        minimum_order_quantity,
        dimension_height_mm,
        dimension_width_mm,
        dimension_length_mm,
        license_ds_cost,
        license_ss_cost,
        license_sgr_cost,
        supplier_notes,
        version,
        frozen_at,
        frozen_by,
        created_at,
        updated_at,
        created_by
    FROM filtered
    ON CONFLICT (invoice_id, position, version) DO NOTHING
    RETURNING id, invoice_id, position, version
)
-- Coverage insert: one row per backfilled invoice_item, ratio = 1.
--
-- Matching backfilled invoice_items back to their source quote_item_id via
-- (invoice_id, position, version), which is the UNIQUE key on invoice_items
-- and is deterministic from backfill_src.
INSERT INTO kvota.invoice_item_coverage (invoice_item_id, quote_item_id, ratio)
SELECT
    inserted_items.id,
    backfill_src.quote_item_id,
    1
FROM inserted_items
JOIN backfill_src
  ON backfill_src.invoice_id = inserted_items.invoice_id
 AND backfill_src.position   = inserted_items.position
 AND backfill_src.version    = inserted_items.version
ON CONFLICT (invoice_item_id, quote_item_id) DO NOTHING;


-- Second pass: cover the "already inserted, coverage missing" case.
-- This handles mid-flight failures (e.g. invoice_items insert succeeded in a
-- prior run but the coverage insert did not). Without this, re-running the
-- migration would leave those rows permanently without coverage because the
-- CTE above only references inserted_items (the NEW inserts).
--
-- Builds a mapping iip_id → (invoice_id, position, version) via ROW_NUMBER()
-- and joins invoice_items on that triple (which is UNIQUE on ii).
WITH iip_position AS (
    SELECT
        iip.id                AS iip_id,
        iip.invoice_id,
        iip.quote_item_id,
        iip.version,
        ROW_NUMBER() OVER (
            PARTITION BY iip.invoice_id
            ORDER BY iip.created_at, iip.id
        )                     AS position
    FROM kvota.invoice_item_prices iip
)
INSERT INTO kvota.invoice_item_coverage (invoice_item_id, quote_item_id, ratio)
SELECT
    ii.id,
    iip_position.quote_item_id,
    1
FROM kvota.invoice_items ii
JOIN iip_position
  ON iip_position.invoice_id = ii.invoice_id
 AND iip_position.version    = ii.version
 AND iip_position.position   = ii.position
ON CONFLICT (invoice_item_id, quote_item_id) DO NOTHING;
