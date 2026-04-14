-- Migration 278: Defense-in-depth — pin search_path on create_user_profile_on_join
--
-- Migration 277 already qualified the target table (`public.user_profiles`),
-- which alone is sufficient to fix the immediate bug ("Failed to create user
-- records" — column "last_active_organization_id" of "user_profiles" missing
-- when search_path resolved to kvota.user_profiles).
--
-- This migration adds the second layer of defense — pinning `search_path` on
-- the function itself — matching the convention established in migration 273
-- (FB-260413-094409-0e1f). With both layers, the function is immune to any
-- caller-side search_path manipulation, including future schemas that might
-- shadow `public`.

BEGIN;

CREATE OR REPLACE FUNCTION public.create_user_profile_on_join()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, kvota
AS $function$
BEGIN
    INSERT INTO public.user_profiles (user_id, last_active_organization_id)
    VALUES (NEW.user_id, NEW.organization_id)
    ON CONFLICT (user_id) DO UPDATE
    SET last_active_organization_id = NEW.organization_id;

    RETURN NEW;
END;
$function$;

COMMENT ON FUNCTION public.create_user_profile_on_join() IS
  'Trigger on kvota.organization_members INSERT — mirrors active org into public.user_profiles.last_active_organization_id. Schema-qualified target + pinned search_path together prevent regressions when callers run with non-standard search_path (see migrations 277, 278).';

-- ============================================================================
-- Regression assertion: verify the function carries both defenses.
-- Trigger functions cannot be invoked directly with a synthetic NEW record,
-- so we assert the function's metadata instead — both the qualified table
-- reference and the pinned search_path must be present in the source.
-- ============================================================================

DO $$
DECLARE
  v_src text;
  v_config text[];
BEGIN
  SELECT prosrc, proconfig
  INTO v_src, v_config
  FROM pg_proc
  WHERE oid = 'public.create_user_profile_on_join'::regproc;

  -- Layer 1: schema-qualified table reference
  IF v_src NOT LIKE '%public.user_profiles%' THEN
    RAISE EXCEPTION 'Regression: function source does not reference public.user_profiles (qualified)';
  END IF;

  -- Layer 2: pinned search_path
  IF v_config IS NULL OR NOT (v_config::text LIKE '%search_path=%') THEN
    RAISE EXCEPTION 'Regression: function lacks pinned search_path';
  END IF;

  RAISE NOTICE 'Defense-in-depth assertion passed: qualified target + pinned search_path';
END;
$$;

COMMIT;
