-- Migration 170: Make planned_amount, planned_currency, planned_date nullable
-- Purpose: Logistics expenses are fact-only entries (actual_amount/actual_currency/actual_date)
--          and do not have planned values. The NOT NULL constraints from migration 009
--          cause inserts to fail with:
--          "null value in column planned_amount of relation plan_fact_items violates not-null constraint"
-- Fix: Drop NOT NULL on all three planned_* columns so fact-only rows can be inserted.

ALTER TABLE kvota.plan_fact_items ALTER COLUMN planned_amount DROP NOT NULL;
ALTER TABLE kvota.plan_fact_items ALTER COLUMN planned_currency DROP NOT NULL;
ALTER TABLE kvota.plan_fact_items ALTER COLUMN planned_date DROP NOT NULL;

-- Record migration
INSERT INTO kvota.migrations (name, description)
VALUES ('170_make_planned_amount_nullable', 'Make planned_amount/planned_currency/planned_date nullable for fact-only entries (logistics expenses)')
ON CONFLICT DO NOTHING;
