-- ===========================================================================
-- Migration 174: Add contract_type and end_date to customer_contracts
-- ===========================================================================
-- Description: Add contract type (one_time / renewable) and end_date fields
--              to customer_contracts table for better contract classification
-- Created: 2026-02-12
-- ===========================================================================

-- Add contract_type column with CHECK constraint
ALTER TABLE kvota.customer_contracts
    ADD COLUMN IF NOT EXISTS contract_type TEXT
    CHECK (contract_type IN ('one_time', 'renewable'));

-- Add end_date column
ALTER TABLE kvota.customer_contracts
    ADD COLUMN IF NOT EXISTS end_date DATE;

-- Index for expiry queries (find contracts expiring soon)
CREATE INDEX IF NOT EXISTS idx_customer_contracts_end_date
    ON kvota.customer_contracts(organization_id, end_date)
    WHERE end_date IS NOT NULL;
