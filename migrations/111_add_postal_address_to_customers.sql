-- Add postal_address column to customers table
-- Migration: 111_add_postal_address_to_customers.sql

-- Add postal_address column
ALTER TABLE kvota.customers
ADD COLUMN IF NOT EXISTS postal_address TEXT;

-- Add comment for documentation
COMMENT ON COLUMN kvota.customers.postal_address IS 'Почтовый адрес (если отличается от фактического адреса)';
