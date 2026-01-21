-- Migration 123: Create invoices table for procurement workflow
-- Feature: Invoice-based procurement grouping
-- Date: 2026-01-21
-- Description: Group quote items into invoices by supplier+buyer_company+pickup_location

-- =============================================================================
-- CREATE INVOICES TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,

    -- Grouping fields (unique combination per quote)
    supplier_id UUID REFERENCES kvota.suppliers(id) ON DELETE SET NULL,
    buyer_company_id UUID REFERENCES kvota.buyer_companies(id) ON DELETE SET NULL,
    pickup_location_id UUID,  -- References locations table (kept as UUID without FK for flexibility)

    -- Invoice details (filled by procurement manager)
    invoice_number VARCHAR(100) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    total_weight_kg DECIMAL(10,3) NOT NULL,
    total_volume_m3 DECIMAL(10,4),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one invoice per combination in a quote
    CONSTRAINT invoices_unique_combination
        UNIQUE(quote_id, supplier_id, buyer_company_id, pickup_location_id)
);

COMMENT ON TABLE kvota.invoices IS 'Invoices grouping quote items by supplier, buyer company, and pickup location for procurement workflow';
COMMENT ON COLUMN kvota.invoices.invoice_number IS 'Invoice number from supplier (e.g., INV-2024-001)';
COMMENT ON COLUMN kvota.invoices.currency IS 'Currency of all items in this invoice (ISO 4217: USD, EUR, RUB, etc.)';
COMMENT ON COLUMN kvota.invoices.total_weight_kg IS 'Total weight in kg for all items in this invoice';
COMMENT ON COLUMN kvota.invoices.total_volume_m3 IS 'Total volume in m³ for all items in this invoice (optional)';

-- =============================================================================
-- ADD INVOICE_ID TO QUOTE_ITEMS
-- =============================================================================

ALTER TABLE kvota.quote_items
ADD COLUMN IF NOT EXISTS invoice_id UUID REFERENCES kvota.invoices(id) ON DELETE SET NULL;

COMMENT ON COLUMN kvota.quote_items.invoice_id IS 'Invoice this item belongs to (grouped by supplier+buyer_company+pickup_location)';

-- =============================================================================
-- REMOVE OLD FIELDS FROM QUOTES TABLE
-- =============================================================================

-- These fields are no longer needed - weight/volume now tracked per invoice
ALTER TABLE kvota.quotes
DROP COLUMN IF EXISTS procurement_total_weight_kg;

ALTER TABLE kvota.quotes
DROP COLUMN IF EXISTS procurement_total_volume_m3;

-- =============================================================================
-- CREATE INDEXES
-- =============================================================================

-- Index for finding invoices by quote
CREATE INDEX IF NOT EXISTS idx_invoices_quote_id
ON kvota.invoices(quote_id);

-- Index for finding invoices by supplier
CREATE INDEX IF NOT EXISTS idx_invoices_supplier_id
ON kvota.invoices(supplier_id)
WHERE supplier_id IS NOT NULL;

-- Index for finding quote items by invoice
CREATE INDEX IF NOT EXISTS idx_quote_items_invoice_id
ON kvota.quote_items(invoice_id)
WHERE invoice_id IS NOT NULL;

-- =============================================================================
-- ADD CHECK CONSTRAINTS
-- =============================================================================

-- Weight must be positive
ALTER TABLE kvota.invoices
DROP CONSTRAINT IF EXISTS invoices_weight_check;

ALTER TABLE kvota.invoices
ADD CONSTRAINT invoices_weight_check
CHECK (total_weight_kg > 0);

-- Volume must be positive if provided
ALTER TABLE kvota.invoices
DROP CONSTRAINT IF EXISTS invoices_volume_check;

ALTER TABLE kvota.invoices
ADD CONSTRAINT invoices_volume_check
CHECK (total_volume_m3 IS NULL OR total_volume_m3 > 0);

-- Currency must be 3 uppercase letters
ALTER TABLE kvota.invoices
DROP CONSTRAINT IF EXISTS invoices_currency_check;

ALTER TABLE kvota.invoices
ADD CONSTRAINT invoices_currency_check
CHECK (currency ~ '^[A-Z]{3}$');

-- Invoice number must not be empty
ALTER TABLE kvota.invoices
DROP CONSTRAINT IF EXISTS invoices_number_check;

ALTER TABLE kvota.invoices
ADD CONSTRAINT invoices_number_check
CHECK (LENGTH(TRIM(invoice_number)) > 0);
