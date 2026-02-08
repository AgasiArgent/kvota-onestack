-- Migration 158: Add order_source column to customers table
-- Tracks how the customer was acquired (cold call, recommendation, tender, etc.)

ALTER TABLE kvota.customers ADD COLUMN IF NOT EXISTS order_source TEXT;
COMMENT ON COLUMN kvota.customers.order_source IS 'How the customer was acquired: cold_call, recommendation, tender, website, exhibition, social, repeat, other';
