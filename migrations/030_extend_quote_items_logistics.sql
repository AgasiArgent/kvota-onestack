-- Migration: Extend quote_items table with logistics fields
-- Feature #DB-013: Add logistics cost segmentation and timing
-- Description: Multi-segment logistics costs (supplier→hub→customs→customer) and total delivery time
-- Created: 2026-01-15
-- Version: 3.0

-- =============================================================================
-- ADD LOGISTICS COLUMNS TO QUOTE_ITEMS TABLE
-- =============================================================================

-- Logistics: Supplier to Hub cost
-- Cost of transportation from supplier's location to the logistics hub (e.g., warehouse in China)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS logistics_supplier_to_hub DECIMAL(15,2);

COMMENT ON COLUMN quote_items.logistics_supplier_to_hub IS 'Transportation cost from supplier location to logistics hub (in base currency)';

-- Logistics: Hub to Customs cost
-- Cost of main transportation leg from hub to customs clearance point
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS logistics_hub_to_customs DECIMAL(15,2);

COMMENT ON COLUMN quote_items.logistics_hub_to_customs IS 'Transportation cost from logistics hub to customs clearance point (in base currency)';

-- Logistics: Customs to Customer cost
-- Cost of final delivery from customs to customer warehouse
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS logistics_customs_to_customer DECIMAL(15,2);

COMMENT ON COLUMN quote_items.logistics_customs_to_customer IS 'Transportation cost from customs to customer warehouse (in base currency)';

-- Logistics: Total Days
-- Total delivery time including all logistics segments
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS logistics_total_days INTEGER;

COMMENT ON COLUMN quote_items.logistics_total_days IS 'Total logistics time in days (all segments combined)';

-- =============================================================================
-- ADD CHECK CONSTRAINTS
-- =============================================================================

-- Logistics costs must be non-negative
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_logistics_supplier_to_hub_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_logistics_supplier_to_hub_check
CHECK (logistics_supplier_to_hub IS NULL OR logistics_supplier_to_hub >= 0);

ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_logistics_hub_to_customs_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_logistics_hub_to_customs_check
CHECK (logistics_hub_to_customs IS NULL OR logistics_hub_to_customs >= 0);

ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_logistics_customs_to_customer_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_logistics_customs_to_customer_check
CHECK (logistics_customs_to_customer IS NULL OR logistics_customs_to_customer >= 0);

-- Logistics total days must be positive
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_logistics_total_days_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_logistics_total_days_check
CHECK (logistics_total_days IS NULL OR logistics_total_days > 0);

-- =============================================================================
-- HELPER FUNCTION: Calculate Total Logistics Cost
-- =============================================================================

-- Function to calculate total logistics cost for an item
CREATE OR REPLACE FUNCTION get_item_logistics_total(p_item_id UUID)
RETURNS DECIMAL(15,2) AS $$
DECLARE
    v_total DECIMAL(15,2);
BEGIN
    SELECT
        COALESCE(logistics_supplier_to_hub, 0) +
        COALESCE(logistics_hub_to_customs, 0) +
        COALESCE(logistics_customs_to_customer, 0)
    INTO v_total
    FROM quote_items
    WHERE id = p_item_id;

    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_item_logistics_total(UUID) IS 'Calculates total logistics cost for a quote item (sum of all segments)';

-- =============================================================================
-- HELPER FUNCTION: Get Logistics Summary for Quote
-- =============================================================================

-- Function to get logistics summary for entire quote
CREATE OR REPLACE FUNCTION get_quote_logistics_summary(p_quote_id UUID)
RETURNS TABLE (
    total_items INTEGER,
    items_with_logistics INTEGER,
    logistics_supplier_to_hub_total DECIMAL(15,2),
    logistics_hub_to_customs_total DECIMAL(15,2),
    logistics_customs_to_customer_total DECIMAL(15,2),
    logistics_grand_total DECIMAL(15,2),
    avg_logistics_days INTEGER,
    max_logistics_days INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total_items,
        COUNT(CASE
            WHEN logistics_supplier_to_hub IS NOT NULL
              OR logistics_hub_to_customs IS NOT NULL
              OR logistics_customs_to_customer IS NOT NULL
            THEN 1
        END)::INTEGER AS items_with_logistics,
        COALESCE(SUM(logistics_supplier_to_hub), 0)::DECIMAL(15,2) AS logistics_supplier_to_hub_total,
        COALESCE(SUM(logistics_hub_to_customs), 0)::DECIMAL(15,2) AS logistics_hub_to_customs_total,
        COALESCE(SUM(logistics_customs_to_customer), 0)::DECIMAL(15,2) AS logistics_customs_to_customer_total,
        COALESCE(SUM(
            COALESCE(logistics_supplier_to_hub, 0) +
            COALESCE(logistics_hub_to_customs, 0) +
            COALESCE(logistics_customs_to_customer, 0)
        ), 0)::DECIMAL(15,2) AS logistics_grand_total,
        COALESCE(AVG(logistics_total_days)::INTEGER, 0) AS avg_logistics_days,
        COALESCE(MAX(logistics_total_days), 0)::INTEGER AS max_logistics_days
    FROM quote_items
    WHERE quote_id = p_quote_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_quote_logistics_summary(UUID) IS 'Returns aggregated logistics costs and times for all items in a quote';

-- =============================================================================
-- HELPER FUNCTION: Check Logistics Completion Status
-- =============================================================================

-- Function to check if logistics is complete for all items in a quote
CREATE OR REPLACE FUNCTION is_quote_logistics_complete(p_quote_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_incomplete_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_incomplete_count
    FROM quote_items
    WHERE quote_id = p_quote_id
      AND (
          logistics_supplier_to_hub IS NULL
          OR logistics_hub_to_customs IS NULL
          OR logistics_customs_to_customer IS NULL
          OR logistics_total_days IS NULL
      );

    RETURN v_incomplete_count = 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION is_quote_logistics_complete(UUID) IS 'Returns TRUE if all items in quote have complete logistics data';

-- =============================================================================
-- VIEW: Quote Items with Logistics Data
-- =============================================================================

-- Create or replace view for logistics workspace
CREATE OR REPLACE VIEW v_quote_items_logistics AS
SELECT
    qi.id AS item_id,
    qi.quote_id,
    q.idn AS quote_idn,
    qi.item_idn,
    qi.position,
    -- Product info
    qi.product_name,
    qi.brand,
    qi.quantity,
    -- Physical dimensions (for logistics calculation)
    qi.weight_kg,
    qi.volume_m3,
    -- Pickup location
    qi.pickup_location_id,
    l.country AS pickup_country,
    l.city AS pickup_city,
    -- Logistics costs
    qi.logistics_supplier_to_hub,
    qi.logistics_hub_to_customs,
    qi.logistics_customs_to_customer,
    COALESCE(qi.logistics_supplier_to_hub, 0) +
    COALESCE(qi.logistics_hub_to_customs, 0) +
    COALESCE(qi.logistics_customs_to_customer, 0) AS logistics_total_cost,
    qi.logistics_total_days,
    -- Completion status
    CASE
        WHEN qi.logistics_supplier_to_hub IS NOT NULL
         AND qi.logistics_hub_to_customs IS NOT NULL
         AND qi.logistics_customs_to_customer IS NOT NULL
         AND qi.logistics_total_days IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END AS logistics_complete,
    -- Quote context
    q.workflow_status,
    q.customer_id,
    c.name AS customer_name,
    q.organization_id
FROM quote_items qi
JOIN quotes q ON q.id = qi.quote_id
LEFT JOIN locations l ON l.id = qi.pickup_location_id
LEFT JOIN customers c ON c.id = q.customer_id;

COMMENT ON VIEW v_quote_items_logistics IS 'View of quote items with logistics data for logistics workspace';

-- Grant permissions
GRANT SELECT ON v_quote_items_logistics TO authenticated;
GRANT EXECUTE ON FUNCTION get_item_logistics_total(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_quote_logistics_summary(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION is_quote_logistics_complete(UUID) TO authenticated;

-- =============================================================================
-- UPDATE TABLE COMMENT
-- =============================================================================

COMMENT ON TABLE quote_items IS 'Quote line items with v3.0 extensions: supply chain (supplier_id, buyer_company_id, pickup_location_id), procurement fields, item IDN, and multi-segment logistics costs (supplier→hub→customs→customer).';
