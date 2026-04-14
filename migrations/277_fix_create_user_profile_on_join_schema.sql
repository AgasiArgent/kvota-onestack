-- Migration 277: Fix create_user_profile_on_join to qualify schema
--
-- Problem: The trigger function `public.create_user_profile_on_join` fires
-- AFTER INSERT ON kvota.organization_members and writes to `user_profiles`
-- (unqualified). Because PostgREST sets `search_path = kvota, public`, the
-- unqualified name resolves to `kvota.user_profiles` — which does NOT have
-- the column `last_active_organization_id`. Insert fails with:
--   'column "last_active_organization_id" of relation "user_profiles" does not exist'
--
-- This blocks admin user creation (api/admin_users.py:227 → trigger fires → fails).
--
-- Fix: Qualify the target table as `public.user_profiles` so the function
-- behaves deterministically regardless of caller's search_path.

CREATE OR REPLACE FUNCTION public.create_user_profile_on_join()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    INSERT INTO public.user_profiles (user_id, last_active_organization_id)
    VALUES (NEW.user_id, NEW.organization_id)
    ON CONFLICT (user_id) DO UPDATE
    SET last_active_organization_id = NEW.organization_id;

    RETURN NEW;
END;
$function$;
