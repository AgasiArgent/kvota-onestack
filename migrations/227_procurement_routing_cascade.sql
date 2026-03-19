-- Migration: 227_procurement_routing_cascade.sql
-- Description: Replace simple brand-based procurement routing with a full priority cascade.
--   Priority: Tender → Sales Group → Multi-brand skip → Brand Assignment → Unassigned
--   Also backfills existing unassigned items through the new cascade logic.

-- =============================================================================
-- PART 1: Replace the routing function with a full priority cascade
-- =============================================================================

CREATE OR REPLACE FUNCTION kvota.assign_procurement_user_cascade()
RETURNS TRIGGER AS $$
DECLARE
    v_org_id UUID;
    v_created_by UUID;
    v_sales_checklist JSONB;
    v_assigned_user UUID;
    v_sales_group_id UUID;
    v_is_multibrand BOOLEAN;
BEGIN
    -- Get quote context
    SELECT organization_id, created_by_user_id, sales_checklist
    INTO v_org_id, v_created_by, v_sales_checklist
    FROM kvota.quotes
    WHERE id = NEW.quote_id;

    -- Bail out if no org context
    IF v_org_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- -------------------------------------------------------------------------
    -- Step 1: TENDER CHECK
    -- If the quote is marked as a tender, route to the first step in the
    -- tender routing chain.
    -- -------------------------------------------------------------------------
    IF (v_sales_checklist->>'is_tender')::boolean = true THEN
        SELECT user_id INTO v_assigned_user
        FROM kvota.tender_routing_chain
        WHERE organization_id = v_org_id
        ORDER BY step_order ASC
        LIMIT 1;

        IF v_assigned_user IS NOT NULL THEN
            NEW.assigned_procurement_user := v_assigned_user;
            RETURN NEW;
        END IF;
    END IF;

    -- -------------------------------------------------------------------------
    -- Step 2: SALES GROUP CHECK
    -- If the quote creator belongs to a sales group that has a mapped
    -- procurement user, route all items to that user.
    -- -------------------------------------------------------------------------
    IF v_created_by IS NOT NULL THEN
        SELECT up.sales_group_id INTO v_sales_group_id
        FROM kvota.user_profiles up
        WHERE up.user_id = v_created_by
          AND up.organization_id = v_org_id;

        IF v_sales_group_id IS NOT NULL THEN
            SELECT user_id INTO v_assigned_user
            FROM kvota.route_procurement_group_assignments
            WHERE organization_id = v_org_id
              AND sales_group_id = v_sales_group_id;

            IF v_assigned_user IS NOT NULL THEN
                NEW.assigned_procurement_user := v_assigned_user;
                RETURN NEW;
            END IF;
        END IF;
    END IF;

    -- Steps 3–4 require a non-NULL brand
    IF NEW.brand IS NULL THEN
        RETURN NEW;
    END IF;

    -- -------------------------------------------------------------------------
    -- Step 3: MULTI-BRAND CHECK
    -- If the quote already has items with different brands, leave unassigned
    -- so the item goes to the dispatcher queue.
    -- -------------------------------------------------------------------------
    SELECT EXISTS(
        SELECT 1
        FROM kvota.quote_items
        WHERE quote_id = NEW.quote_id
          AND brand IS NOT NULL
          AND LOWER(brand) != LOWER(NEW.brand)
    ) INTO v_is_multibrand;

    IF v_is_multibrand THEN
        -- Multi-brand quote → leave NULL for dispatcher
        RETURN NEW;
    END IF;

    -- -------------------------------------------------------------------------
    -- Step 4: BRAND ASSIGNMENT CHECK (existing logic)
    -- Look up the procurement user mapped to this brand.
    -- -------------------------------------------------------------------------
    SELECT user_id INTO v_assigned_user
    FROM kvota.brand_assignments
    WHERE organization_id = v_org_id
      AND LOWER(brand) = LOWER(NEW.brand);

    IF v_assigned_user IS NOT NULL THEN
        NEW.assigned_procurement_user := v_assigned_user;
        RETURN NEW;
    END IF;

    -- -------------------------------------------------------------------------
    -- Step 5: NO MATCH
    -- Leave assigned_procurement_user as NULL → unassigned queue
    -- -------------------------------------------------------------------------
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- PART 2: Replace the trigger
-- =============================================================================

DROP TRIGGER IF EXISTS trigger_assign_procurement_user ON kvota.quote_items;

CREATE TRIGGER trigger_assign_procurement_user
    BEFORE INSERT OR UPDATE OF brand ON kvota.quote_items
    FOR EACH ROW
    EXECUTE FUNCTION kvota.assign_procurement_user_cascade();

-- =============================================================================
-- PART 3: Drop the old function (no longer referenced)
-- =============================================================================

DROP FUNCTION IF EXISTS kvota.assign_procurement_user_by_brand();

-- =============================================================================
-- PART 4: Grant execute on the new function
-- =============================================================================

GRANT EXECUTE ON FUNCTION kvota.assign_procurement_user_cascade() TO authenticated;

-- =============================================================================
-- PART 5: Backfill existing unassigned items through the cascade
-- =============================================================================

DO $$
DECLARE
    v_item RECORD;
    v_org_id UUID;
    v_created_by UUID;
    v_sales_checklist JSONB;
    v_assigned_user UUID;
    v_sales_group_id UUID;
    v_is_multibrand BOOLEAN;
    v_total_processed INTEGER := 0;
    v_total_assigned INTEGER := 0;
BEGIN
    FOR v_item IN
        SELECT qi.id, qi.quote_id, qi.brand
        FROM kvota.quote_items qi
        JOIN kvota.quotes q ON q.id = qi.quote_id
        WHERE qi.assigned_procurement_user IS NULL
          AND q.deleted_at IS NULL
          AND q.organization_id IS NOT NULL
    LOOP
        v_total_processed := v_total_processed + 1;

        -- Get quote context
        SELECT organization_id, created_by_user_id, sales_checklist
        INTO v_org_id, v_created_by, v_sales_checklist
        FROM kvota.quotes
        WHERE id = v_item.quote_id;

        v_assigned_user := NULL;

        -- Step 1: Tender
        IF (v_sales_checklist->>'is_tender')::boolean = true THEN
            SELECT user_id INTO v_assigned_user
            FROM kvota.tender_routing_chain
            WHERE organization_id = v_org_id
            ORDER BY step_order ASC
            LIMIT 1;
        END IF;

        -- Step 2: Sales group
        IF v_assigned_user IS NULL AND v_created_by IS NOT NULL THEN
            SELECT up.sales_group_id INTO v_sales_group_id
            FROM kvota.user_profiles up
            WHERE up.user_id = v_created_by
              AND up.organization_id = v_org_id;

            IF v_sales_group_id IS NOT NULL THEN
                SELECT user_id INTO v_assigned_user
                FROM kvota.route_procurement_group_assignments
                WHERE organization_id = v_org_id
                  AND sales_group_id = v_sales_group_id;
            END IF;
        END IF;

        -- Step 3: Multi-brand → skip (leave unassigned)
        -- Step 4: Brand assignment
        IF v_assigned_user IS NULL AND v_item.brand IS NOT NULL THEN
            SELECT EXISTS(
                SELECT 1
                FROM kvota.quote_items
                WHERE quote_id = v_item.quote_id
                  AND brand IS NOT NULL
                  AND id != v_item.id
                  AND LOWER(brand) != LOWER(v_item.brand)
            ) INTO v_is_multibrand;

            IF NOT v_is_multibrand THEN
                SELECT user_id INTO v_assigned_user
                FROM kvota.brand_assignments
                WHERE organization_id = v_org_id
                  AND LOWER(brand) = LOWER(v_item.brand);
            END IF;
        END IF;

        -- Apply assignment if found
        IF v_assigned_user IS NOT NULL THEN
            UPDATE kvota.quote_items
            SET assigned_procurement_user = v_assigned_user
            WHERE id = v_item.id;

            v_total_assigned := v_total_assigned + 1;
        END IF;
    END LOOP;

    RAISE NOTICE 'Procurement routing backfill complete: % items processed, % items assigned',
        v_total_processed, v_total_assigned;
END $$;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON FUNCTION kvota.assign_procurement_user_cascade() IS
    'Assigns a procurement user to a quote item using a priority cascade: '
    '1) Tender routing chain, 2) Sales group mapping, 3) Multi-brand skip, '
    '4) Brand assignment, 5) Unassigned (NULL).';
