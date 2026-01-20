-- ===========================================================================
-- Migration 101: Move existing OneStack tables to kvota schema
-- ===========================================================================
-- Description: Move 45 existing OneStack tables from public to kvota schema
--              This operation is SAFE - no data loss, only schema change
-- Prerequisites: Migration 100 must be applied (kvota schema created)
-- Created: 2026-01-20
-- ===========================================================================

-- ===========================================================================
-- SAFETY CHECK: Verify kvota schema exists
-- ===========================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata
        WHERE schema_name = 'kvota'
    ) THEN
        RAISE EXCEPTION 'Schema kvota does not exist! Please run migration 100 first.';
    END IF;
END $$;

-- ===========================================================================
-- STEP 1: Move Quotes tables (12 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.quotes SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_items SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_versions SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_approval_history SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_calculation_products_versioned SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_calculation_results SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_calculation_summaries SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_calculation_summaries_versioned SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_calculation_variables SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_export_settings SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_timeline_events SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.quote_workflow_transitions SET SCHEMA kvota;

-- ===========================================================================
-- STEP 2: Move Plan-Fact tables (7 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.plan_fact_categories SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_items SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_financing_recalculated SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_logistics_stages SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_permissions SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_products SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.plan_fact_sections SET SCHEMA kvota;

-- ===========================================================================
-- STEP 3: Move Organization tables (6 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.organizations SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.organization_members SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.organization_currency_history SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.organization_exchange_rates SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.organization_invitations SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.organization_workflow_settings SET SCHEMA kvota;

-- ===========================================================================
-- STEP 4: Move Customer tables (4 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.customers SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.customer_contacts SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.customer_contracts SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.customer_delivery_addresses SET SCHEMA kvota;

-- ===========================================================================
-- STEP 5: Move Supplier tables (2 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.suppliers SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.supplier_countries SET SCHEMA kvota;

-- ===========================================================================
-- STEP 6: Move Specification and Deal tables (3 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.specifications SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.specification_exports SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.deals SET SCHEMA kvota;

-- ===========================================================================
-- STEP 7: Move Workflow and Roles tables (5 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.roles SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.user_roles SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.brand_assignments SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.approvals SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.workflow_transitions SET SCHEMA kvota;

-- ===========================================================================
-- STEP 8: Move Notification tables (2 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.notifications SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.telegram_users SET SCHEMA kvota;

-- ===========================================================================
-- STEP 9: Move Company tables (2 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.seller_companies SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.purchasing_companies SET SCHEMA kvota;

-- ===========================================================================
-- STEP 10: Move Settings tables (2 tables)
-- ===========================================================================

ALTER TABLE IF EXISTS public.calculation_settings SET SCHEMA kvota;
ALTER TABLE IF EXISTS public.exchange_rates SET SCHEMA kvota;

-- ===========================================================================
-- STEP 11: Move Functions to kvota schema
-- ===========================================================================

-- Helper functions for roles
DO $$
DECLARE
    func_record RECORD;
BEGIN
    FOR func_record IN (
        SELECT n.nspname as schema_name, p.proname as function_name,
               pg_get_function_identity_arguments(p.oid) as args
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'public'
        AND (
            p.proname LIKE '%quote%'
            OR p.proname LIKE '%specification%'
            OR p.proname LIKE '%deal%'
            OR p.proname LIKE '%supplier%'
            OR p.proname LIKE '%plan_fact%'
            OR p.proname LIKE '%organization%'
            OR p.proname LIKE '%customer%'
            OR p.proname IN (
                'user_has_role_in_org',
                'user_organization_ids',
                'user_is_admin_in_org',
                'complete_item_procurement',
                'check_quote_procurement_complete',
                'assign_procurement_user_by_brand',
                'generate_deal_number',
                'update_deals_updated_at',
                'calculate_plan_fact_variance',
                'update_plan_fact_items_updated_at',
                'generate_telegram_verification_code',
                'request_telegram_verification',
                'verify_telegram_account',
                'create_notification',
                'mark_notification_sent',
                'mark_notification_failed',
                'mark_notification_read',
                'get_pending_notifications'
            )
        )
    ) LOOP
        BEGIN
            EXECUTE format('ALTER FUNCTION public.%I(%s) SET SCHEMA kvota',
                          func_record.function_name,
                          func_record.args);
            RAISE NOTICE 'Moved function: %.%(%))', func_record.schema_name,
                        func_record.function_name, func_record.args;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Could not move function %.%(%): %', func_record.schema_name,
                        func_record.function_name, func_record.args, SQLERRM;
        END;
    END LOOP;
END $$;

-- ===========================================================================
-- STEP 12: Update RLS Policies search paths
-- ===========================================================================

-- Note: RLS policies will continue to work after schema move
-- However, any explicit schema references in policies need updating
-- This is handled automatically by PostgreSQL for most cases

-- ===========================================================================
-- STEP 13: Grant permissions on moved objects
-- ===========================================================================

GRANT ALL ON ALL TABLES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL ROUTINES IN SCHEMA kvota TO authenticated;

GRANT ALL ON ALL TABLES IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA kvota TO service_role;

-- ===========================================================================
-- VERIFICATION: List moved tables
-- ===========================================================================

DO $$
DECLARE
    table_count INTEGER;
    func_count INTEGER;
BEGIN
    -- Count tables in kvota schema
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'kvota'
    AND table_type = 'BASE TABLE';

    -- Count functions in kvota schema
    SELECT COUNT(*) INTO func_count
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'kvota';

    RAISE NOTICE '=====================================';
    RAISE NOTICE 'Migration 101 completed successfully!';
    RAISE NOTICE '=====================================';
    RAISE NOTICE 'Tables moved to kvota schema: %', table_count;
    RAISE NOTICE 'Functions moved to kvota schema: %', func_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Expected: 45 tables minimum';

    IF table_count < 45 THEN
        RAISE WARNING 'Expected at least 45 tables, but found only %. Some tables may not have been moved.', table_count;
    END IF;

    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Update backend code to use schema kvota';
    RAISE NOTICE '2. Set search_path in database connections';
    RAISE NOTICE '3. Run migrations 102-109 to create missing tables';
END $$;

-- ===========================================================================
-- List all tables in kvota schema for verification
-- ===========================================================================

SELECT
    schemaname,
    tablename,
    CASE
        WHEN tablename LIKE 'quote%' THEN 'Quotes'
        WHEN tablename LIKE 'plan_fact%' THEN 'Finance'
        WHEN tablename LIKE 'organization%' THEN 'Organizations'
        WHEN tablename LIKE 'customer%' THEN 'Customers'
        WHEN tablename LIKE 'supplier%' THEN 'Suppliers'
        WHEN tablename LIKE 'specification%' THEN 'Specifications'
        ELSE 'Other'
    END as category
FROM pg_tables
WHERE schemaname = 'kvota'
ORDER BY category, tablename;

-- ===========================================================================
-- END OF MIGRATION
-- ===========================================================================
