-- Migration 328: Move advance_pct + payment_terms from quote_items → invoices
-- Testing 2 row 69 — product decision (user 2026-05-25):
--   «Per-supplier и per-invoice. Два разных инвойса от одного суплаера
--    могут иметь разные цены из-за разных условий оплаты».
--
-- Currently:
--   quote_items.advance_to_supplier_percent (NUMERIC(5,2) DEFAULT 100, m016)
--   quote_items.supplier_payment_terms      (TEXT, m016)
--
-- After this migration:
--   invoices.advance_pct                    (NUMERIC(5,2) NULL with CHECK 0..100)
--   invoices.payment_terms                  (TEXT NULL)
--
-- The quote_items columns are dropped at the end so application code can no
-- longer hide divergence between the source of truth (invoices) and stale
-- position-level snapshots. Backfill picks the first non-null position value
-- per invoice (any divergence on the source side resolves to that value).
--
-- Wrapped in BEGIN/COMMIT for atomic schema swap (mitigates m318 partial-state
-- hazard documented in memory: apply-migrations.sh reports success when only
-- the last statement passes).

BEGIN;

-- =============================================================================
-- 1. Add columns to invoices (invoice-level fields)
-- =============================================================================

ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS advance_pct NUMERIC(5,2);

ALTER TABLE kvota.invoices
  ADD COLUMN IF NOT EXISTS payment_terms TEXT;

-- Bounded percent (0..100), consistent with the prior quote_items CHECK on
-- advance_to_supplier_percent (m016). NULL is allowed → field unset.
ALTER TABLE kvota.invoices
  DROP CONSTRAINT IF EXISTS invoices_advance_pct_range_check;

ALTER TABLE kvota.invoices
  ADD CONSTRAINT invoices_advance_pct_range_check
  CHECK (advance_pct IS NULL OR (advance_pct >= 0 AND advance_pct <= 100));

COMMENT ON COLUMN kvota.invoices.advance_pct IS
  'Required advance payment percent to supplier (0..100). Per-invoice — two invoices from the same supplier may have different terms (Testing 2 row 69, m328).';

COMMENT ON COLUMN kvota.invoices.payment_terms IS
  'Free-text supplier payment terms (e.g., "30% advance, 70% before shipment"). Per-invoice — see invoices.advance_pct (Testing 2 row 69, m328).';

-- =============================================================================
-- 2. Backfill: first non-null value per invoice group
-- =============================================================================
-- quote_items.invoice_id was removed in an earlier migration; the link runs
-- through invoice_item_coverage (m282). For each invoice we walk:
--   invoices.id → invoice_items.invoice_id → invoice_item_coverage.invoice_item_id
--                                          → invoice_item_coverage.quote_item_id
--                                          → quote_items (carries the per-position values)
--
-- DISTINCT ON (invoice_id) with ORDER BY ... NULLS LAST picks the first
-- non-null position per invoice. Each field is backfilled independently so a
-- partially-filled invoice (e.g., only payment terms set) still contributes
-- what it has. invoice_items.position breaks ties deterministically.

UPDATE kvota.invoices i
SET advance_pct = sub.advance_to_supplier_percent
FROM (
  SELECT DISTINCT ON (ii.invoice_id)
    ii.invoice_id,
    qi.advance_to_supplier_percent
  FROM kvota.invoice_items ii
  JOIN kvota.invoice_item_coverage cov ON cov.invoice_item_id = ii.id
  JOIN kvota.quote_items qi ON qi.id = cov.quote_item_id
  WHERE qi.advance_to_supplier_percent IS NOT NULL
  ORDER BY ii.invoice_id, ii.position NULLS LAST, qi.created_at NULLS LAST
) sub
WHERE i.id = sub.invoice_id
  AND i.advance_pct IS NULL;

UPDATE kvota.invoices i
SET payment_terms = sub.supplier_payment_terms
FROM (
  SELECT DISTINCT ON (ii.invoice_id)
    ii.invoice_id,
    qi.supplier_payment_terms
  FROM kvota.invoice_items ii
  JOIN kvota.invoice_item_coverage cov ON cov.invoice_item_id = ii.id
  JOIN kvota.quote_items qi ON qi.id = cov.quote_item_id
  WHERE qi.supplier_payment_terms IS NOT NULL
    AND LENGTH(TRIM(qi.supplier_payment_terms)) > 0
  ORDER BY ii.invoice_id, ii.position NULLS LAST, qi.created_at NULLS LAST
) sub
WHERE i.id = sub.invoice_id
  AND i.payment_terms IS NULL;

-- =============================================================================
-- 3. Drop source columns from quote_items
-- =============================================================================
-- Removed unconditionally — there is no read path remaining after this
-- migration ships. The matching frontend/backend changes in this PR replace
-- every reader with the invoice-level fields.

ALTER TABLE kvota.quote_items
  DROP COLUMN IF EXISTS advance_to_supplier_percent;

ALTER TABLE kvota.quote_items
  DROP COLUMN IF EXISTS supplier_payment_terms;

-- =============================================================================
-- 4. Track migration
-- =============================================================================

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (328, '328_move_advance_pct_payment_terms_to_invoice.sql', now())
ON CONFLICT (id) DO NOTHING;

COMMIT;
