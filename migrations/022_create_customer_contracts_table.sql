-- ===========================================================================
-- Migration 022: Create customer_contracts table
-- ===========================================================================
-- Description: Supply contracts with customers
--              Includes next_specification_number counter for spec generation
-- Level: CUSTOMER (multiple contracts per customer)
-- Created: 2026-01-15
-- ===========================================================================

-- ===========================================================================
-- CREATE CUSTOMER_CONTRACTS TABLE
-- ===========================================================================

CREATE TABLE IF NOT EXISTS customer_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Contract identification
    contract_number TEXT NOT NULL,           -- Номер договора поставки
    contract_date DATE NOT NULL,             -- Дата договора

    -- Contract status
    status TEXT DEFAULT 'active'             -- active, suspended, terminated
        CHECK (status IN ('active', 'suspended', 'terminated')),

    -- Specification numbering counter
    -- Increments each time a new specification is created for this contract
    -- Format: Спецификация №1 к Договору №XXX от DD.MM.YYYY
    next_specification_number INTEGER DEFAULT 1,

    -- Additional info
    notes TEXT,                              -- Free-form notes

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ===========================================================================
-- INDEXES
-- ===========================================================================

-- Primary lookup: contracts by customer
CREATE INDEX IF NOT EXISTS idx_customer_contracts_customer_id
    ON customer_contracts(customer_id);

-- Organization isolation
CREATE INDEX IF NOT EXISTS idx_customer_contracts_organization_id
    ON customer_contracts(organization_id);

-- Find active contracts for a customer
CREATE INDEX IF NOT EXISTS idx_customer_contracts_customer_status
    ON customer_contracts(customer_id, status);

-- Contract number lookup within organization
CREATE INDEX IF NOT EXISTS idx_customer_contracts_org_number
    ON customer_contracts(organization_id, contract_number);

-- ===========================================================================
-- UNIQUE CONSTRAINT
-- ===========================================================================

-- Contract number should be unique within organization
ALTER TABLE customer_contracts
    ADD CONSTRAINT uq_customer_contracts_org_number
    UNIQUE (organization_id, contract_number);

-- ===========================================================================
-- TRIGGER FOR AUTOMATIC UPDATED_AT
-- ===========================================================================

CREATE OR REPLACE FUNCTION update_customer_contracts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_customer_contracts_updated_at
    BEFORE UPDATE ON customer_contracts
    FOR EACH ROW
    EXECUTE FUNCTION update_customer_contracts_updated_at();

-- ===========================================================================
-- FUNCTION TO GET NEXT SPECIFICATION NUMBER
-- ===========================================================================

-- Atomically increments and returns the next specification number for a contract
CREATE OR REPLACE FUNCTION get_next_specification_number(p_contract_id UUID)
RETURNS INTEGER AS $$
DECLARE
    v_next_number INTEGER;
BEGIN
    -- Atomically increment and return
    UPDATE customer_contracts
    SET next_specification_number = next_specification_number + 1,
        updated_at = NOW()
    WHERE id = p_contract_id
    RETURNING next_specification_number - 1 INTO v_next_number;

    -- Return the number BEFORE increment (what we just used)
    IF v_next_number IS NULL THEN
        RAISE EXCEPTION 'Contract not found: %', p_contract_id;
    END IF;

    RETURN v_next_number;
END;
$$ LANGUAGE plpgsql;

-- ===========================================================================
-- ROW LEVEL SECURITY
-- ===========================================================================

ALTER TABLE customer_contracts ENABLE ROW LEVEL SECURITY;

-- SELECT: Users can view contracts for customers in their organization
CREATE POLICY "customer_contracts_select_policy" ON customer_contracts
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM organization_members om
            WHERE om.organization_id = customer_contracts.organization_id
            AND om.user_id = auth.uid()
        )
    );

-- INSERT: Sales managers, spec controllers, and admins can create contracts
CREATE POLICY "customer_contracts_insert_policy" ON customer_contracts
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM organization_members om
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = om.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE om.organization_id = customer_contracts.organization_id
            AND om.user_id = auth.uid()
            AND r.code IN ('sales', 'spec_controller', 'admin')
        )
    );

-- UPDATE: Sales managers, spec controllers, and admins can update contracts
CREATE POLICY "customer_contracts_update_policy" ON customer_contracts
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM organization_members om
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = om.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE om.organization_id = customer_contracts.organization_id
            AND om.user_id = auth.uid()
            AND r.code IN ('sales', 'spec_controller', 'admin')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM organization_members om
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = om.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE om.organization_id = customer_contracts.organization_id
            AND om.user_id = auth.uid()
            AND r.code IN ('sales', 'spec_controller', 'admin')
        )
    );

-- DELETE: Only admins can delete contracts
CREATE POLICY "customer_contracts_delete_policy" ON customer_contracts
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM organization_members om
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = om.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE om.organization_id = customer_contracts.organization_id
            AND om.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

-- ===========================================================================
-- COMMENTS
-- ===========================================================================

COMMENT ON TABLE customer_contracts IS 'Supply contracts with customers for specification generation (v3.0)';
COMMENT ON COLUMN customer_contracts.organization_id IS 'Organization that owns this contract';
COMMENT ON COLUMN customer_contracts.customer_id IS 'Reference to customer company';
COMMENT ON COLUMN customer_contracts.contract_number IS 'Contract number (unique within organization)';
COMMENT ON COLUMN customer_contracts.contract_date IS 'Date when contract was signed';
COMMENT ON COLUMN customer_contracts.status IS 'Contract status: active, suspended, or terminated';
COMMENT ON COLUMN customer_contracts.next_specification_number IS 'Counter for generating sequential specification numbers';
COMMENT ON COLUMN customer_contracts.notes IS 'Free-form notes about the contract';
COMMENT ON FUNCTION get_next_specification_number(UUID) IS 'Atomically increments and returns next specification number for a contract';

-- ===========================================================================
-- DONE
-- ===========================================================================
