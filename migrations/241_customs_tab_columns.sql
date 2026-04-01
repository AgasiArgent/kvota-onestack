-- Migration 241: Add customs-related columns to quote_items
-- Per-item customs fields, split duty inputs, and import ban flag.
-- Date: 2026-03-30

-- Per-item customs fields
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_ds_sgr VARCHAR(255);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_util_fee DECIMAL(15,4);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_excise DECIMAL(15,4);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_psn_pts VARCHAR(255);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_notification VARCHAR(255);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_licenses VARCHAR(255);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_marking VARCHAR(255);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_eco_fee DECIMAL(15,4);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_honest_mark VARCHAR(255);

-- Split duty: percent-based and per-kg components
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_duty_percent DECIMAL(15,4);
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS customs_duty_per_kg DECIMAL(15,4);

-- Import ban flag and reason
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS import_banned BOOLEAN DEFAULT FALSE;
ALTER TABLE kvota.quote_items ADD COLUMN IF NOT EXISTS import_ban_reason TEXT;
