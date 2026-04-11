-- migrations/265_backfill_composition.sql
-- Phase 5b Task 3: Idempotent backfill of invoice_item_prices + composition
-- pointer + invoice verification state.
--
-- This is the first Phase 5b migration that writes data. Idempotent by design:
-- re-applying produces zero additional effect thanks to ON CONFLICT DO NOTHING
-- (INSERT), NULL guards (UPDATE pointer), and the verified_at IS NULL guard
-- (UPDATE verified_at).
--
-- After this migration completes:
--
-- 1) Every quote_items row with a non-null invoice_id has a matching
--    (invoice_id, quote_item_id, version=1) row in invoice_item_prices,
--    with prices copied from quote_items.
--
-- 2) Every quote_items row with a non-null invoice_id has
--    composition_selected_invoice_id = invoice_id (composition pointer set).
--
-- 3) Every invoices row with status='completed' has verified_at set
--    (backfilled from updated_at or created_at — the latest meaningful
--    timestamp we have).
--
-- Existing calculations continue to produce identical results because:
--   - composition_service reads iip rows via the (composition_pointer) join
--   - the backfilled iip rows contain the exact same prices as quote_items
--   - therefore the overlay is a no-op for pre-Phase-5b data

SET search_path TO kvota, public;

-- 1) Populate invoice_item_prices from existing (quote_item, invoice) pairs.
--    JOIN to quotes resolves organization_id (required NOT NULL on iip).
--    Data quality fallback: if both purchase_price_original and base_price_vat
--    are NULL on an existing row, insert 0 (iip requires NOT NULL price) —
--    this matches the legacy path's implicit behaviour.
--    Note: quote_items has no created_by column, so iip.created_by stays NULL
--    for backfilled rows (we don't know historically who created them).
INSERT INTO kvota.invoice_item_prices (
    invoice_id,
    quote_item_id,
    organization_id,
    purchase_price_original,
    purchase_currency,
    base_price_vat,
    price_includes_vat,
    version,
    created_at,
    updated_at
)
SELECT
    qi.invoice_id,
    qi.id AS quote_item_id,
    q.organization_id,
    COALESCE(qi.purchase_price_original, qi.base_price_vat, 0) AS purchase_price_original,
    COALESCE(qi.purchase_currency, 'USD')                      AS purchase_currency,
    qi.base_price_vat,
    COALESCE(qi.price_includes_vat, false)                     AS price_includes_vat,
    1                                                          AS version,
    qi.created_at,
    qi.updated_at
FROM kvota.quote_items qi
JOIN kvota.quotes q ON q.id = qi.quote_id
WHERE qi.invoice_id IS NOT NULL
ON CONFLICT (invoice_id, quote_item_id, version) DO NOTHING;

-- 2) Set composition pointer = legacy invoice_id for existing items.
--    NULL guard ensures idempotency — re-running is a no-op.
UPDATE kvota.quote_items
SET composition_selected_invoice_id = invoice_id
WHERE invoice_id IS NOT NULL
  AND composition_selected_invoice_id IS NULL;

-- 3) Mark existing completed invoices as verified.
--    Uses updated_at or created_at as the verification timestamp
--    (best-effort for historical data). verified_by stays NULL since
--    we don't know who approved these historically.
UPDATE kvota.invoices
SET verified_at = COALESCE(updated_at, created_at)
WHERE status = 'completed'
  AND verified_at IS NULL;
