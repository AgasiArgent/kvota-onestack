-- Migration 290: calc engine adapter view v_logistics_plan_fact_items.
-- Wave 1 Task 4.3 of logistics-customs-redesign spec (R6.3).
--
-- Purpose: expose new logistics_route_segments + logistics_segment_expenses
-- in the row shape calc engine expects (plan_fact_items-compatible), so
-- calc_engine.py stays untouched.
--
-- Category mapping via (from_location_type, to_location_type) — see
-- .kiro/specs/logistics-customs-redesign/design.md §5.4 for the full matrix.
--
-- Expenses inherit their parent segment's category (don't create a dedicated
-- "additional expense" category — expenses are semantically attached to the
-- segment they occur on).
--
-- Read-only view. All writes go through the normal segments/expenses tables.

CREATE OR REPLACE VIEW kvota.v_logistics_plan_fact_items AS
-- Helper CTE: resolve category_id per segment via (from_type, to_type)
WITH segment_with_category AS (
    SELECT
        rs.id AS segment_id,
        rs.invoice_id,
        rs.label,
        rs.sequence_order,
        rs.main_cost_rub,
        rs.transit_days,
        rs.created_by,
        rs.created_at,
        (
            SELECT pfc.id
            FROM kvota.plan_fact_categories pfc
            WHERE pfc.code = CASE
                WHEN from_loc.location_type = 'supplier' AND to_loc.location_type = 'hub'
                    THEN 'logistics_first_mile'
                WHEN from_loc.location_type = 'hub' AND to_loc.location_type = 'hub'
                    THEN 'logistics_hub_hub'
                WHEN from_loc.location_type = 'hub' AND to_loc.location_type IN ('customs', 'own_warehouse')
                    THEN 'logistics_transit'
                WHEN from_loc.location_type = 'customs' AND to_loc.location_type = 'own_warehouse'
                    THEN 'logistics_post_transit'
                WHEN from_loc.location_type IN ('customs', 'own_warehouse') AND to_loc.location_type = 'client'
                    THEN 'logistics_last_mile'
                ELSE 'logistics_transit'  -- catch-all fallback
            END
            LIMIT 1
        ) AS category_id
    FROM kvota.logistics_route_segments rs
    JOIN kvota.locations from_loc ON from_loc.id = rs.from_location_id
    JOIN kvota.locations to_loc ON to_loc.id = rs.to_location_id
)
-- Main cost row per segment
SELECT
    -- Deterministic UUID — hashtext of 'seg:' + segment_id keeps row stable
    -- across view refreshes (not strictly needed for read-only view, but
    -- helps if any consumer remembers ids between calls).
    ('00000000-0000-0000-0000-' || substring(md5('seg:' || swc.segment_id::text), 1, 12))::uuid AS id,
    d.id AS deal_id,
    swc.category_id,
    COALESCE(swc.label, 'Сегмент ' || swc.sequence_order::text) AS description,
    swc.main_cost_rub AS planned_amount,
    'RUB'::text AS planned_currency,
    NULL::timestamptz AS planned_date,
    NULL::numeric AS actual_amount,
    NULL::text AS actual_currency,
    NULL::date AS actual_date,
    NULL::uuid AS logistics_stage_id,  -- deprecated model reference
    swc.segment_id AS logistics_segment_id,
    NULL::uuid AS segment_expense_id,
    swc.created_by,
    swc.created_at,
    'v_logistics_segment'::text AS source
FROM segment_with_category swc
JOIN kvota.invoices i ON i.id = swc.invoice_id
JOIN kvota.deals d ON d.specification_id = i.quote_id
WHERE swc.main_cost_rub > 0

UNION ALL

-- Row per segment_expense (inherits parent's category)
SELECT
    ('00000000-0000-0000-0000-' || substring(md5('exp:' || se.id::text), 1, 12))::uuid AS id,
    d.id AS deal_id,
    swc.category_id,
    se.label AS description,
    se.cost_rub AS planned_amount,
    'RUB'::text AS planned_currency,
    NULL::timestamptz AS planned_date,
    NULL::numeric AS actual_amount,
    NULL::text AS actual_currency,
    NULL::date AS actual_date,
    NULL::uuid AS logistics_stage_id,
    swc.segment_id AS logistics_segment_id,
    se.id AS segment_expense_id,
    NULL::uuid AS created_by,
    se.created_at,
    'v_logistics_segment_expense'::text AS source
FROM kvota.logistics_segment_expenses se
JOIN segment_with_category swc ON swc.segment_id = se.segment_id
JOIN kvota.invoices i ON i.id = swc.invoice_id
JOIN kvota.deals d ON d.specification_id = i.quote_id
WHERE se.cost_rub > 0;

COMMENT ON VIEW kvota.v_logistics_plan_fact_items IS
    'Calc engine adapter: exposes logistics_route_segments + logistics_segment_expenses in plan_fact_items-compatible shape. Read-only. See .kiro/specs/logistics-customs-redesign/design.md §5.4.';

-- Grant SELECT to authenticated; view is read-only by PostgreSQL default.
GRANT SELECT ON kvota.v_logistics_plan_fact_items TO authenticated;

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (290, '290_v_logistics_plan_fact_items', now())
ON CONFLICT (id) DO NOTHING;
