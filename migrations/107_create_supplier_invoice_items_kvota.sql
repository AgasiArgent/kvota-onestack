-- ===========================================================================
-- Migration 107: Create supplier_invoice_items table in kvota schema
-- ===========================================================================
-- Description: Link invoice items to quote_items - tracks what was invoiced per item
-- Prerequisites: Migration 106 must be applied (supplier_invoices created)
-- Created: 2026-01-20
-- ===========================================================================

-- ============================================
-- SUPPLIER INVOICE ITEMS TABLE
-- ============================================
-- Each invoice can contain multiple items from different quotes
-- Links invoice positions to quote_items for traceability
-- Allows partial invoicing (quantity can differ from quote_item quantity)

CREATE TABLE IF NOT EXISTS kvota.supplier_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent invoice
    invoice_id UUID NOT NULL REFERENCES kvota.supplier_invoices(id) ON DELETE CASCADE,

    -- Link to quote item (optional - some invoices may be for non-quote purchases)
    quote_item_id UUID REFERENCES kvota.quote_items(id) ON DELETE SET NULL,

    -- Item details
    description TEXT,  -- Description if no quote_item link or different from quote

    -- Quantities and pricing
    quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
    unit_price DECIMAL(15,4) NOT NULL,  -- Price per unit in invoice currency
    total_price DECIMAL(15,2) NOT NULL,  -- Total = quantity * unit_price (calculated)

    -- Unit of measure (if different from quote_item)
    unit VARCHAR(20),

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT supplier_invoice_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT supplier_invoice_items_unit_price_positive CHECK (unit_price >= 0),
    CONSTRAINT supplier_invoice_items_total_price_positive CHECK (total_price >= 0)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_supplier_invoice_items_invoice
ON kvota.supplier_invoice_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoice_items_quote_item
ON kvota.supplier_invoice_items(quote_item_id)
WHERE quote_item_id IS NOT NULL;

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================
-- Inherits access from parent invoice

ALTER TABLE kvota.supplier_invoice_items ENABLE ROW LEVEL SECURITY;

-- Users can view items if they can view the parent invoice
CREATE POLICY supplier_invoice_items_select_policy ON kvota.supplier_invoice_items
    FOR SELECT
    USING (
        invoice_id IN (
            SELECT id FROM kvota.supplier_invoices
            WHERE organization_id IN (
                SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
            )
        )
    );

-- Users with appropriate roles can insert items
CREATE POLICY supplier_invoice_items_insert_policy ON kvota.supplier_invoice_items
    FOR INSERT
    WITH CHECK (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

-- Users with appropriate roles can update items
CREATE POLICY supplier_invoice_items_update_policy ON kvota.supplier_invoice_items
    FOR UPDATE
    USING (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

-- Delete allowed for users with appropriate roles
CREATE POLICY supplier_invoice_items_delete_policy ON kvota.supplier_invoice_items
    FOR DELETE
    USING (
        invoice_id IN (
            SELECT si.id FROM kvota.supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.slug IN ('admin', 'procurement', 'quote_controller')
            )
        )
    );

-- ============================================
-- TRIGGER: Auto-calculate total_price
-- ============================================

CREATE OR REPLACE FUNCTION kvota.calculate_invoice_item_total()
RETURNS TRIGGER AS $$
BEGIN
    -- Auto-calculate total_price from quantity and unit_price
    NEW.total_price := ROUND((NEW.quantity * NEW.unit_price)::NUMERIC, 2);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoice_items_calc_total ON kvota.supplier_invoice_items;
CREATE TRIGGER supplier_invoice_items_calc_total
    BEFORE INSERT OR UPDATE OF quantity, unit_price ON kvota.supplier_invoice_items
    FOR EACH ROW
    EXECUTE FUNCTION kvota.calculate_invoice_item_total();

-- ============================================
-- TRIGGER: Update invoice total when items change
-- ============================================

CREATE OR REPLACE FUNCTION kvota.update_invoice_total_from_items()
RETURNS TRIGGER AS $$
DECLARE
    v_invoice_id UUID;
    v_new_total DECIMAL(15,2);
BEGIN
    -- Determine which invoice to update
    IF TG_OP = 'DELETE' THEN
        v_invoice_id := OLD.invoice_id;
    ELSE
        v_invoice_id := NEW.invoice_id;
    END IF;

    -- Calculate new total from all items
    SELECT COALESCE(SUM(total_price), 0)
    INTO v_new_total
    FROM kvota.supplier_invoice_items
    WHERE invoice_id = v_invoice_id;

    -- Update the parent invoice total
    UPDATE kvota.supplier_invoices
    SET total_amount = v_new_total,
        updated_at = NOW()
    WHERE id = v_invoice_id;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoice_items_update_total ON kvota.supplier_invoice_items;
CREATE TRIGGER supplier_invoice_items_update_total
    AFTER INSERT OR UPDATE OF total_price OR DELETE ON kvota.supplier_invoice_items
    FOR EACH ROW
    EXECUTE FUNCTION kvota.update_invoice_total_from_items();

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE kvota.supplier_invoice_items IS 'Invoice line items linked to quote_items for traceability (v3.0)';
COMMENT ON COLUMN kvota.supplier_invoice_items.quote_item_id IS 'Link to quote item - NULL for non-quote purchases';
COMMENT ON COLUMN kvota.supplier_invoice_items.description IS 'Item description - used when no quote_item or differs from quote';
COMMENT ON COLUMN kvota.supplier_invoice_items.total_price IS 'Auto-calculated: quantity * unit_price';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 107: supplier_invoice_items table created successfully in kvota schema';
    RAISE NOTICE 'Created triggers: calculate_invoice_item_total, update_invoice_total_from_items';
END $$;
