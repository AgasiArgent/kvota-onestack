-- Migration 199: Enrich company tables with fields needed for currency invoice documents
-- Adds legal_name, tax_id, address to buyer_companies
-- Adds address, tax_id to seller_companies
-- These fields are used by _resolve_company_details() in main.py for DOCX export headers

-- =============================================================
-- buyer_companies: add legal_name, tax_id, address
-- =============================================================

-- Full legal name for document headers (distinct from short display 'name')
ALTER TABLE kvota.buyer_companies
ADD COLUMN IF NOT EXISTS legal_name TEXT;

-- Tax ID / VAT number for international companies (non-Russian format)
ALTER TABLE kvota.buyer_companies
ADD COLUMN IF NOT EXISTS tax_id TEXT;

-- Physical/mailing address for invoice document headers
ALTER TABLE kvota.buyer_companies
ADD COLUMN IF NOT EXISTS address TEXT;

COMMENT ON COLUMN kvota.buyer_companies.legal_name IS 'Full legal name for document headers (distinct from short display name)';
COMMENT ON COLUMN kvota.buyer_companies.tax_id IS 'Tax ID / VAT number for document headers (EU VAT, TR tax number, etc.)';
COMMENT ON COLUMN kvota.buyer_companies.address IS 'Mailing/physical address for invoice document headers';

-- =============================================================
-- seller_companies: add address, tax_id
-- =============================================================

-- Physical/mailing address for invoice document headers
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS address TEXT;

-- Tax ID for international context (Russian companies already have inn column)
ALTER TABLE kvota.seller_companies
ADD COLUMN IF NOT EXISTS tax_id TEXT;

COMMENT ON COLUMN kvota.seller_companies.address IS 'Mailing/physical address for invoice document headers';
COMMENT ON COLUMN kvota.seller_companies.tax_id IS 'Tax ID for international context (distinct from Russian inn column)';

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (199, '199_enrich_company_fields.sql', now())
ON CONFLICT (id) DO NOTHING;
