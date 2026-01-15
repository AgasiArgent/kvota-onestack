-- Migration: Create supplier_invoices table
-- Feature: DB-015
-- Description: Registry of invoices from suppliers for tracking purchasing and payments
-- Part of v3.0: Supply chain management

-- ============================================
-- SUPPLIER INVOICES TABLE
-- ============================================
-- Registry of invoices received from suppliers
-- Linked to suppliers and quote_items
-- Status tracking: pending → partially_paid → paid (or overdue/cancelled)

CREATE TABLE IF NOT EXISTS supplier_invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Supplier reference
    supplier_id UUID NOT NULL REFERENCES suppliers(id) ON DELETE RESTRICT,

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
ON supplier_invoices(organization_id, supplier_id, invoice_number);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_supplier_invoices_organization
ON supplier_invoices(organization_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_supplier
ON supplier_invoices(supplier_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_status
ON supplier_invoices(organization_id, status);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_date
ON supplier_invoices(organization_id, invoice_date DESC);

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_due_date
ON supplier_invoices(organization_id, due_date) WHERE due_date IS NOT NULL AND status NOT IN ('paid', 'cancelled');

CREATE INDEX IF NOT EXISTS idx_supplier_invoices_overdue
ON supplier_invoices(organization_id, status, due_date)
WHERE status IN ('pending', 'partially_paid');

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE supplier_invoices ENABLE ROW LEVEL SECURITY;

-- Users can view invoices in their organization
CREATE POLICY supplier_invoices_select_policy ON supplier_invoices
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
        )
    );

-- Users with appropriate roles can insert invoices
-- procurement, quote_controller, finance, admin
CREATE POLICY supplier_invoices_insert_policy ON supplier_invoices
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

-- Users with appropriate roles can update invoices
CREATE POLICY supplier_invoices_update_policy ON supplier_invoices
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code IN ('admin', 'procurement', 'quote_controller', 'finance')
        )
    );

-- Only admin can delete invoices (soft delete preferred)
CREATE POLICY supplier_invoices_delete_policy ON supplier_invoices
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

-- ============================================
-- TRIGGER FOR updated_at
-- ============================================

CREATE OR REPLACE FUNCTION update_supplier_invoices_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoices_update_timestamp ON supplier_invoices;
CREATE TRIGGER supplier_invoices_update_timestamp
    BEFORE UPDATE ON supplier_invoices
    FOR EACH ROW
    EXECUTE FUNCTION update_supplier_invoices_timestamp();

-- ============================================
-- AUTO-UPDATE OVERDUE STATUS FUNCTION
-- ============================================
-- Scheduled job should call this to mark invoices as overdue

CREATE OR REPLACE FUNCTION update_overdue_supplier_invoices()
RETURNS INTEGER AS $$
DECLARE
    updated_count INTEGER;
BEGIN
    WITH updated AS (
        UPDATE supplier_invoices
        SET status = 'overdue',
            updated_at = NOW()
        WHERE status IN ('pending', 'partially_paid')
        AND due_date IS NOT NULL
        AND due_date < CURRENT_DATE
        RETURNING id
    )
    SELECT COUNT(*) INTO updated_count FROM updated;

    RETURN updated_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Get invoice payment summary
CREATE OR REPLACE FUNCTION get_invoice_payment_summary(p_invoice_id UUID)
RETURNS TABLE(
    total_amount DECIMAL(15,2),
    paid_amount DECIMAL(15,2),
    remaining_amount DECIMAL(15,2),
    payment_count INTEGER,
    is_fully_paid BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        si.total_amount,
        COALESCE(SUM(sip.amount), 0::DECIMAL) AS paid_amount,
        si.total_amount - COALESCE(SUM(sip.amount), 0::DECIMAL) AS remaining_amount,
        COUNT(sip.id)::INTEGER AS payment_count,
        COALESCE(SUM(sip.amount), 0) >= si.total_amount AS is_fully_paid
    FROM supplier_invoices si
    LEFT JOIN supplier_invoice_payments sip ON sip.invoice_id = si.id
    WHERE si.id = p_invoice_id
    GROUP BY si.id, si.total_amount;
END;
$$ LANGUAGE plpgsql;

-- Get supplier invoices summary for organization
CREATE OR REPLACE FUNCTION get_supplier_invoices_summary(p_org_id UUID)
RETURNS TABLE(
    status VARCHAR(20),
    invoice_count BIGINT,
    total_amount DECIMAL(15,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        si.status,
        COUNT(*) AS invoice_count,
        SUM(si.total_amount) AS total_amount
    FROM supplier_invoices si
    WHERE si.organization_id = p_org_id
    GROUP BY si.status
    ORDER BY
        CASE si.status
            WHEN 'overdue' THEN 1
            WHEN 'pending' THEN 2
            WHEN 'partially_paid' THEN 3
            WHEN 'paid' THEN 4
            WHEN 'cancelled' THEN 5
        END;
END;
$$ LANGUAGE plpgsql;

-- Get invoices for supplier with payment status
CREATE OR REPLACE FUNCTION get_invoices_for_supplier(p_supplier_id UUID)
RETURNS TABLE(
    id UUID,
    invoice_number VARCHAR(100),
    invoice_date DATE,
    due_date DATE,
    total_amount DECIMAL(15,2),
    paid_amount DECIMAL(15,2),
    status VARCHAR(20),
    is_overdue BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        si.id,
        si.invoice_number,
        si.invoice_date,
        si.due_date,
        si.total_amount,
        COALESCE(SUM(sip.amount), 0::DECIMAL) AS paid_amount,
        si.status,
        (si.due_date < CURRENT_DATE AND si.status IN ('pending', 'partially_paid')) AS is_overdue
    FROM supplier_invoices si
    LEFT JOIN supplier_invoice_payments sip ON sip.invoice_id = si.id
    WHERE si.supplier_id = p_supplier_id
    GROUP BY si.id
    ORDER BY si.invoice_date DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEW: Supplier invoices with payment info
-- ============================================

CREATE OR REPLACE VIEW v_supplier_invoices_with_payments AS
SELECT
    si.id,
    si.organization_id,
    si.supplier_id,
    s.name AS supplier_name,
    s.supplier_code,
    si.invoice_number,
    si.invoice_date,
    si.due_date,
    si.total_amount,
    si.currency,
    COALESCE(SUM(sip.amount), 0) AS paid_amount,
    si.total_amount - COALESCE(SUM(sip.amount), 0) AS remaining_amount,
    COUNT(sip.id) AS payment_count,
    si.status,
    CASE
        WHEN si.status IN ('paid', 'cancelled') THEN false
        WHEN si.due_date IS NOT NULL AND si.due_date < CURRENT_DATE THEN true
        ELSE false
    END AS is_overdue,
    CASE
        WHEN si.due_date IS NULL THEN NULL
        ELSE si.due_date - CURRENT_DATE
    END AS days_until_due,
    si.notes,
    si.invoice_file_url,
    si.created_at,
    si.updated_at,
    si.created_by
FROM supplier_invoices si
JOIN suppliers s ON si.supplier_id = s.id
LEFT JOIN supplier_invoice_payments sip ON sip.invoice_id = si.id
GROUP BY si.id, s.id;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE supplier_invoices IS 'Registry of invoices from suppliers for tracking payments (v3.0)';
COMMENT ON COLUMN supplier_invoices.invoice_number IS 'Invoice number as provided by supplier';
COMMENT ON COLUMN supplier_invoices.due_date IS 'Payment due date - NULL means no specific due date';
COMMENT ON COLUMN supplier_invoices.total_amount IS 'Total invoice amount in specified currency';
COMMENT ON COLUMN supplier_invoices.status IS 'Invoice status: pending, partially_paid, paid, overdue, cancelled';
COMMENT ON COLUMN supplier_invoices.invoice_file_url IS 'URL to scanned invoice document in Supabase storage';
COMMENT ON FUNCTION update_overdue_supplier_invoices() IS 'Call periodically to auto-mark invoices as overdue';
COMMENT ON FUNCTION get_invoice_payment_summary(UUID) IS 'Get payment status for specific invoice';
COMMENT ON FUNCTION get_supplier_invoices_summary(UUID) IS 'Get invoice counts and totals by status for organization';
COMMENT ON VIEW v_supplier_invoices_with_payments IS 'Invoices with aggregated payment information';
