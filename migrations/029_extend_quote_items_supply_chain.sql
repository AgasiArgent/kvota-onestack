-- Migration: Extend quote_items table with supply chain columns
-- Feature #DB-012: Add supplier_id, buyer_company_id, pickup_location_id, procurement fields
-- Description: Links quote items to supply chain entities at item level
-- Created: 2026-01-15
-- Version: 3.0

-- =============================================================================
-- ADD NEW COLUMNS TO QUOTE_ITEMS TABLE FOR V3.0 SUPPLY CHAIN
-- =============================================================================

-- Item IDN - Unique identification number for the item
-- Format: QUOTE_IDN-POSITION (e.g., CMT-1234567890-2025-1-001)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS item_idn VARCHAR(120);

COMMENT ON COLUMN quote_items.item_idn IS 'Item IDN in format QUOTE_IDN-POSITION (e.g., CMT-1234567890-2025-1-001)';

-- Supplier ID - Reference to external supplier (at ITEM level, can vary per item)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_id UUID;

COMMENT ON COLUMN quote_items.supplier_id IS 'Reference to suppliers table. External supplier for this item.';

-- Buyer Company ID - Our legal entity for purchasing this item
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS buyer_company_id UUID;

COMMENT ON COLUMN quote_items.buyer_company_id IS 'Reference to buyer_companies table. Our legal entity used for purchasing this item.';

-- Pickup Location ID - Location where goods will be picked up from supplier
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS pickup_location_id UUID;

COMMENT ON COLUMN quote_items.pickup_location_id IS 'Reference to locations table. Pickup location (country/city) from supplier.';

-- Supplier Payment Terms - Text description of payment terms with supplier
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_payment_terms TEXT;

COMMENT ON COLUMN quote_items.supplier_payment_terms IS 'Payment terms with supplier (e.g., "30% advance, 70% before shipment")';

-- Supplier Advance Percent - Percentage of advance payment to supplier
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_advance_percent DECIMAL(5,2);

COMMENT ON COLUMN quote_items.supplier_advance_percent IS 'Advance payment percentage to supplier (0-100)';

-- Production Time Days - Manufacturing/production time in days
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS production_time_days INTEGER;

COMMENT ON COLUMN quote_items.production_time_days IS 'Production/manufacturing time in days';

-- Weight KG - Item weight in kilograms
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS weight_kg DECIMAL(10,3);

COMMENT ON COLUMN quote_items.weight_kg IS 'Item weight in kilograms (precision to grams)';

-- Volume M3 - Item volume in cubic meters
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS volume_m3 DECIMAL(10,4);

COMMENT ON COLUMN quote_items.volume_m3 IS 'Item volume in cubic meters (precision to 0.0001 m³)';

-- =============================================================================
-- ADD FOREIGN KEY CONSTRAINTS
-- =============================================================================

-- Foreign key for supplier_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_supplier_id_fkey'
    ) THEN
        ALTER TABLE quote_items
        ADD CONSTRAINT quote_items_supplier_id_fkey
        FOREIGN KEY (supplier_id)
        REFERENCES suppliers(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'suppliers table not found, skipping FK constraint';
END $$;

-- Foreign key for buyer_company_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_buyer_company_id_fkey'
    ) THEN
        ALTER TABLE quote_items
        ADD CONSTRAINT quote_items_buyer_company_id_fkey
        FOREIGN KEY (buyer_company_id)
        REFERENCES buyer_companies(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'buyer_companies table not found, skipping FK constraint';
END $$;

-- Foreign key for pickup_location_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_pickup_location_id_fkey'
    ) THEN
        ALTER TABLE quote_items
        ADD CONSTRAINT quote_items_pickup_location_id_fkey
        FOREIGN KEY (pickup_location_id)
        REFERENCES locations(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'locations table not found, skipping FK constraint';
END $$;

-- =============================================================================
-- ADD INDEXES FOR QUERY PERFORMANCE
-- =============================================================================

-- Index on item_idn for quick lookups
CREATE INDEX IF NOT EXISTS idx_quote_items_item_idn
ON quote_items(item_idn)
WHERE item_idn IS NOT NULL;

-- Unique index on item_idn
CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_items_item_idn_unique
ON quote_items(item_idn)
WHERE item_idn IS NOT NULL;

-- Index on supplier_id for filtering items by supplier
CREATE INDEX IF NOT EXISTS idx_quote_items_supplier_id
ON quote_items(supplier_id)
WHERE supplier_id IS NOT NULL;

-- Index on buyer_company_id for filtering items by buyer company
CREATE INDEX IF NOT EXISTS idx_quote_items_buyer_company_id
ON quote_items(buyer_company_id)
WHERE buyer_company_id IS NOT NULL;

-- Index on pickup_location_id for filtering items by pickup location
CREATE INDEX IF NOT EXISTS idx_quote_items_pickup_location_id
ON quote_items(pickup_location_id)
WHERE pickup_location_id IS NOT NULL;

-- =============================================================================
-- ADD CHECK CONSTRAINTS
-- =============================================================================

-- Supplier advance percent must be between 0 and 100
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_supplier_advance_percent_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_supplier_advance_percent_check
CHECK (supplier_advance_percent IS NULL OR (supplier_advance_percent >= 0 AND supplier_advance_percent <= 100));

-- Production time must be positive
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_production_time_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_production_time_check
CHECK (production_time_days IS NULL OR production_time_days > 0);

-- Weight must be positive
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_weight_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_weight_check
CHECK (weight_kg IS NULL OR weight_kg > 0);

-- Volume must be positive
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_volume_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_volume_check
CHECK (volume_m3 IS NULL OR volume_m3 > 0);

-- =============================================================================
-- HELPER FUNCTION: Generate Item IDN
-- =============================================================================

-- Function to generate IDN for a quote item
-- Parameters: quote_id UUID, position INTEGER
-- Returns: VARCHAR - the generated item IDN
CREATE OR REPLACE FUNCTION generate_item_idn(
    p_quote_id UUID,
    p_position INTEGER
) RETURNS VARCHAR AS $$
DECLARE
    v_quote_idn VARCHAR;
BEGIN
    -- Get the parent quote's IDN
    SELECT idn INTO v_quote_idn
    FROM quotes
    WHERE id = p_quote_id;

    -- If quote doesn't have IDN yet, return NULL
    IF v_quote_idn IS NULL THEN
        RETURN NULL;
    END IF;

    -- Return formatted item IDN: QUOTE_IDN-POSITION (3-digit padded)
    RETURN v_quote_idn || '-' || LPAD(p_position::TEXT, 3, '0');
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION generate_item_idn(UUID, INTEGER) IS 'Generates item IDN in format QUOTE_IDN-POSITION (e.g., CMT-1234567890-2025-1-001)';

-- =============================================================================
-- TRIGGER: Auto-generate Item IDN
-- =============================================================================

-- Function to auto-generate item IDN when quote has IDN
CREATE OR REPLACE FUNCTION auto_generate_item_idn()
RETURNS TRIGGER AS $$
DECLARE
    v_position INTEGER;
    v_quote_idn VARCHAR;
BEGIN
    -- Skip if item already has IDN
    IF NEW.item_idn IS NOT NULL THEN
        RETURN NEW;
    END IF;

    -- Get quote IDN
    SELECT idn INTO v_quote_idn
    FROM quotes
    WHERE id = NEW.quote_id;

    -- Only generate if quote has IDN
    IF v_quote_idn IS NOT NULL THEN
        -- Get position (count of items + 1, or use existing position if available)
        IF NEW.position IS NOT NULL THEN
            v_position := NEW.position;
        ELSE
            SELECT COALESCE(MAX(position), 0) + 1 INTO v_position
            FROM quote_items
            WHERE quote_id = NEW.quote_id;
        END IF;

        NEW.item_idn := generate_item_idn(NEW.quote_id, v_position);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trg_auto_generate_item_idn ON quote_items;

CREATE TRIGGER trg_auto_generate_item_idn
BEFORE INSERT ON quote_items
FOR EACH ROW
EXECUTE FUNCTION auto_generate_item_idn();

COMMENT ON TRIGGER trg_auto_generate_item_idn ON quote_items IS 'Auto-generates item IDN when inserting item into a quote that has IDN';

-- =============================================================================
-- FUNCTION: Update Item IDNs for Quote
-- =============================================================================

-- Function to regenerate all item IDNs for a quote (useful when quote gets IDN)
CREATE OR REPLACE FUNCTION regenerate_item_idns_for_quote(p_quote_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_quote_idn VARCHAR;
    v_count INTEGER := 0;
BEGIN
    -- Get quote IDN
    SELECT idn INTO v_quote_idn
    FROM quotes
    WHERE id = p_quote_id;

    IF v_quote_idn IS NULL THEN
        RETURN 0;
    END IF;

    -- Update all items that don't have IDN
    UPDATE quote_items
    SET item_idn = v_quote_idn || '-' || LPAD(position::TEXT, 3, '0')
    WHERE quote_id = p_quote_id
      AND item_idn IS NULL
      AND position IS NOT NULL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION regenerate_item_idns_for_quote(UUID) IS 'Regenerates item IDNs for all items in a quote (call after quote gets IDN)';

-- =============================================================================
-- HELPER FUNCTION: Get Supply Chain Summary for Item
-- =============================================================================

CREATE OR REPLACE FUNCTION get_item_supply_chain_summary(p_item_id UUID)
RETURNS TABLE (
    item_idn VARCHAR,
    supplier_name VARCHAR,
    supplier_code VARCHAR,
    buyer_company_name VARCHAR,
    buyer_company_code VARCHAR,
    pickup_location VARCHAR,
    production_days INTEGER,
    weight DECIMAL,
    volume DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        qi.item_idn,
        s.name AS supplier_name,
        s.supplier_code,
        bc.name AS buyer_company_name,
        bc.company_code AS buyer_company_code,
        COALESCE(l.city || ', ' || l.country, NULL) AS pickup_location,
        qi.production_time_days AS production_days,
        qi.weight_kg AS weight,
        qi.volume_m3 AS volume
    FROM quote_items qi
    LEFT JOIN suppliers s ON s.id = qi.supplier_id
    LEFT JOIN buyer_companies bc ON bc.id = qi.buyer_company_id
    LEFT JOIN locations l ON l.id = qi.pickup_location_id
    WHERE qi.id = p_item_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_item_supply_chain_summary(UUID) IS 'Returns supply chain summary for a quote item including supplier, buyer company, and pickup location';

-- Grant execute permissions
GRANT EXECUTE ON FUNCTION generate_item_idn(UUID, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION regenerate_item_idns_for_quote(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_item_supply_chain_summary(UUID) TO authenticated;

-- =============================================================================
-- UPDATE TABLE COMMENT
-- =============================================================================

COMMENT ON TABLE quote_items IS 'Quote line items with v3.0 supply chain extensions: supplier_id, buyer_company_id, pickup_location_id, weight, volume, production time, and item IDN generation.';
