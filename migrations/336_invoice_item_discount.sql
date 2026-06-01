-- Migration 336: Add `discount_pct` to invoice_items for per-line КПП discount.
-- Testing 2 row 91: procurement (МОЗ) can grant a per-line-item discount on a
-- supplier's КП. The discount is a percentage off the line's unit purchase
-- price; NULL / 0 means no discount.
--
-- The discount is applied to the effective purchase price in
-- build_calculation_inputs() (services/calculation_helpers.py) BEFORE the value
-- reaches the locked calculation engine:
--     effective_price = purchase_price_original * (1 - discount_pct / 100)
-- A NULL / 0 discount leaves the price unchanged, so the calc-engine
-- golden-master output is byte-identical for all existing (discount-less) data.
--
-- Per-line (NOT per-КПП, not whole-quote) — each invoice_items row carries its
-- own discount. Editing a discount on a procurement-completed (locked) КПП
-- routes through the existing request-edit → /approvals → approve flow
-- (approval_type='edit_completed_procurement'); no new approval machinery.
--
-- BEGIN/COMMIT wrap per feedback_apply_migrations_silent_partial (м318 incident
-- 2026-05-21): scripts/apply-migrations.sh only checks the LAST statement's
-- result, so multi-statement migrations must be transactional to avoid silent
-- partial state on prod.

BEGIN;

ALTER TABLE kvota.invoice_items
    ADD COLUMN IF NOT EXISTS discount_pct NUMERIC;

COMMENT ON COLUMN kvota.invoice_items.discount_pct IS
    'Per-line discount, percent off the line unit purchase price (Testing 2 row 91). '
    'NULL / 0 = no discount. Applied in build_calculation_inputs() as '
    'effective_price = purchase_price_original * (1 - discount_pct / 100) before '
    'the value reaches the locked calculation engine; NULL / 0 leaves it unchanged.';

COMMIT;
