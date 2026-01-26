-- Migration 134: Fix get_quote_invoicing_summary function
-- Problem: Function uses INNER JOIN with products table, but:
--   1. products table doesn't exist in kvota schema
--   2. quote_items.product_id is rarely set (items use free text product_name)
--   3. Column names were wrong (unit_price, purchase_price don't exist)
-- Solution: Remove products join, use only quote_items columns

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
        COALESCE(qi.product_name, 'Без названия')::TEXT AS product_name,
        qi.quantity::DECIMAL(10,2) AS quote_quantity,
        COALESCE(qi.purchase_price_original, qi.base_price_vat, 0)::DECIMAL(15,4) AS quote_unit_price,
        COALESCE(SUM(sii.quantity), 0)::DECIMAL(10,2) AS invoiced_quantity,
        COALESCE(SUM(sii.total_price), 0)::DECIMAL(15,2) AS invoiced_amount,
        COUNT(DISTINCT sii.invoice_id)::INTEGER AS invoice_count,
        (COALESCE(SUM(sii.quantity), 0) >= qi.quantity)::BOOLEAN AS is_fully_invoiced
    FROM kvota.quote_items qi
    LEFT JOIN kvota.supplier_invoice_items sii ON sii.quote_item_id = qi.id
    LEFT JOIN kvota.supplier_invoices si ON sii.invoice_id = si.id AND si.status NOT IN ('cancelled')
    WHERE qi.quote_id = p_quote_id
    GROUP BY qi.id, qi.product_name, qi.quantity, qi.purchase_price_original, qi.base_price_vat
    ORDER BY qi.created_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permission
GRANT EXECUTE ON FUNCTION kvota.get_quote_invoicing_summary(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION kvota.get_quote_invoicing_summary(UUID) TO service_role;

COMMENT ON FUNCTION kvota.get_quote_invoicing_summary(UUID) IS
'Get invoicing status for all items in a quote. Returns items with their invoice data.';
