-- Regression test for migration 280: active_* views + hide_deleted_from_non_admin RLS
--
-- Usage (from local machine):
--   cat tests/sql/test_migration_280.sql | \
--     ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres -v ON_ERROR_STOP=1"
--
-- Everything runs inside a single transaction with ROLLBACK at the end — prod
-- data is never touched. If any assertion fails, RAISE EXCEPTION aborts and
-- psql exits with non-zero status (via ON_ERROR_STOP=1).
--
-- Covers REQ-005 (read-side invisibility) from
-- .kiro/specs/soft-delete-entity-lifecycle/requirements.md.

BEGIN;

DO $$
DECLARE
  v_org           uuid;
  v_user          uuid;
  v_customer      uuid;
  v_q_active      uuid := gen_random_uuid();
  v_q_deleted     uuid := gen_random_uuid();
  v_s_active      uuid := gen_random_uuid();
  v_s_deleted     uuid := gen_random_uuid();
  v_d_active      uuid := gen_random_uuid();
  v_d_deleted     uuid := gen_random_uuid();
  v_active_count  int;
  v_deleted_seen  int;
BEGIN
  -- Fixtures
  SELECT id INTO v_org FROM kvota.organizations LIMIT 1;
  SELECT id INTO v_user FROM auth.users LIMIT 1;
  SELECT id INTO v_customer FROM kvota.customers LIMIT 1;

  IF v_org IS NULL OR v_user IS NULL OR v_customer IS NULL THEN
    RAISE EXCEPTION 'Prerequisite fixtures missing (org=% user=% customer=%)',
      v_org, v_user, v_customer;
  END IF;

  -- Two quotes: one active, one soft-deleted
  INSERT INTO kvota.quotes (id, organization_id, customer_id, idn_quote, title, created_by)
  VALUES (v_q_active,  v_org, v_customer, 'TEST-280-ACTIVE',  'Active',  v_user),
         (v_q_deleted, v_org, v_customer, 'TEST-280-DELETED', 'Deleted', v_user);
  UPDATE kvota.quotes SET deleted_at = now(), deleted_by = v_user WHERE id = v_q_deleted;

  -- Two specs: one active, one soft-deleted
  INSERT INTO kvota.specifications (id, quote_id, organization_id)
  VALUES (v_s_active,  v_q_active,  v_org),
         (v_s_deleted, v_q_deleted, v_org);
  UPDATE kvota.specifications SET deleted_at = now(), deleted_by = v_user
    WHERE id = v_s_deleted;

  -- Two deals: one active, one soft-deleted
  INSERT INTO kvota.deals (id, specification_id, quote_id, organization_id,
                           deal_number, signed_at, total_amount)
  VALUES (v_d_active,  v_s_active,  v_q_active,  v_org, 'TEST-280-DA',  CURRENT_DATE, 100.00),
         (v_d_deleted, v_s_deleted, v_q_deleted, v_org, 'TEST-280-DD',  CURRENT_DATE, 100.00);
  UPDATE kvota.deals SET deleted_at = now(), deleted_by = v_user WHERE id = v_d_deleted;

  RAISE NOTICE '[SETUP] 3 active + 3 soft-deleted fixtures created';

  -- ───────────────────────────────────────────────────────────
  -- TEST 1: active_quotes excludes soft-deleted
  SELECT count(*) INTO v_active_count
    FROM kvota.active_quotes WHERE id IN (v_q_active, v_q_deleted);
  SELECT count(*) INTO v_deleted_seen
    FROM kvota.active_quotes WHERE id = v_q_deleted;

  IF v_active_count <> 1 THEN
    RAISE EXCEPTION 'TEST 1 FAIL: active_quotes should return 1 row for our pair, got %', v_active_count;
  END IF;
  IF v_deleted_seen <> 0 THEN
    RAISE EXCEPTION 'TEST 1 FAIL: active_quotes should NOT return soft-deleted row, got %', v_deleted_seen;
  END IF;
  RAISE NOTICE '[TEST 1] PASS: active_quotes hides soft-deleted quote';

  -- TEST 2: active_specs excludes soft-deleted
  SELECT count(*) INTO v_active_count
    FROM kvota.active_specs WHERE id IN (v_s_active, v_s_deleted);
  SELECT count(*) INTO v_deleted_seen
    FROM kvota.active_specs WHERE id = v_s_deleted;
  IF v_active_count <> 1 OR v_deleted_seen <> 0 THEN
    RAISE EXCEPTION 'TEST 2 FAIL: active_specs active=%, deleted_seen=%', v_active_count, v_deleted_seen;
  END IF;
  RAISE NOTICE '[TEST 2] PASS: active_specs hides soft-deleted spec';

  -- TEST 3: active_deals excludes soft-deleted
  SELECT count(*) INTO v_active_count
    FROM kvota.active_deals WHERE id IN (v_d_active, v_d_deleted);
  SELECT count(*) INTO v_deleted_seen
    FROM kvota.active_deals WHERE id = v_d_deleted;
  IF v_active_count <> 1 OR v_deleted_seen <> 0 THEN
    RAISE EXCEPTION 'TEST 3 FAIL: active_deals active=%, deleted_seen=%', v_active_count, v_deleted_seen;
  END IF;
  RAISE NOTICE '[TEST 3] PASS: active_deals hides soft-deleted deal';

  -- ───────────────────────────────────────────────────────────
  -- TEST 4: base tables still visible via service_role / superuser
  -- (we're running as superuser inside this DO block — RLS does not apply to
  --  table owners and bypassrls roles, which is exactly the admin bypass path
  --  the application uses. Verify we CAN see the soft-deleted rows here.)
  SELECT count(*) INTO v_deleted_seen
    FROM kvota.quotes WHERE id = v_q_deleted;
  IF v_deleted_seen <> 1 THEN
    RAISE EXCEPTION 'TEST 4 FAIL: superuser/service_role should see soft-deleted quote on base table, got %', v_deleted_seen;
  END IF;
  RAISE NOTICE '[TEST 4] PASS: base kvota.quotes still exposes soft-deleted row to service_role';

  -- ───────────────────────────────────────────────────────────
  -- TEST 5: verify the three views actually exist with security_invoker=true
  PERFORM 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'kvota'
      AND c.relname IN ('active_quotes', 'active_specs', 'active_deals')
      AND c.reloptions @> ARRAY['security_invoker=true'];
  IF NOT FOUND THEN
    RAISE EXCEPTION 'TEST 5 FAIL: active_* views not found with security_invoker=true';
  END IF;
  -- Must find exactly 3
  SELECT count(*) INTO v_active_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'kvota'
      AND c.relname IN ('active_quotes', 'active_specs', 'active_deals')
      AND c.reloptions @> ARRAY['security_invoker=true'];
  IF v_active_count <> 3 THEN
    RAISE EXCEPTION 'TEST 5 FAIL: expected 3 active_* views with security_invoker=true, got %', v_active_count;
  END IF;
  RAISE NOTICE '[TEST 5] PASS: 3 active_* views exist with security_invoker=true';

  -- TEST 6: verify restrictive RLS policies exist on all 3 tables
  SELECT count(*) INTO v_active_count
    FROM pg_policy p
    JOIN pg_class c ON c.oid = p.polrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'kvota'
      AND c.relname IN ('quotes', 'specifications', 'deals')
      AND p.polname LIKE '%hide_deleted_from_non_admin'
      AND p.polpermissive = false;  -- RESTRICTIVE
  IF v_active_count <> 3 THEN
    RAISE EXCEPTION 'TEST 6 FAIL: expected 3 RESTRICTIVE hide-deleted policies, got %', v_active_count;
  END IF;
  RAISE NOTICE '[TEST 6] PASS: 3 RESTRICTIVE RLS policies exist';

END $$;

ROLLBACK;
