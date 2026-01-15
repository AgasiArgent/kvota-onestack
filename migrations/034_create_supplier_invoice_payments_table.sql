-- Migration: 034_create_supplier_invoice_payments_table.sql
-- Description: Create supplier_invoice_payments table for tracking payments
-- Feature: DB-017 - Track payments with payment_type, buyer_company_id
-- Created: 2026-01-15

-- ============================================
-- Table: supplier_invoice_payments
-- ============================================
-- Tracks payments made against supplier invoices
-- Links payments to buyer_company (our legal entity that made the payment)
-- Supports multiple payment types: advance, partial, final, refund

CREATE TABLE IF NOT EXISTS supplier_invoice_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES supplier_invoices(id) ON DELETE CASCADE,

    -- Payment details
    payment_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    exchange_rate DECIMAL(10, 4),  -- Exchange rate to RUB at payment date

    -- Payment type: advance, partial, final, refund
    payment_type VARCHAR(20) NOT NULL DEFAULT 'advance',

    -- Which of our legal entities made the payment
    buyer_company_id UUID REFERENCES buyer_companies(id),

    -- Payment document reference (e.g., bank transfer number)
    payment_document VARCHAR(100),

    -- Notes about the payment
    notes TEXT,

    -- Audit fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),

    -- Constraints
    CONSTRAINT chk_payment_type CHECK (payment_type IN ('advance', 'partial', 'final', 'refund')),
    CONSTRAINT chk_payment_amount_positive CHECK (amount > 0),
    CONSTRAINT chk_exchange_rate_positive CHECK (exchange_rate IS NULL OR exchange_rate > 0)
);

-- ============================================
-- Indexes
-- ============================================

-- Find payments by invoice
CREATE INDEX IF NOT EXISTS idx_invoice_payments_invoice_id
ON supplier_invoice_payments(invoice_id);

-- Find payments by date range
CREATE INDEX IF NOT EXISTS idx_invoice_payments_date
ON supplier_invoice_payments(payment_date);

-- Find payments by buyer company
CREATE INDEX IF NOT EXISTS idx_invoice_payments_buyer_company
ON supplier_invoice_payments(buyer_company_id) WHERE buyer_company_id IS NOT NULL;

-- Find payments by type
CREATE INDEX IF NOT EXISTS idx_invoice_payments_type
ON supplier_invoice_payments(payment_type);

-- ============================================
-- Row Level Security
-- ============================================

ALTER TABLE supplier_invoice_payments ENABLE ROW LEVEL SECURITY;

-- RLS policies inherit from parent invoice organization
-- Users can access payments if they can access the parent invoice

CREATE POLICY "Users can view payments for invoices in their organization"
ON supplier_invoice_payments FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM supplier_invoices si
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND si.organization_id = auth.jwt() ->> 'organization_id'::text
    )
);

CREATE POLICY "Authorized roles can insert payments"
ON supplier_invoice_payments FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM supplier_invoices si
        JOIN user_roles ur ON ur.user_id = auth.uid()
        JOIN roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND si.organization_id = ur.organization_id
        AND r.code IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

CREATE POLICY "Authorized roles can update payments"
ON supplier_invoice_payments FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM supplier_invoices si
        JOIN user_roles ur ON ur.user_id = auth.uid()
        JOIN roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND si.organization_id = ur.organization_id
        AND r.code IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

CREATE POLICY "Admins can delete payments"
ON supplier_invoice_payments FOR DELETE
USING (
    EXISTS (
        SELECT 1 FROM supplier_invoices si
        JOIN user_roles ur ON ur.user_id = auth.uid()
        JOIN roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND si.organization_id = ur.organization_id
        AND r.code IN ('admin', 'finance')
    )
);

-- ============================================
-- Trigger: Auto-update invoice status on payment
-- ============================================

CREATE OR REPLACE FUNCTION update_invoice_status_on_payment()
RETURNS TRIGGER AS $$
DECLARE
    v_invoice_total DECIMAL(15, 2);
    v_paid_total DECIMAL(15, 2);
    v_new_status VARCHAR(20);
    v_due_date DATE;
BEGIN
    -- Get invoice details
    SELECT total_amount, due_date
    INTO v_invoice_total, v_due_date
    FROM supplier_invoices
    WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    -- Calculate total paid (exclude refunds from sum, they subtract)
    SELECT COALESCE(
        SUM(CASE WHEN payment_type = 'refund' THEN -amount ELSE amount END),
        0
    )
    INTO v_paid_total
    FROM supplier_invoice_payments
    WHERE invoice_id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    -- Determine new status
    IF v_paid_total >= v_invoice_total THEN
        v_new_status := 'paid';
    ELSIF v_paid_total > 0 THEN
        v_new_status := 'partially_paid';
    ELSIF v_due_date IS NOT NULL AND v_due_date < CURRENT_DATE THEN
        v_new_status := 'overdue';
    ELSE
        v_new_status := 'pending';
    END IF;

    -- Update invoice status
    UPDATE supplier_invoices
    SET status = v_new_status,
        updated_at = NOW()
    WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_invoice_status_on_payment
AFTER INSERT OR UPDATE OR DELETE ON supplier_invoice_payments
FOR EACH ROW
EXECUTE FUNCTION update_invoice_status_on_payment();

-- ============================================
-- Trigger: Auto-set updated_at
-- ============================================

CREATE TRIGGER trg_supplier_invoice_payments_updated_at
BEFORE UPDATE ON supplier_invoice_payments
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Helper Functions
-- ============================================

-- Get payment summary for an invoice
CREATE OR REPLACE FUNCTION get_invoice_payments_summary(p_invoice_id UUID)
RETURNS TABLE (
    invoice_id UUID,
    total_paid DECIMAL(15, 2),
    total_refunded DECIMAL(15, 2),
    net_paid DECIMAL(15, 2),
    payment_count INTEGER,
    last_payment_date DATE,
    advance_amount DECIMAL(15, 2),
    partial_amount DECIMAL(15, 2),
    final_amount DECIMAL(15, 2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_invoice_id AS invoice_id,
        COALESCE(SUM(CASE WHEN p.payment_type != 'refund' THEN p.amount ELSE 0 END), 0) AS total_paid,
        COALESCE(SUM(CASE WHEN p.payment_type = 'refund' THEN p.amount ELSE 0 END), 0) AS total_refunded,
        COALESCE(SUM(CASE WHEN p.payment_type = 'refund' THEN -p.amount ELSE p.amount END), 0) AS net_paid,
        COUNT(*)::INTEGER AS payment_count,
        MAX(p.payment_date) AS last_payment_date,
        COALESCE(SUM(CASE WHEN p.payment_type = 'advance' THEN p.amount ELSE 0 END), 0) AS advance_amount,
        COALESCE(SUM(CASE WHEN p.payment_type = 'partial' THEN p.amount ELSE 0 END), 0) AS partial_amount,
        COALESCE(SUM(CASE WHEN p.payment_type = 'final' THEN p.amount ELSE 0 END), 0) AS final_amount
    FROM supplier_invoice_payments p
    WHERE p.invoice_id = p_invoice_id;
END;
$$ LANGUAGE plpgsql;

-- Get all payments for an invoice with buyer company details
CREATE OR REPLACE FUNCTION get_payments_for_invoice(p_invoice_id UUID)
RETURNS TABLE (
    payment_id UUID,
    payment_date DATE,
    amount DECIMAL(15, 2),
    currency VARCHAR(3),
    exchange_rate DECIMAL(10, 4),
    amount_rub DECIMAL(15, 2),
    payment_type VARCHAR(20),
    buyer_company_id UUID,
    buyer_company_name VARCHAR(255),
    buyer_company_code VARCHAR(3),
    payment_document VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ,
    created_by UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.id AS payment_id,
        p.payment_date,
        p.amount,
        p.currency,
        p.exchange_rate,
        CASE WHEN p.exchange_rate IS NOT NULL
             THEN p.amount * p.exchange_rate
             ELSE NULL
        END AS amount_rub,
        p.payment_type,
        p.buyer_company_id,
        bc.name AS buyer_company_name,
        bc.company_code AS buyer_company_code,
        p.payment_document,
        p.notes,
        p.created_at,
        p.created_by
    FROM supplier_invoice_payments p
    LEFT JOIN buyer_companies bc ON bc.id = p.buyer_company_id
    WHERE p.invoice_id = p_invoice_id
    ORDER BY p.payment_date DESC, p.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Get payments summary by buyer company
CREATE OR REPLACE FUNCTION get_payments_by_buyer_company(
    p_organization_id UUID,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL
)
RETURNS TABLE (
    buyer_company_id UUID,
    buyer_company_name VARCHAR(255),
    buyer_company_code VARCHAR(3),
    total_amount DECIMAL(15, 2),
    payment_count INTEGER,
    currency VARCHAR(3)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.buyer_company_id,
        bc.name AS buyer_company_name,
        bc.company_code AS buyer_company_code,
        SUM(p.amount) AS total_amount,
        COUNT(*)::INTEGER AS payment_count,
        p.currency
    FROM supplier_invoice_payments p
    JOIN supplier_invoices si ON si.id = p.invoice_id
    LEFT JOIN buyer_companies bc ON bc.id = p.buyer_company_id
    WHERE si.organization_id = p_organization_id
    AND (p_from_date IS NULL OR p.payment_date >= p_from_date)
    AND (p_to_date IS NULL OR p.payment_date <= p_to_date)
    GROUP BY p.buyer_company_id, bc.name, bc.company_code, p.currency
    ORDER BY SUM(p.amount) DESC;
END;
$$ LANGUAGE plpgsql;

-- Get supplier payment summary
CREATE OR REPLACE FUNCTION get_supplier_payment_summary(
    p_supplier_id UUID,
    p_from_date DATE DEFAULT NULL,
    p_to_date DATE DEFAULT NULL
)
RETURNS TABLE (
    supplier_id UUID,
    total_invoiced DECIMAL(15, 2),
    total_paid DECIMAL(15, 2),
    total_refunded DECIMAL(15, 2),
    net_paid DECIMAL(15, 2),
    outstanding DECIMAL(15, 2),
    invoice_count INTEGER,
    payment_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p_supplier_id AS supplier_id,
        COALESCE(SUM(si.total_amount), 0) AS total_invoiced,
        COALESCE(SUM(CASE WHEN p.payment_type != 'refund' THEN p.amount ELSE 0 END), 0) AS total_paid,
        COALESCE(SUM(CASE WHEN p.payment_type = 'refund' THEN p.amount ELSE 0 END), 0) AS total_refunded,
        COALESCE(SUM(CASE WHEN p.payment_type = 'refund' THEN -p.amount ELSE p.amount END), 0) AS net_paid,
        COALESCE(SUM(si.total_amount), 0) -
            COALESCE(SUM(CASE WHEN p.payment_type = 'refund' THEN -p.amount ELSE p.amount END), 0) AS outstanding,
        COUNT(DISTINCT si.id)::INTEGER AS invoice_count,
        COUNT(p.id)::INTEGER AS payment_count
    FROM supplier_invoices si
    LEFT JOIN supplier_invoice_payments p ON p.invoice_id = si.id
        AND (p_from_date IS NULL OR p.payment_date >= p_from_date)
        AND (p_to_date IS NULL OR p.payment_date <= p_to_date)
    WHERE si.supplier_id = p_supplier_id
    AND si.status != 'cancelled';
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- View: Full payment details with context
-- ============================================

CREATE OR REPLACE VIEW v_supplier_invoice_payments_full AS
SELECT
    p.id AS payment_id,
    p.invoice_id,
    si.invoice_number,
    si.supplier_id,
    s.name AS supplier_name,
    s.supplier_code,
    si.organization_id,

    -- Payment details
    p.payment_date,
    p.amount,
    p.currency,
    p.exchange_rate,
    CASE WHEN p.exchange_rate IS NOT NULL
         THEN ROUND(p.amount * p.exchange_rate, 2)
         ELSE NULL
    END AS amount_rub,
    p.payment_type,

    -- Buyer company (who paid)
    p.buyer_company_id,
    bc.name AS buyer_company_name,
    bc.company_code AS buyer_company_code,

    -- Document and notes
    p.payment_document,
    p.notes,

    -- Invoice context
    si.total_amount AS invoice_total,
    si.status AS invoice_status,

    -- Audit
    p.created_at,
    p.created_by,
    u.email AS created_by_email
FROM supplier_invoice_payments p
JOIN supplier_invoices si ON si.id = p.invoice_id
JOIN suppliers s ON s.id = si.supplier_id
LEFT JOIN buyer_companies bc ON bc.id = p.buyer_company_id
LEFT JOIN auth.users u ON u.id = p.created_by;

-- ============================================
-- Comments
-- ============================================

COMMENT ON TABLE supplier_invoice_payments IS
'Payments made against supplier invoices. Tracks amount, date, payment type, and which buyer company made the payment.';

COMMENT ON COLUMN supplier_invoice_payments.payment_type IS
'Type of payment: advance (before delivery), partial (during), final (completion), refund (return)';

COMMENT ON COLUMN supplier_invoice_payments.buyer_company_id IS
'Our legal entity that made the payment. Important for financial accounting.';

COMMENT ON COLUMN supplier_invoice_payments.exchange_rate IS
'Exchange rate to RUB at the time of payment. Used for financial reporting.';

COMMENT ON FUNCTION get_invoice_payments_summary IS
'Returns aggregated payment statistics for an invoice including totals by payment type';

COMMENT ON FUNCTION get_payments_for_invoice IS
'Returns all payments for an invoice with buyer company details';

COMMENT ON FUNCTION get_payments_by_buyer_company IS
'Returns payment aggregates grouped by buyer company for a date range';

COMMENT ON FUNCTION get_supplier_payment_summary IS
'Returns invoice and payment summary for a supplier';

-- ============================================
-- Grant permissions
-- ============================================

-- Enable RLS bypass for service role
GRANT ALL ON supplier_invoice_payments TO service_role;
GRANT SELECT ON v_supplier_invoice_payments_full TO authenticated;
