-- Migration 235: Allow zero weight on invoices
-- Fix: invoice creation fails because CHECK (total_weight_kg > 0) rejects default 0
-- Weight may not be known at creation time — filled later during procurement
-- Date: 2026-03-28

ALTER TABLE kvota.invoices
DROP CONSTRAINT IF EXISTS invoices_weight_check;

ALTER TABLE kvota.invoices
ADD CONSTRAINT invoices_weight_check
CHECK (total_weight_kg >= 0);

-- Also make total_weight_kg nullable with default 0 so it's optional at creation
ALTER TABLE kvota.invoices
ALTER COLUMN total_weight_kg SET DEFAULT 0;

ALTER TABLE kvota.invoices
ALTER COLUMN total_weight_kg DROP NOT NULL;
