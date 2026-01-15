-- Migration: Extend quote_items table with customs fields
-- Feature #DB-014: Add customs duty and clearance fields
-- Description: HS code, customs duty percentage, and extra customs costs for quote items
-- Created: 2026-01-15
-- Version: 3.0

-- =============================================================================
-- ADD CUSTOMS COLUMNS TO QUOTE_ITEMS TABLE
-- =============================================================================

-- HS Code (Harmonized System code / ТН ВЭД код)
-- International standardized system of names and numbers to classify traded products
-- Format: typically 6-10 digits (e.g., 8482.10.10 for ball bearings)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS hs_code VARCHAR(20);

COMMENT ON COLUMN quote_items.hs_code IS 'Harmonized System code (ТН ВЭД) for customs classification. Format: XXXX.XX.XX';

-- Customs Duty Percentage
-- The percentage of import duty applied to the item based on HS code
-- Russian customs duties typically range from 0% to 20%
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_duty_percent DECIMAL(5,2);

COMMENT ON COLUMN quote_items.customs_duty_percent IS 'Customs duty rate as percentage (e.g., 5.00 for 5%). Depends on HS code classification.';

-- Customs Extra Cost
-- Additional customs-related expenses beyond duty (brokerage fees, storage, inspections)
ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_extra_cost DECIMAL(15,2);

COMMENT ON COLUMN quote_items.customs_extra_cost IS 'Additional customs costs beyond duty: brokerage fees, customs warehouse fees, inspections, certifications, etc.';

-- =============================================================================
-- ADD CHECK CONSTRAINTS
-- =============================================================================

-- HS code format validation (optional - can be digits with dots or just digits)
-- Common formats: 8482.10.10 or 8482101000
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_hs_code_format_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_hs_code_format_check
CHECK (hs_code IS NULL OR hs_code ~ '^[0-9]{4,10}(\.[0-9]{2,4})*$');

-- Customs duty percent must be between 0 and 100
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_customs_duty_percent_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_customs_duty_percent_check
CHECK (customs_duty_percent IS NULL OR (customs_duty_percent >= 0 AND customs_duty_percent <= 100));

-- Customs extra cost must be non-negative
ALTER TABLE quote_items
DROP CONSTRAINT IF EXISTS quote_items_customs_extra_cost_check;

ALTER TABLE quote_items
ADD CONSTRAINT quote_items_customs_extra_cost_check
CHECK (customs_extra_cost IS NULL OR customs_extra_cost >= 0);

-- =============================================================================
-- HELPER FUNCTION: Calculate Total Customs Cost
-- =============================================================================

-- Function to calculate total customs cost for an item
-- Uses purchase price * (duty_percent/100) + extra_cost
CREATE OR REPLACE FUNCTION get_item_customs_total(
    p_item_id UUID,
    p_use_rub_amount BOOLEAN DEFAULT TRUE
)
RETURNS DECIMAL(15,2) AS $$
DECLARE
    v_duty_base DECIMAL(15,2);
    v_duty_percent DECIMAL(5,2);
    v_extra_cost DECIMAL(15,2);
    v_duty_amount DECIMAL(15,2);
    v_total DECIMAL(15,2);
BEGIN
    -- Get item data
    SELECT
        CASE
            WHEN p_use_rub_amount THEN COALESCE(purchase_price_rub, 0)
            ELSE COALESCE(purchase_price_original, 0)
        END * COALESCE(quantity, 1),
        COALESCE(customs_duty_percent, 0),
        COALESCE(customs_extra_cost, 0)
    INTO v_duty_base, v_duty_percent, v_extra_cost
    FROM quote_items
    WHERE id = p_item_id;

    -- Calculate duty amount
    v_duty_amount := v_duty_base * (v_duty_percent / 100);

    -- Total = duty + extra costs
    v_total := v_duty_amount + v_extra_cost;

    RETURN ROUND(v_total, 2);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_item_customs_total(UUID, BOOLEAN) IS 'Calculates total customs cost for a quote item (duty based on purchase price + extra costs)';

-- =============================================================================
-- HELPER FUNCTION: Get Customs Summary for Quote
-- =============================================================================

-- Function to get customs summary for entire quote
CREATE OR REPLACE FUNCTION get_quote_customs_summary(p_quote_id UUID)
RETURNS TABLE (
    total_items INTEGER,
    items_with_customs INTEGER,
    items_with_hs_code INTEGER,
    avg_duty_percent DECIMAL(5,2),
    total_duty_amount DECIMAL(15,2),
    total_extra_costs DECIMAL(15,2),
    customs_grand_total DECIMAL(15,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total_items,
        COUNT(CASE
            WHEN customs_duty_percent IS NOT NULL OR customs_extra_cost IS NOT NULL
            THEN 1
        END)::INTEGER AS items_with_customs,
        COUNT(CASE WHEN hs_code IS NOT NULL THEN 1 END)::INTEGER AS items_with_hs_code,
        COALESCE(AVG(customs_duty_percent), 0)::DECIMAL(5,2) AS avg_duty_percent,
        COALESCE(SUM(
            COALESCE(purchase_price_rub, 0) * COALESCE(quantity, 1) * (COALESCE(customs_duty_percent, 0) / 100)
        ), 0)::DECIMAL(15,2) AS total_duty_amount,
        COALESCE(SUM(customs_extra_cost), 0)::DECIMAL(15,2) AS total_extra_costs,
        COALESCE(SUM(
            COALESCE(purchase_price_rub, 0) * COALESCE(quantity, 1) * (COALESCE(customs_duty_percent, 0) / 100)
            + COALESCE(customs_extra_cost, 0)
        ), 0)::DECIMAL(15,2) AS customs_grand_total
    FROM quote_items
    WHERE quote_id = p_quote_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_quote_customs_summary(UUID) IS 'Returns aggregated customs data for all items in a quote';

-- =============================================================================
-- HELPER FUNCTION: Check Customs Completion Status
-- =============================================================================

-- Function to check if customs data is complete for all items in a quote
CREATE OR REPLACE FUNCTION is_quote_customs_complete(p_quote_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_incomplete_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_incomplete_count
    FROM quote_items
    WHERE quote_id = p_quote_id
      AND (
          hs_code IS NULL
          OR customs_duty_percent IS NULL
          -- customs_extra_cost can be 0 or NULL, not required
      );

    RETURN v_incomplete_count = 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION is_quote_customs_complete(UUID) IS 'Returns TRUE if all items in quote have HS code and duty percent filled';

-- =============================================================================
-- HELPER FUNCTION: Get HS Code Statistics
-- =============================================================================

-- Function to get statistics on HS codes used (for reporting/analytics)
CREATE OR REPLACE FUNCTION get_hs_code_stats(p_organization_id UUID)
RETURNS TABLE (
    hs_code_prefix VARCHAR(4),
    usage_count BIGINT,
    avg_duty_percent DECIMAL(5,2),
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        LEFT(qi.hs_code, 4)::VARCHAR(4) AS hs_code_prefix,
        COUNT(*) AS usage_count,
        AVG(qi.customs_duty_percent)::DECIMAL(5,2) AS avg_duty_percent,
        CASE LEFT(qi.hs_code, 2)
            WHEN '84' THEN 'Nuclear reactors, boilers, machinery'
            WHEN '85' THEN 'Electrical machinery and equipment'
            WHEN '87' THEN 'Vehicles other than railway'
            WHEN '73' THEN 'Articles of iron or steel'
            WHEN '90' THEN 'Optical, photographic, measuring instruments'
            ELSE 'Other products'
        END AS description
    FROM quote_items qi
    JOIN quotes q ON q.id = qi.quote_id
    WHERE q.organization_id = p_organization_id
      AND qi.hs_code IS NOT NULL
    GROUP BY LEFT(qi.hs_code, 4), LEFT(qi.hs_code, 2)
    ORDER BY usage_count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_hs_code_stats(UUID) IS 'Returns statistics on HS code usage grouped by 4-digit prefix';

-- =============================================================================
-- VIEW: Quote Items with Customs Data
-- =============================================================================

-- Create or replace view for customs workspace
CREATE OR REPLACE VIEW v_quote_items_customs AS
SELECT
    qi.id AS item_id,
    qi.quote_id,
    q.idn AS quote_idn,
    qi.item_idn,
    qi.position,
    -- Product info
    qi.product_name,
    qi.part_number,
    qi.brand,
    qi.quantity,
    -- Pricing (for duty calculation)
    qi.purchase_price_rub,
    qi.purchase_price_original,
    (COALESCE(qi.purchase_price_rub, 0) * COALESCE(qi.quantity, 1)) AS total_purchase_value,
    -- Customs data
    qi.hs_code,
    qi.customs_duty_percent,
    qi.customs_extra_cost,
    -- Calculated customs amounts
    ROUND(COALESCE(qi.purchase_price_rub, 0) * COALESCE(qi.quantity, 1) * (COALESCE(qi.customs_duty_percent, 0) / 100), 2) AS calculated_duty,
    ROUND(
        COALESCE(qi.purchase_price_rub, 0) * COALESCE(qi.quantity, 1) * (COALESCE(qi.customs_duty_percent, 0) / 100)
        + COALESCE(qi.customs_extra_cost, 0),
    2) AS total_customs_cost,
    -- Completion status
    CASE
        WHEN qi.hs_code IS NOT NULL AND qi.customs_duty_percent IS NOT NULL
        THEN TRUE
        ELSE FALSE
    END AS customs_complete,
    -- Quote context
    q.workflow_status,
    q.customer_id,
    c.name AS customer_name,
    q.organization_id
FROM quote_items qi
JOIN quotes q ON q.id = qi.quote_id
LEFT JOIN customers c ON c.id = q.customer_id;

COMMENT ON VIEW v_quote_items_customs IS 'View of quote items with customs data for customs workspace';

-- Grant permissions
GRANT SELECT ON v_quote_items_customs TO authenticated;
GRANT EXECUTE ON FUNCTION get_item_customs_total(UUID, BOOLEAN) TO authenticated;
GRANT EXECUTE ON FUNCTION get_quote_customs_summary(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION is_quote_customs_complete(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_hs_code_stats(UUID) TO authenticated;

-- =============================================================================
-- INDEX: HS Code for reporting
-- =============================================================================

-- Create index on hs_code for efficient filtering and grouping
CREATE INDEX IF NOT EXISTS idx_quote_items_hs_code ON quote_items (hs_code)
WHERE hs_code IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quote_items_hs_code_prefix ON quote_items (LEFT(hs_code, 4))
WHERE hs_code IS NOT NULL;

-- =============================================================================
-- UPDATE TABLE COMMENT
-- =============================================================================

COMMENT ON TABLE quote_items IS 'Quote line items with v3.0 extensions: supply chain (supplier_id, buyer_company_id, pickup_location_id), procurement fields, item IDN, multi-segment logistics costs (supplier→hub→customs→customer), and customs data (hs_code, duty, extra costs).';
