-- Regression test for migration 279: cascade soft-delete for quote → spec → deal
--
-- Usage (from local machine):
--   cat tests/sql/test_migration_279_soft_delete.sql | \
--     ssh beget-kvota "docker exec -i supabase-db psql -U postgres -d postgres -v ON_ERROR_STOP=1"
--
-- Everything runs inside a single transaction with ROLLBACK at the end — prod
-- data is never touched. If any assertion fails, RAISE EXCEPTION aborts and
-- psql exits with non-zero status (via ON_ERROR_STOP=1).
--
-- Covers REQ-002 (cascade soft-delete) and REQ-003 (restore) from
-- .kiro/specs/soft-delete-entity-lifecycle/requirements.md.

BEGIN;

DO $$
DECLARE
  v_org        uuid;
  v_user       uuid;
  v_customer   uuid;
  v_q_empty    uuid := gen_random_uuid();
  v_q_spec     uuid := gen_random_uuid();
  v_q_full     uuid := gen_random_uuid();
  v_s_alone    uuid := gen_random_uuid();
  v_s_full     uuid := gen_random_uuid();
  v_d_full     uuid := gen_random_uuid();
  v_result     record;
BEGIN
  -- Pick any existing org, user, customer — fixtures reference them via FK only.
  SELECT id INTO v_org FROM kvota.organizations LIMIT 1;
  SELECT id INTO v_user FROM auth.users LIMIT 1;
  SELECT id INTO v_customer FROM kvota.customers LIMIT 1;

  IF v_org IS NULL OR v_user IS NULL OR v_customer IS NULL THEN
    RAISE EXCEPTION 'Prerequisite fixtures missing (org=% user=% customer=%)',
      v_org, v_user, v_customer;
  END IF;

  -- ───────────────────────────────────────────────────────────
  -- Fixture 1: quote only (no spec, no deal)
  INSERT INTO kvota.quotes (id, organization_id, customer_id, idn_quote, title, created_by)
  VALUES (v_q_empty, v_org, v_customer, 'TEST-279-EMPTY', 'Test empty', v_user);

  -- Fixture 2: quote + spec, no deal
  INSERT INTO kvota.quotes (id, organization_id, customer_id, idn_quote, title, created_by)
  VALUES (v_q_spec, v_org, v_customer, 'TEST-279-SPEC', 'Test with spec', v_user);
  INSERT INTO kvota.specifications (id, quote_id, organization_id)
  VALUES (v_s_alone, v_q_spec, v_org);

  -- Fixture 3: quote + spec + deal (full lifecycle)
  INSERT INTO kvota.quotes (id, organization_id, customer_id, idn_quote, title, created_by)
  VALUES (v_q_full, v_org, v_customer, 'TEST-279-FULL', 'Test full', v_user);
  INSERT INTO kvota.specifications (id, quote_id, organization_id)
  VALUES (v_s_full, v_q_full, v_org);
  INSERT INTO kvota.deals (id, specification_id, quote_id, organization_id,
                           deal_number, signed_at, total_amount)
  VALUES (v_d_full, v_s_full, v_q_full, v_org,
          'TEST-279-DEAL', CURRENT_DATE, 100.00);

  RAISE NOTICE '[SETUP] 3 fixtures created';

  -- ───────────────────────────────────────────────────────────
  -- TEST 1: soft-delete quote with no spec, no deal → (1, 0, 0)
  SELECT * INTO v_result FROM kvota.soft_delete_quote(v_q_empty, v_user);
  IF v_result.quote_affected <> 1 OR v_result.spec_affected <> 0 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 1 FAIL: expected (1,0,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  IF (SELECT deleted_at FROM kvota.quotes WHERE id = v_q_empty) IS NULL THEN
    RAISE EXCEPTION 'TEST 1 FAIL: quote deleted_at not set';
  END IF;
  IF (SELECT deleted_by FROM kvota.quotes WHERE id = v_q_empty) <> v_user THEN
    RAISE EXCEPTION 'TEST 1 FAIL: quote deleted_by not set to actor';
  END IF;
  RAISE NOTICE '[TEST 1] PASS: empty quote cascade returns (1,0,0)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 2: soft-delete quote with spec, no deal → (1, 1, 0)
  SELECT * INTO v_result FROM kvota.soft_delete_quote(v_q_spec, v_user);
  IF v_result.quote_affected <> 1 OR v_result.spec_affected <> 1 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 2 FAIL: expected (1,1,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  IF (SELECT deleted_at FROM kvota.specifications WHERE id = v_s_alone) IS NULL THEN
    RAISE EXCEPTION 'TEST 2 FAIL: spec deleted_at not set';
  END IF;
  RAISE NOTICE '[TEST 2] PASS: spec-only cascade returns (1,1,0)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 3: soft-delete full lifecycle → (1, 1, 1)
  SELECT * INTO v_result FROM kvota.soft_delete_quote(v_q_full, v_user);
  IF v_result.quote_affected <> 1 OR v_result.spec_affected <> 1 OR v_result.deal_affected <> 1 THEN
    RAISE EXCEPTION 'TEST 3 FAIL: expected (1,1,1), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  IF (SELECT deleted_at FROM kvota.deals WHERE id = v_d_full) IS NULL THEN
    RAISE EXCEPTION 'TEST 3 FAIL: deal deleted_at not set';
  END IF;
  RAISE NOTICE '[TEST 3] PASS: full-lifecycle cascade returns (1,1,1)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 4: double soft-delete is idempotent → (0, 0, 0)
  SELECT * INTO v_result FROM kvota.soft_delete_quote(v_q_full, v_user);
  IF v_result.quote_affected <> 0 OR v_result.spec_affected <> 0 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 4 FAIL: expected (0,0,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  RAISE NOTICE '[TEST 4] PASS: double soft-delete idempotent, returns (0,0,0)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 5: soft-delete non-existent quote → (0, 0, 0), no error
  SELECT * INTO v_result FROM kvota.soft_delete_quote(
    '99999999-9999-9999-9999-999999999999'::uuid, v_user);
  IF v_result.quote_affected <> 0 OR v_result.spec_affected <> 0 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 5 FAIL: non-existent should return (0,0,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  RAISE NOTICE '[TEST 5] PASS: non-existent quote returns (0,0,0)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 6: restore full lifecycle → (1, 1, 1)
  SELECT * INTO v_result FROM kvota.restore_quote(v_q_full);
  IF v_result.quote_affected <> 1 OR v_result.spec_affected <> 1 OR v_result.deal_affected <> 1 THEN
    RAISE EXCEPTION 'TEST 6 FAIL: expected (1,1,1), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  IF (SELECT deleted_at FROM kvota.quotes WHERE id = v_q_full) IS NOT NULL THEN
    RAISE EXCEPTION 'TEST 6 FAIL: quote deleted_at not cleared';
  END IF;
  IF (SELECT deleted_by FROM kvota.quotes WHERE id = v_q_full) IS NOT NULL THEN
    RAISE EXCEPTION 'TEST 6 FAIL: quote deleted_by not cleared';
  END IF;
  IF (SELECT deleted_at FROM kvota.specifications WHERE id = v_s_full) IS NOT NULL THEN
    RAISE EXCEPTION 'TEST 6 FAIL: spec deleted_at not cleared';
  END IF;
  IF (SELECT deleted_at FROM kvota.deals WHERE id = v_d_full) IS NOT NULL THEN
    RAISE EXCEPTION 'TEST 6 FAIL: deal deleted_at not cleared';
  END IF;
  RAISE NOTICE '[TEST 6] PASS: full-lifecycle restore returns (1,1,1) and clears all columns';

  -- ───────────────────────────────────────────────────────────
  -- TEST 7: double restore is idempotent → (0, 0, 0)
  SELECT * INTO v_result FROM kvota.restore_quote(v_q_full);
  IF v_result.quote_affected <> 0 OR v_result.spec_affected <> 0 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 7 FAIL: expected (0,0,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  RAISE NOTICE '[TEST 7] PASS: double restore idempotent, returns (0,0,0)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 8: partial cascade — user hand-restored only the quote, not spec/deal;
  -- restore_quote should catch up the rest → (0, 1, 1)
  UPDATE kvota.quotes SET deleted_at = now(), deleted_by = v_user WHERE id = v_q_full;
  UPDATE kvota.specifications SET deleted_at = now(), deleted_by = v_user WHERE id = v_s_full;
  UPDATE kvota.deals SET deleted_at = now(), deleted_by = v_user WHERE id = v_d_full;
  UPDATE kvota.quotes SET deleted_at = NULL, deleted_by = NULL WHERE id = v_q_full;
  SELECT * INTO v_result FROM kvota.restore_quote(v_q_full);
  IF v_result.quote_affected <> 0 OR v_result.spec_affected <> 1 OR v_result.deal_affected <> 1 THEN
    RAISE EXCEPTION 'TEST 8 FAIL: expected (0,1,1), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  RAISE NOTICE '[TEST 8] PASS: partial-restore catches up stragglers, returns (0,1,1)';

  -- ───────────────────────────────────────────────────────────
  -- TEST 9: restore of a quote that had no spec/deal → (1, 0, 0)
  -- (Test 1 soft-deleted v_q_empty; restore should bring it back cleanly.)
  SELECT * INTO v_result FROM kvota.restore_quote(v_q_empty);
  IF v_result.quote_affected <> 1 OR v_result.spec_affected <> 0 OR v_result.deal_affected <> 0 THEN
    RAISE EXCEPTION 'TEST 9 FAIL: expected (1,0,0), got (%,%,%)',
      v_result.quote_affected, v_result.spec_affected, v_result.deal_affected;
  END IF;
  IF (SELECT deleted_at FROM kvota.quotes WHERE id = v_q_empty) IS NOT NULL THEN
    RAISE EXCEPTION 'TEST 9 FAIL: quote deleted_at not cleared';
  END IF;
  RAISE NOTICE '[TEST 9] PASS: restore of empty quote returns (1,0,0)';

  RAISE NOTICE '';
  RAISE NOTICE '✅ ALL 9 TESTS PASS';
END;
$$;

ROLLBACK;
