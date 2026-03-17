-- Add general_email column to customers table
ALTER TABLE kvota.customers ADD COLUMN IF NOT EXISTS general_email VARCHAR(255);
