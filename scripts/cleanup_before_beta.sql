-- Cleanup script: Remove all business data before beta test
-- Keeps: seller_companies, roles, departments, sales_groups, plan_fact_categories, organizations
-- Run via: docker exec supabase-db psql -U postgres -d postgres -f /tmp/cleanup_before_beta.sql

BEGIN;

-- 1. Remove business data in dependency order

-- Deals and related
DELETE FROM kvota.plan_fact_items;
DELETE FROM kvota.deal_logistics;
DELETE FROM kvota.deal_customs;
DELETE FROM kvota.deals;

-- Specifications and related
DELETE FROM kvota.specification_payments;
DELETE FROM kvota.specification_items;
DELETE FROM kvota.specifications;

-- Quotes and related
DELETE FROM kvota.quote_versions;
DELETE FROM kvota.quote_approvals;
DELETE FROM kvota.quote_items;
DELETE FROM kvota.quotes;

-- Invoices
DELETE FROM kvota.invoice_items;
DELETE FROM kvota.invoices;
DELETE FROM kvota.supplier_invoice_items;
DELETE FROM kvota.supplier_invoices;

-- Reference business data
DELETE FROM kvota.customers;
DELETE FROM kvota.suppliers;
DELETE FROM kvota.products;

-- Tasks and notifications
DELETE FROM kvota.tasks;
DELETE FROM kvota.notifications;

-- 2. Remove test users EXCEPT admin@test.kvota.ru

-- Get admin user ID to exclude
DO $$
DECLARE
    admin_uid uuid;
    test_uid uuid;
    r RECORD;
BEGIN
    -- Find admin test user
    SELECT id INTO admin_uid FROM auth.users WHERE email = 'admin@test.kvota.ru';

    -- Loop through all other test users
    FOR r IN SELECT id, email FROM auth.users
             WHERE email LIKE '%@test.kvota.ru'
             AND email != 'admin@test.kvota.ru'
    LOOP
        test_uid := r.id;
        RAISE NOTICE 'Removing test user: %', r.email;

        -- Remove role assignments
        DELETE FROM kvota.user_roles WHERE user_id = test_uid;
        -- Remove org membership
        DELETE FROM kvota.organization_members WHERE user_id = test_uid;
        -- Remove user profile
        DELETE FROM kvota.user_profiles WHERE user_id = test_uid;
        -- Remove brand assignments
        DELETE FROM kvota.brand_assignments WHERE user_id = test_uid;
        -- Delete auth user
        DELETE FROM auth.users WHERE id = test_uid;
    END LOOP;

    RAISE NOTICE 'Kept admin user: %', admin_uid;
END $$;

COMMIT;
