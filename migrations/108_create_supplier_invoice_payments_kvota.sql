-- ===========================================================================
-- Migration 108: Create supplier_invoice_payments table in kvota schema
-- ===========================================================================
-- Description: Track payments made against supplier invoices
-- Prerequisites: Migration 106 must be applied (supplier_invoices created)
--                Migration 102 must be applied (buyer_companies created)
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- Table: supplier_invoice_payments
-- ============================================
-- Tracks payments made against supplier invoices
-- Links payments to buyer_company (our legal entity that made the payment)
-- Supports multiple payment types: advance, partial, final, refund

CREATE TABLE IF NOT EXISTS kvota.supplier_invoice_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES kvota.supplier_invoices(id) ON DELETE CASCADE,

    -- Payment details
    payment_date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    exchange_rate DECIMAL(10, 4),  -- Exchange rate to RUB at payment date

    -- Payment type: advance, partial, final, refund
    payment_type VARCHAR(20) NOT NULL DEFAULT 'advance',

    -- Which of our legal entities made the payment
    buyer_company_id UUID REFERENCES kvota.buyer_companies(id),

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
ON kvota.supplier_invoice_payments(invoice_id);

-- Find payments by date range
CREATE INDEX IF NOT EXISTS idx_invoice_payments_date
ON kvota.supplier_invoice_payments(payment_date);

-- Find payments by buyer company
CREATE INDEX IF NOT EXISTS idx_invoice_payments_buyer_company
ON kvota.supplier_invoice_payments(buyer_company_id) WHERE buyer_company_id IS NOT NULL;

-- Find payments by type
CREATE INDEX IF NOT EXISTS idx_invoice_payments_type
ON kvota.supplier_invoice_payments(payment_type);

-- ============================================
-- Row Level Security
-- ============================================

ALTER TABLE kvota.supplier_invoice_payments ENABLE ROW LEVEL SECURITY;

-- SELECT: Users can view payments for invoices in their organization
CREATE POLICY "Users can view payments for invoices in their organization"
ON kvota.supplier_invoice_payments FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.organization_id = si.organization_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND ur.user_id = auth.uid()
    )
);

-- INSERT: Authorized roles can insert payments
CREATE POLICY "Authorized roles can insert payments"
ON kvota.supplier_invoice_payments FOR INSERT
WITH CHECK (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.code IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

-- UPDATE: Authorized roles can update payments
CREATE POLICY "Authorized roles can update payments"
ON kvota.supplier_invoice_payments FOR UPDATE
USING (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.code IN ('procurement', 'finance', 'admin', 'head_of_procurement')
    )
);

-- DELETE: Admins can delete payments
CREATE POLICY "Admins can delete payments"
ON kvota.supplier_invoice_payments FOR DELETE
USING (
    EXISTS (
        SELECT 1 FROM kvota.supplier_invoices si
        JOIN kvota.user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = si.organization_id
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE si.id = supplier_invoice_payments.invoice_id
        AND r.code IN ('admin', 'finance')
    )
);

-- ============================================
-- Trigger: Auto-update invoice status on payment
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_invoice_status_on_payment()
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
    FROM kvota.supplier_invoices
    WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    -- Calculate total paid (exclude refunds from sum, they subtract)
    SELECT COALESCE(
        SUM(CASE WHEN payment_type = 'refund' THEN -amount ELSE amount END),
        0
    )
    INTO v_paid_total
    FROM kvota.supplier_invoice_payments
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
    UPDATE kvota.supplier_invoices
    SET status = v_new_status,
        updated_at = NOW()
    WHERE id = COALESCE(NEW.invoice_id, OLD.invoice_id);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_invoice_status_on_payment
AFTER INSERT OR UPDATE OR DELETE ON kvota.supplier_invoice_payments
FOR EACH ROW
EXECUTE FUNCTION kvota.update_invoice_status_on_payment();

-- ============================================
-- Trigger: Auto-set updated_at
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_supplier_invoice_payments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_supplier_invoice_payments_updated_at
BEFORE UPDATE ON kvota.supplier_invoice_payments
FOR EACH ROW
EXECUTE FUNCTION kvota.update_supplier_invoice_payments_updated_at();

-- ============================================
-- Comments
-- ============================================

COMMENT ON TABLE kvota.supplier_invoice_payments IS
'Payments made against supplier invoices. Tracks amount, date, payment type, and which buyer company made the payment.';

COMMENT ON COLUMN kvota.supplier_invoice_payments.payment_type IS
'Type of payment: advance (before delivery), partial (during), final (completion), refund (return)';

COMMENT ON COLUMN kvota.supplier_invoice_payments.buyer_company_id IS
'Our legal entity that made the payment. Important for financial accounting.';

COMMENT ON COLUMN kvota.supplier_invoice_payments.exchange_rate IS
'Exchange rate to RUB at the time of payment. Used for financial reporting.';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 108: supplier_invoice_payments table created successfully in kvota schema';
    RAISE NOTICE 'Created triggers: update_invoice_status_on_payment, update_supplier_invoice_payments_updated_at';
END $$;
