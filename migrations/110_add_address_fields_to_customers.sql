-- Add legal_address and actual_address columns to customers table
-- Migration: 110_add_address_fields_to_customers.sql

-- Add new address columns to customers table in kvota schema
ALTER TABLE kvota.customers
ADD COLUMN IF NOT EXISTS legal_address TEXT,
ADD COLUMN IF NOT EXISTS actual_address TEXT;

-- Migrate existing address data to legal_address
UPDATE kvota.customers
SET legal_address = address
WHERE address IS NOT NULL AND legal_address IS NULL;

-- Add comments for documentation
COMMENT ON COLUMN kvota.customers.legal_address IS 'Юридический адрес компании (legal registration address)';
COMMENT ON COLUMN kvota.customers.actual_address IS 'Фактический адрес компании (actual business address)';
COMMENT ON COLUMN kvota.customers.address IS 'Legacy address field - use legal_address instead';
