-- Migration 134: Fix get_quote_invoicing_summary function
-- Problem: Function uses INNER JOIN with products table, but quote_items.product_id is rarely set
-- Solution: Use LEFT JOIN and fallback to quote_items.product_name

-- Drop and recreate the function with fix
CREATE OR REPLACE FUNCTION kvota.get_quote_invoicing_summary(p_quote_id UUID)
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
        -- Use product_name from quote_items directly, fallback to products table if linked
        COALESCE(qi.product_name, p.name, 'Unknown') AS product_name,
        qi.quantity AS quote_quantity,
        COALESCE(qi.purchase_price, qi.unit_price, 0)::DECIMAL(15,4) AS quote_unit_price,
        COALESCE(SUM(sii.quantity), 0::DECIMAL) AS invoiced_quantity,
        COALESCE(SUM(sii.total_price), 0::DECIMAL) AS invoiced_amount,
        COUNT(DISTINCT sii.invoice_id)::INTEGER AS invoice_count,
        COALESCE(SUM(sii.quantity), 0) >= qi.quantity AS is_fully_invoiced
    FROM kvota.quote_items qi
    LEFT JOIN kvota.products p ON qi.product_id = p.id  -- Changed to LEFT JOIN
    LEFT JOIN kvota.supplier_invoice_items sii ON sii.quote_item_id = qi.id
    LEFT JOIN kvota.supplier_invoices si ON sii.invoice_id = si.id AND si.status NOT IN ('cancelled')
    WHERE qi.quote_id = p_quote_id
    GROUP BY qi.id, qi.product_name, p.name, qi.quantity, qi.purchase_price, qi.unit_price
    ORDER BY qi.created_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION kvota.get_quote_invoicing_summary(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION kvota.get_quote_invoicing_summary(UUID) TO service_role;

COMMENT ON FUNCTION kvota.get_quote_invoicing_summary(UUID) IS 
'Get invoicing status for all items in a quote. Fixed to use LEFT JOIN with products table.';
