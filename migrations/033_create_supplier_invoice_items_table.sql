-- Migration: Create supplier_invoice_items table
-- Feature: DB-016
-- Description: Link invoice items to quote_items - tracks what was invoiced per item
-- Part of v3.0: Supply chain management

-- ============================================
-- SUPPLIER INVOICE ITEMS TABLE
-- ============================================
-- Each invoice can contain multiple items from different quotes
-- Links invoice positions to quote_items for traceability
-- Allows partial invoicing (quantity can differ from quote_item quantity)

CREATE TABLE IF NOT EXISTS supplier_invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent invoice
    invoice_id UUID NOT NULL REFERENCES supplier_invoices(id) ON DELETE CASCADE,

    -- Link to quote item (optional - some invoices may be for non-quote purchases)
    quote_item_id UUID REFERENCES quote_items(id) ON DELETE SET NULL,

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
ON supplier_invoice_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_supplier_invoice_items_quote_item
ON supplier_invoice_items(quote_item_id)
WHERE quote_item_id IS NOT NULL;

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================
-- Inherits access from parent invoice

ALTER TABLE supplier_invoice_items ENABLE ROW LEVEL SECURITY;

-- Users can view items if they can view the parent invoice
CREATE POLICY supplier_invoice_items_select_policy ON supplier_invoice_items
    FOR SELECT
    USING (
        invoice_id IN (
            SELECT id FROM supplier_invoices
            WHERE organization_id IN (
                SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
            )
        )
    );

-- Users with appropriate roles can insert items
CREATE POLICY supplier_invoice_items_insert_policy ON supplier_invoice_items
    FOR INSERT
    WITH CHECK (
        invoice_id IN (
            SELECT si.id FROM supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.code IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

-- Users with appropriate roles can update items
CREATE POLICY supplier_invoice_items_update_policy ON supplier_invoice_items
    FOR UPDATE
    USING (
        invoice_id IN (
            SELECT si.id FROM supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.code IN ('admin', 'procurement', 'quote_controller', 'finance')
            )
        )
    );

-- Delete allowed for users with appropriate roles
CREATE POLICY supplier_invoice_items_delete_policy ON supplier_invoice_items
    FOR DELETE
    USING (
        invoice_id IN (
            SELECT si.id FROM supplier_invoices si
            WHERE si.organization_id IN (
                SELECT ur.organization_id
                FROM user_roles ur
                JOIN roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND r.code IN ('admin', 'procurement', 'quote_controller')
            )
        )
    );

-- ============================================
-- TRIGGER: Auto-calculate total_price
-- ============================================

CREATE OR REPLACE FUNCTION calculate_invoice_item_total()
RETURNS TRIGGER AS $$
BEGIN
    -- Auto-calculate total_price from quantity and unit_price
    NEW.total_price := ROUND((NEW.quantity * NEW.unit_price)::NUMERIC, 2);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS supplier_invoice_items_calc_total ON supplier_invoice_items;
CREATE TRIGGER supplier_invoice_items_calc_total
    BEFORE INSERT OR UPDATE OF quantity, unit_price ON supplier_invoice_items
    FOR EACH ROW
    EXECUTE FUNCTION calculate_invoice_item_total();

-- ============================================
-- TRIGGER: Update invoice total when items change
-- ============================================

CREATE OR REPLACE FUNCTION update_invoice_total_from_items()
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
    FROM supplier_invoice_items
    WHERE invoice_id = v_invoice_id;

    -- Update the parent invoice total
    UPDATE supplier_invoices
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

DROP TRIGGER IF EXISTS supplier_invoice_items_update_total ON supplier_invoice_items;
CREATE TRIGGER supplier_invoice_items_update_total
    AFTER INSERT OR UPDATE OF total_price OR DELETE ON supplier_invoice_items
    FOR EACH ROW
    EXECUTE FUNCTION update_invoice_total_from_items();

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Get items for an invoice with quote details
CREATE OR REPLACE FUNCTION get_invoice_items_with_details(p_invoice_id UUID)
RETURNS TABLE(
    id UUID,
    quote_item_id UUID,
    product_name TEXT,
    product_sku TEXT,
    description TEXT,
    quantity DECIMAL(10,2),
    unit_price DECIMAL(15,4),
    total_price DECIMAL(15,2),
    unit VARCHAR(20),
    quote_idn VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sii.id,
        sii.quote_item_id,
        COALESCE(p.name, sii.description) AS product_name,
        p.sku AS product_sku,
        sii.description,
        sii.quantity,
        sii.unit_price,
        sii.total_price,
        COALESCE(sii.unit, p.unit) AS unit,
        q.idn AS quote_idn
    FROM supplier_invoice_items sii
    LEFT JOIN quote_items qi ON sii.quote_item_id = qi.id
    LEFT JOIN products p ON qi.product_id = p.id
    LEFT JOIN quotes q ON qi.quote_id = q.id
    WHERE sii.invoice_id = p_invoice_id
    ORDER BY sii.created_at;
END;
$$ LANGUAGE plpgsql;

-- Get all invoices for a quote item (to see invoicing history)
CREATE OR REPLACE FUNCTION get_invoices_for_quote_item(p_quote_item_id UUID)
RETURNS TABLE(
    invoice_id UUID,
    invoice_number VARCHAR(100),
    invoice_date DATE,
    supplier_name TEXT,
    quantity DECIMAL(10,2),
    unit_price DECIMAL(15,4),
    total_price DECIMAL(15,2),
    invoice_status VARCHAR(20)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        si.id AS invoice_id,
        si.invoice_number,
        si.invoice_date,
        s.name AS supplier_name,
        sii.quantity,
        sii.unit_price,
        sii.total_price,
        si.status AS invoice_status
    FROM supplier_invoice_items sii
    JOIN supplier_invoices si ON sii.invoice_id = si.id
    JOIN suppliers s ON si.supplier_id = s.id
    WHERE sii.quote_item_id = p_quote_item_id
    ORDER BY si.invoice_date DESC;
END;
$$ LANGUAGE plpgsql;

-- Calculate total invoiced amount for a quote item
CREATE OR REPLACE FUNCTION get_quote_item_invoiced_total(p_quote_item_id UUID)
RETURNS DECIMAL(15,2) AS $$
DECLARE
    v_total DECIMAL(15,2);
BEGIN
    SELECT COALESCE(SUM(sii.total_price), 0)
    INTO v_total
    FROM supplier_invoice_items sii
    JOIN supplier_invoices si ON sii.invoice_id = si.id
    WHERE sii.quote_item_id = p_quote_item_id
    AND si.status NOT IN ('cancelled');

    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- Get invoice items summary for a quote (all items in quote)
CREATE OR REPLACE FUNCTION get_quote_invoicing_summary(p_quote_id UUID)
RETURNS TABLE(
    quote_item_id UUID,
    product_name TEXT,
    quote_quantity DECIMAL(10,2),
    quote_unit_price DECIMAL(15,4),
    invoiced_quantity DECIMAL(10,2),
    invoiced_amount DECIMAL(15,2),
    invoice_count INTEGER,
    is_fully_invoiced BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        qi.id AS quote_item_id,
        p.name AS product_name,
        qi.quantity AS quote_quantity,
        qi.unit_price AS quote_unit_price,
        COALESCE(SUM(sii.quantity), 0::DECIMAL) AS invoiced_quantity,
        COALESCE(SUM(sii.total_price), 0::DECIMAL) AS invoiced_amount,
        COUNT(DISTINCT sii.invoice_id)::INTEGER AS invoice_count,
        COALESCE(SUM(sii.quantity), 0) >= qi.quantity AS is_fully_invoiced
    FROM quote_items qi
    JOIN products p ON qi.product_id = p.id
    LEFT JOIN supplier_invoice_items sii ON sii.quote_item_id = qi.id
    LEFT JOIN supplier_invoices si ON sii.invoice_id = si.id AND si.status NOT IN ('cancelled')
    WHERE qi.quote_id = p_quote_id
    GROUP BY qi.id, p.name, qi.quantity, qi.unit_price
    ORDER BY qi.created_at;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEW: Invoice items with full context
-- ============================================

CREATE OR REPLACE VIEW v_supplier_invoice_items_full AS
SELECT
    sii.id,
    sii.invoice_id,
    si.invoice_number,
    si.invoice_date,
    si.status AS invoice_status,
    si.supplier_id,
    s.name AS supplier_name,
    sii.quote_item_id,
    qi.quote_id,
    q.idn AS quote_idn,
    p.id AS product_id,
    p.name AS product_name,
    p.sku AS product_sku,
    sii.description,
    sii.quantity,
    sii.unit_price,
    sii.total_price,
    COALESCE(sii.unit, p.unit) AS unit,
    si.currency,
    si.organization_id,
    sii.created_at
FROM supplier_invoice_items sii
JOIN supplier_invoices si ON sii.invoice_id = si.id
JOIN suppliers s ON si.supplier_id = s.id
LEFT JOIN quote_items qi ON sii.quote_item_id = qi.id
LEFT JOIN quotes q ON qi.quote_id = q.id
LEFT JOIN products p ON qi.product_id = p.id;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE supplier_invoice_items IS 'Invoice line items linked to quote_items for traceability (v3.0)';
COMMENT ON COLUMN supplier_invoice_items.quote_item_id IS 'Link to quote item - NULL for non-quote purchases';
COMMENT ON COLUMN supplier_invoice_items.description IS 'Item description - used when no quote_item or differs from quote';
COMMENT ON COLUMN supplier_invoice_items.total_price IS 'Auto-calculated: quantity * unit_price';
COMMENT ON FUNCTION calculate_invoice_item_total() IS 'Auto-calculate total from quantity and unit_price';
COMMENT ON FUNCTION update_invoice_total_from_items() IS 'Keep parent invoice total in sync with items';
COMMENT ON FUNCTION get_invoice_items_with_details(UUID) IS 'Get invoice items with product and quote details';
COMMENT ON FUNCTION get_invoices_for_quote_item(UUID) IS 'See all invoices containing a specific quote item';
COMMENT ON FUNCTION get_quote_item_invoiced_total(UUID) IS 'Total amount invoiced for a quote item';
COMMENT ON FUNCTION get_quote_invoicing_summary(UUID) IS 'Invoicing status for all items in a quote';
COMMENT ON VIEW v_supplier_invoice_items_full IS 'Complete invoice item details with product and quote context';
