-- Migration 273: Harden kvota.get_user_organization_ids against search_path pitfalls
-- Bug: FB-260413-094409-0e1f — "Сломался выбор контактов и адреса доставки"
--
-- Root cause: the SECURITY DEFINER function referenced organization_members
-- without a schema qualifier and had no SET search_path clause. When the RLS
-- chain on customer_contacts → organization_members → get_user_organization_ids
-- was evaluated by a session whose search_path did not include `kvota`
-- (e.g. plan-cached across connections, or transactions where PostgREST had
-- not yet applied the schema profile), the SQL function errored out during
-- startup with "relation \"organization_members\" does not exist". RLS on
-- organization_members then returned empty, which cascaded to empty results
-- on customer_contacts and customer_delivery_addresses — contact/address
-- dropdowns on the quote page showed "Нет контактов" / "Нет адресов" even
-- for users with legitimate access.
--
-- Fix (defense in depth):
--   1. Schema-qualify the table reference: FROM kvota.organization_members
--   2. Pin search_path on the function itself: SET search_path = kvota, public
-- Either fix alone prevents this class of bug; both together make the
-- function immune to any caller-side search_path mistake — the standard
-- PostgreSQL security best practice for SECURITY DEFINER functions.
--
-- This migration intentionally touches ONLY get_user_organization_ids.
-- ~24 other kvota.* SECURITY DEFINER functions lack SET search_path and
-- should be hardened in a follow-up sweep (out of scope for this bug fix).

BEGIN;

CREATE OR REPLACE FUNCTION kvota.get_user_organization_ids(p_user_id uuid)
  RETURNS SETOF uuid
  LANGUAGE sql
  STABLE
  SECURITY DEFINER
  SET search_path = kvota, public
AS $$
  SELECT organization_id
  FROM kvota.organization_members
  WHERE user_id = p_user_id AND status = 'active';
$$;

COMMENT ON FUNCTION kvota.get_user_organization_ids(uuid) IS
  'Returns active organization IDs for a user. SECURITY DEFINER + pinned search_path prevent RLS chain failures when caller search_path lacks kvota (see migration 273 / FB-260413-094409-0e1f).';

-- ============================================================================
-- Regression test: assert the function works even when caller's session
-- search_path deliberately excludes kvota. This is the exact condition that
-- broke contact/address dropdowns in production.
-- ============================================================================

DO $$
DECLARE
  v_count integer;
BEGIN
  -- Deliberately shadow the search_path so kvota.* is NOT resolvable by
  -- unqualified references — this simulates the broken production state.
  PERFORM set_config('search_path', 'public', true);

  -- The function must succeed. Before the fix, this would raise
  -- "relation \"organization_members\" does not exist".
  SELECT count(*) INTO v_count
  FROM kvota.get_user_organization_ids('00000000-0000-0000-0000-000000000000'::uuid);

  -- Any non-negative count (including 0 for the fake UUID) means the function
  -- executed successfully instead of erroring during startup.
  IF v_count IS NULL THEN
    RAISE EXCEPTION 'Regression: get_user_organization_ids returned NULL count — function likely failed silently';
  END IF;

  RAISE NOTICE 'Regression test passed: get_user_organization_ids works under search_path=public';
END;
$$;

COMMIT;
