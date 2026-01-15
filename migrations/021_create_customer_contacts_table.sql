-- ===========================================================================
-- Migration 021: Create customer_contacts table
-- ===========================================================================
-- Description: Contact persons for customers (ЛПР - Decision Makers)
--              Includes is_signatory flag for specification PDF signatory selection
-- Level: CUSTOMER (multiple contacts per customer)
-- Created: 2026-01-15
-- Feature: DB-004
-- ===========================================================================

-- Create customer_contacts table
CREATE TABLE IF NOT EXISTS customer_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,

    -- Contact information
    name VARCHAR(255) NOT NULL,
    position VARCHAR(255),  -- e.g., "Директор", "Главный инженер", "Менеджер по закупкам"
    email VARCHAR(255),
    phone VARCHAR(50),

    -- Specification signatory flag
    -- When is_signatory = true, this contact's name appears on specification PDF
    is_signatory BOOLEAN DEFAULT FALSE,

    -- Primary contact flag (for general communication)
    is_primary BOOLEAN DEFAULT FALSE,

    -- Additional info
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_customer_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER customer_contacts_updated_at_trigger
    BEFORE UPDATE ON customer_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_customer_contacts_updated_at();

-- ===========================================================================
-- Indexes
-- ===========================================================================

-- Primary lookup: all contacts for a customer
CREATE INDEX IF NOT EXISTS idx_customer_contacts_customer_id
    ON customer_contacts(customer_id);

-- Find signatory for specification generation
CREATE INDEX IF NOT EXISTS idx_customer_contacts_signatory
    ON customer_contacts(customer_id, is_signatory)
    WHERE is_signatory = TRUE;

-- Find primary contacts
CREATE INDEX IF NOT EXISTS idx_customer_contacts_primary
    ON customer_contacts(customer_id, is_primary)
    WHERE is_primary = TRUE;

-- ===========================================================================
-- Row Level Security (RLS)
-- ===========================================================================

ALTER TABLE customer_contacts ENABLE ROW LEVEL SECURITY;

-- SELECT: Users can view contacts for customers in their organization
CREATE POLICY "customer_contacts_select_policy" ON customer_contacts
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM customers c
            JOIN organization_members om ON om.organization_id = c.organization_id
            WHERE c.id = customer_contacts.customer_id
            AND om.user_id = auth.uid()
        )
    );

-- INSERT: Sales, admin can create contacts
CREATE POLICY "customer_contacts_insert_policy" ON customer_contacts
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM customers c
            JOIN organization_members om ON om.organization_id = c.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = c.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE c.id = customer_contacts.customer_id
            AND r.code IN ('admin', 'sales')
        )
    );

-- UPDATE: Sales, admin can update contacts
CREATE POLICY "customer_contacts_update_policy" ON customer_contacts
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM customers c
            JOIN organization_members om ON om.organization_id = c.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = c.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE c.id = customer_contacts.customer_id
            AND r.code IN ('admin', 'sales')
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM customers c
            JOIN organization_members om ON om.organization_id = c.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = c.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE c.id = customer_contacts.customer_id
            AND r.code IN ('admin', 'sales')
        )
    );

-- DELETE: Only admin can delete contacts
CREATE POLICY "customer_contacts_delete_policy" ON customer_contacts
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM customers c
            JOIN organization_members om ON om.organization_id = c.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = c.organization_id
            JOIN roles r ON ur.role_id = r.id
            WHERE c.id = customer_contacts.customer_id
            AND r.code = 'admin'
        )
    );

-- ===========================================================================
-- Comments
-- ===========================================================================

COMMENT ON TABLE customer_contacts IS 'Contact persons (ЛПР) for customers with signatory selection for specifications';
COMMENT ON COLUMN customer_contacts.customer_id IS 'Reference to parent customer';
COMMENT ON COLUMN customer_contacts.name IS 'Full name of contact person';
COMMENT ON COLUMN customer_contacts.position IS 'Job position/title (e.g., Директор, Главный инженер)';
COMMENT ON COLUMN customer_contacts.email IS 'Contact email address';
COMMENT ON COLUMN customer_contacts.phone IS 'Contact phone number';
COMMENT ON COLUMN customer_contacts.is_signatory IS 'If TRUE, this contact appears as signatory on specification PDFs';
COMMENT ON COLUMN customer_contacts.is_primary IS 'If TRUE, this is the main contact for general communication';
COMMENT ON COLUMN customer_contacts.notes IS 'Additional notes about this contact';

-- ===========================================================================
-- Helper function: Get signatory for a customer
-- ===========================================================================

CREATE OR REPLACE FUNCTION get_customer_signatory(p_customer_id UUID)
RETURNS TABLE (
    contact_id UUID,
    contact_name VARCHAR,
    contact_position VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cc.id,
        cc.name,
        cc.position
    FROM customer_contacts cc
    WHERE cc.customer_id = p_customer_id
    AND cc.is_signatory = TRUE
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION get_customer_signatory(UUID) IS 'Returns the signatory contact for a customer (used in specification PDF generation)';

-- ===========================================================================
-- End of Migration 021
-- ===========================================================================
