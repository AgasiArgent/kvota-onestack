-- Migration: Extend quotes table with v3.0 columns
-- Feature #DB-011: Add idn, seller_company_id columns for supply chain
-- Description: Adds IDN system and seller company reference at quote level
-- Created: 2026-01-15
-- Version: 3.0

-- =============================================================================
-- ADD NEW COLUMNS TO QUOTES TABLE FOR V3.0
-- =============================================================================

-- IDN - Identification Number for the quote
-- Format: SELLER-INN-YEAR-SEQ (e.g., CMT-1234567890-2025-1)
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS idn VARCHAR(100);

COMMENT ON COLUMN quotes.idn IS 'Quote IDN in format SELLER-INN-YEAR-SEQ (e.g., CMT-1234567890-2025-1). Generated when quote is finalized.';

-- Seller Company ID - Reference to the selling legal entity (our company)
-- This is at QUOTE level - one seller company for the entire quote
ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS seller_company_id UUID;

COMMENT ON COLUMN quotes.seller_company_id IS 'Reference to seller_companies table. Our legal entity used for selling (e.g., CMT, MBR, RAR). Set at quote level.';

-- =============================================================================
-- ADD FOREIGN KEY CONSTRAINTS
-- =============================================================================

-- Foreign key for seller_company_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_seller_company_id_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_seller_company_id_fkey
        FOREIGN KEY (seller_company_id)
        REFERENCES seller_companies(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        -- seller_companies table doesn't exist yet, skip FK constraint
        RAISE NOTICE 'seller_companies table not found, skipping FK constraint';
END $$;

-- =============================================================================
-- ADD INDEXES FOR QUERY PERFORMANCE
-- =============================================================================

-- Index on idn for quick lookups by IDN
CREATE INDEX IF NOT EXISTS idx_quotes_idn
ON quotes(idn)
WHERE idn IS NOT NULL;

-- Unique index on idn (IDN must be unique across all quotes)
CREATE UNIQUE INDEX IF NOT EXISTS idx_quotes_idn_unique
ON quotes(idn)
WHERE idn IS NOT NULL;

-- Index on seller_company_id for filtering quotes by seller company
CREATE INDEX IF NOT EXISTS idx_quotes_seller_company_id
ON quotes(seller_company_id)
WHERE seller_company_id IS NOT NULL;

-- =============================================================================
-- HELPER FUNCTION: Generate Quote IDN
-- =============================================================================

-- Function to generate IDN for a quote
-- Parameters: seller_company_id UUID, customer_inn VARCHAR
-- Returns: VARCHAR - the generated IDN
CREATE OR REPLACE FUNCTION generate_quote_idn(
    p_seller_company_id UUID,
    p_customer_inn VARCHAR
) RETURNS VARCHAR AS $$
DECLARE
    v_seller_code VARCHAR(10);
    v_year INTEGER;
    v_counter_key TEXT;
    v_current_seq INTEGER;
    v_org_id UUID;
    v_counters JSONB;
BEGIN
    -- Get seller company code
    SELECT supplier_code, organization_id INTO v_seller_code, v_org_id
    FROM seller_companies
    WHERE id = p_seller_company_id;

    IF v_seller_code IS NULL THEN
        RAISE EXCEPTION 'Seller company not found: %', p_seller_company_id;
    END IF;

    -- Get current year
    v_year := EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER;

    -- Counter key: YEAR-INN
    v_counter_key := v_year::TEXT || '-' || p_customer_inn;

    -- Get or initialize counters from organization
    SELECT COALESCE(idn_counters, '{}'::JSONB) INTO v_counters
    FROM organizations
    WHERE id = v_org_id;

    -- Get current sequence for this key
    v_current_seq := COALESCE((v_counters->>v_counter_key)::INTEGER, 0) + 1;

    -- Update counter in organization
    UPDATE organizations
    SET idn_counters = v_counters || jsonb_build_object(v_counter_key, v_current_seq)
    WHERE id = v_org_id;

    -- Return formatted IDN
    RETURN v_seller_code || '-' || p_customer_inn || '-' || v_year::TEXT || '-' || v_current_seq::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_quote_idn(UUID, VARCHAR) IS 'Generates a unique IDN for a quote in format SELLER-INN-YEAR-SEQ. Uses idn_counters JSONB in organizations table.';

-- =============================================================================
-- ENSURE ORGANIZATIONS TABLE HAS IDN_COUNTERS COLUMN
-- =============================================================================

-- Add idn_counters column to organizations if not exists
ALTER TABLE organizations
ADD COLUMN IF NOT EXISTS idn_counters JSONB DEFAULT '{}'::JSONB;

COMMENT ON COLUMN organizations.idn_counters IS 'JSONB storing IDN counters by year-inn key. Format: {"2025-1234567890": 5, ...}';

-- =============================================================================
-- TRIGGER TO AUTO-GENERATE IDN ON FIRST FINALIZATION
-- =============================================================================

-- Function to auto-generate IDN when quote transitions from draft
CREATE OR REPLACE FUNCTION auto_generate_quote_idn()
RETURNS TRIGGER AS $$
BEGIN
    -- Only generate IDN if:
    -- 1. IDN is currently NULL
    -- 2. seller_company_id is set
    -- 3. Quote has a customer with INN
    IF NEW.idn IS NULL AND NEW.seller_company_id IS NOT NULL THEN
        DECLARE
            v_customer_inn VARCHAR;
        BEGIN
            -- Get customer INN from related customer
            SELECT c.inn INTO v_customer_inn
            FROM customers c
            WHERE c.id = NEW.customer_id;

            -- Only generate if customer has INN
            IF v_customer_inn IS NOT NULL AND v_customer_inn != '' THEN
                NEW.idn := generate_quote_idn(NEW.seller_company_id, v_customer_inn);
            END IF;
        END;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (drop first if exists to allow re-running migration)
DROP TRIGGER IF EXISTS trg_auto_generate_quote_idn ON quotes;

CREATE TRIGGER trg_auto_generate_quote_idn
BEFORE INSERT OR UPDATE ON quotes
FOR EACH ROW
EXECUTE FUNCTION auto_generate_quote_idn();

COMMENT ON TRIGGER trg_auto_generate_quote_idn ON quotes IS 'Auto-generates IDN when seller_company_id is set and customer has INN';

-- =============================================================================
-- UPDATE TABLE COMMENT
-- =============================================================================

COMMENT ON TABLE quotes IS 'Commercial proposals (КП) with multi-role workflow support. Extended with IDN system, seller company reference, workflow_status, deal_type, role assignments, and completion timestamps. v3.0 adds supply chain entity references.';
