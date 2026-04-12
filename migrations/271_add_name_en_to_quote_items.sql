-- Phase 4b: bilingual document output
-- Adds English name column to quote_items so procurement can prepare КП
-- documents in English for non-Russian-speaking suppliers (90% of them).
-- Filled manually by users; no AI translation in scope for Phase 4.
-- When NULL, the English XLS export falls back to the Russian product_name.

ALTER TABLE kvota.quote_items
  ADD COLUMN IF NOT EXISTS name_en TEXT;

COMMENT ON COLUMN kvota.quote_items.name_en IS
  'English name of the item for supplier КП documents. NULL = fall back to product_name in EN exports.';
