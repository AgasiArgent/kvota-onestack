-- ===========================================================================
-- Migration 106: Create supplier_invoices table in kvota schema
-- ===========================================================================
-- Description: Registry of invoices from suppliers for tracking purchasing and payments
-- Prerequisites: Migration 101 must be applied (tables moved to kvota schema)
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- SUPPLIER INVOICES TABLE
-- ============================================
-- Registry of invoices received from suppliers
-- Linked to suppliers and quote_items
-- Status tracking: pending → partially_paid → paid (or overdue/cancelled)

CREATE TABLE IF NOT EXISTS kvota.supplier_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Supplier reference
    supplier_id UUID NOT NULL REFERENCES kvota.suppliers(id) ON DELETE RESTRICT,

    -- Invoice details
    invoice_number VARCHAR(100) NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE,  -- Payment due date

    -- Financial info
    total_amount DECIMAL(15,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,

    -- Additional info
    notes TEXT,

    -- File attachments (Supabase storage URLs)
    invoice_file_url TEXT,  -- Scanned invoice document

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),

    -- Constraints
    CONSTRAINT supplier_invoices_status_check CHECK (
        status IN ('pending', 'partially_paid', 'paid', 'overdue', 'cancelled')
    ),
    CONSTRAINT supplier_invoices_amount_positive CHECK (total_amount > 0),
    CONSTRAINT supplier_invoices_currency_format CHECK (currency ~ '^[A-Z]{3}$'),
    CONSTRAINT supplier_invoices_due_date_check CHECK (
        due_date IS NULL OR due_date >= invoice_date
    )
);

-- Unique constraint: one invoice number per supplier per organization
CREATE UNIQUE INDEX IF NOT EXISTS idx_supplier_invoices_unique_number
ON kvota.supplier_invoices(organization_id, supplier_id, invoice_number);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_supplier_invoices_organization
ON kvota.supplier_invoices(organization_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_supplier
ON kvota.supplier_invoices(supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_status
ON kvota.supplier_invoices(organization_id, status);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_date
ON kvota.supplier_invoices(organization_id, invoice_date DESC);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_due_date
ON kvota.supplier_invoices(organization_id, due_date) WHERE due_date IS NOT NULL AND status NOT IN ('paid', 'cancelled');

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_overdue
ON kvota.supplier_invoices(organization_id, status, due_date)
WHERE status IN ('pending', 'partially_paid');

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE kvota.supplier_invoices ENABLE ROW LEVEL SECURITY;

-- Users can view invoices in their organization
CREATE POLICY supplier_invoices_select_policy ON kvota.supplier_invoices
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
        )
    );

-- Users with appropriate roles can insert invoices
CREATE POLICY supplier_invoices_insert_policy ON kvota.supplier_invoices
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

-- Users with appropriate roles can update invoices
CREATE POLICY supplier_invoices_update_policy ON kvota.supplier_invoices
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

-- Only admin can delete invoices
CREATE POLICY supplier_invoices_delete_policy ON kvota.supplier_invoices
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug = 'admin'
        )
    );

-- ============================================
-- TRIGGER FOR updated_at
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_supplier_invoices_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoices_update_timestamp ON kvota.supplier_invoices;
CREATE TRIGGER supplier_invoices_update_timestamp
    BEFORE UPDATE ON kvota.supplier_invoices
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_supplier_invoices_timestamp();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE kvota.supplier_invoices IS 'Registry of invoices from suppliers for tracking payments (v3.0)';
COMMENT ON COLUMN kvota.supplier_invoices.invoice_number IS 'Invoice number as provided by supplier';
COMMENT ON COLUMN kvota.supplier_invoices.due_date IS 'Payment due date - NULL means no specific due date';
COMMENT ON COLUMN kvota.supplier_invoices.total_amount IS 'Total invoice amount in specified currency';
COMMENT ON COLUMN kvota.supplier_invoices.status IS 'Invoice status: pending, partially_paid, paid, overdue, cancelled';
COMMENT ON COLUMN kvota.supplier_invoices.invoice_file_url IS 'URL to scanned invoice document in Supabase storage';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 106: supplier_invoices table created successfully in kvota schema';
END $$;
