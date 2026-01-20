-- Migration: Extend quotes table with v3.0 columns (FIXED for kvota schema)
-- Feature #DB-011: Add idn, seller_company_id columns for supply chain
-- Description: Adds IDN system and seller company reference at quote level
-- Created: 2026-01-20
-- Version: 3.0 (fixed)

SET search_path TO kvota;

-- =============================================================================
-- ADD FOREIGN KEY CONSTRAINTS
-- =============================================================================

-- Foreign key for seller_company_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_seller_company_id_fkey'
    ) THEN
        ALTER TABLE kvota.quotes
        ADD CONSTRAINT quotes_seller_company_id_fkey
        FOREIGN KEY (seller_company_id)
        REFERENCES kvota.seller_companies(id)
        ON DELETE SET NULL;

        RAISE NOTICE 'Added foreign key quotes_seller_company_id_fkey';
    ELSE
        RAISE NOTICE 'Foreign key quotes_seller_company_id_fkey already exists';
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'seller_companies table not found, skipping FK constraint';
END $$;

-- =============================================================================
-- ADD INDEXES FOR QUERY PERFORMANCE
-- =============================================================================

-- Index on idn for quick lookups by IDN
CREATE INDEX IF NOT EXISTS idx_quotes_idn_v3
ON kvota.quotes(idn)
WHERE idn IS NOT NULL;

-- Unique index on idn (IDN must be unique across all quotes)
CREATE UNIQUE INDEX IF NOT EXISTS idx_quotes_idn_unique_v3
ON kvota.quotes(idn)
WHERE idn IS NOT NULL;

-- Index on seller_company_id for filtering quotes by seller company
CREATE INDEX IF NOT EXISTS idx_quotes_seller_company_id_v3
ON kvota.quotes(seller_company_id)
WHERE seller_company_id IS NOT NULL;

-- =============================================================================
-- ADD COMMENTS
-- =============================================================================

COMMENT ON COLUMN kvota.quotes.idn IS 'Quote IDN in format SELLER-INN-YEAR-SEQ (e.g., CMT-1234567890-2025-1). Generated when quote is finalized.';
COMMENT ON COLUMN kvota.quotes.seller_company_id IS 'Reference to seller_companies table. Our legal entity used for selling (e.g., CMT, MBR, RAR). Set at quote level.';
