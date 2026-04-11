-- Phase 3: Replace the hardcoded currency allowlist with a format-only regex check.
-- Aligns deal_logistics_expenses with all other currency-bearing tables in the schema.
-- All existing rows satisfy the new constraint because they already satisfied the stricter IN list.

ALTER TABLE kvota.deal_logistics_expenses
    DROP CONSTRAINT IF EXISTS deal_logistics_expenses_currency_check;

ALTER TABLE kvota.deal_logistics_expenses
    ADD CONSTRAINT deal_logistics_expenses_currency_check
    CHECK (currency ~ '^[A-Z]{3}$');
