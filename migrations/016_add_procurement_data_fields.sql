-- Migration 016: Add procurement data fields to quote_items
-- Feature #35: Форма ввода закупочных данных
-- Date: 2025-01-15
-- Description: Add fields for procurement managers to enter supplier details

-- =============================================================================
-- ADD NEW COLUMNS TO QUOTE_ITEMS TABLE
-- =============================================================================

-- Supplier city (город поставщика)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_city VARCHAR(255);

-- Production lead time in days (срок производства)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS production_time_days INTEGER DEFAULT 0;

-- Supplier payment terms (условия оплаты поставщику)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_payment_terms TEXT;

-- Our payer company for this item (наша компания-плательщик)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS payer_company VARCHAR(255);

-- Advance percentage to supplier for this item (% аванса поставщику)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS advance_to_supplier_percent DECIMAL(5, 2) DEFAULT 100;

-- Procurement notes (notes from procurement manager)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_notes TEXT;

-- =============================================================================
-- ADD CONSTRAINTS
-- =============================================================================

-- Check constraint for advance percentage (0-100)
ALTER TABLE quote_items
ADD CONSTRAINT quote_items_advance_supplier_check
CHECK (advance_to_supplier_percent >= 0 AND advance_to_supplier_percent <= 100);

-- =============================================================================
-- ADD COLUMN COMMENTS
-- =============================================================================

COMMENT ON COLUMN quote_items.supplier_city IS 'City where the supplier is located';
COMMENT ON COLUMN quote_items.production_time_days IS 'Production lead time in days';
COMMENT ON COLUMN quote_items.supplier_payment_terms IS 'Payment terms with the supplier (e.g., "30% advance, 70% before shipment")';
COMMENT ON COLUMN quote_items.payer_company IS 'Our legal entity that will pay the supplier';
COMMENT ON COLUMN quote_items.advance_to_supplier_percent IS 'Percentage of advance payment to supplier (0-100)';
COMMENT ON COLUMN quote_items.procurement_notes IS 'Notes from procurement manager about this item';

-- =============================================================================
-- CREATE INDEXES
-- =============================================================================

-- No additional indexes needed for these fields (they're not used for filtering)

-- =============================================================================
-- Grant permissions (RLS is already enabled on quote_items)
-- =============================================================================
-- No additional permissions needed - existing RLS policies handle access
