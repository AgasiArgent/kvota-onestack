-- Migration 188: Add region column to buyer_companies for currency invoice routing
-- Problem: currency_invoice_service checks country == "EU" / "TR" but actual data
-- has full country names ("Germany", "Turkey"). Region column provides clean routing.

ALTER TABLE kvota.buyer_companies
ADD COLUMN IF NOT EXISTS region VARCHAR(5);

-- Set default values for known companies
UPDATE kvota.buyer_companies SET region = 'EU' WHERE company_code = 'KEU' AND country = 'Germany';
UPDATE kvota.buyer_companies SET region = 'TR' WHERE company_code = 'GES' AND country = 'Turkey';

-- Add CHECK constraint: only EU and TR for now
ALTER TABLE kvota.buyer_companies
ADD CONSTRAINT chk_buyer_companies_region CHECK (region IN ('EU', 'TR'));

-- Comment explaining purpose
COMMENT ON COLUMN kvota.buyer_companies.region IS 'Region code for currency invoice segment routing: EU (European) or TR (Turkish). Used by currency_invoice_service to determine EURTR vs TRRU invoice segments.';
