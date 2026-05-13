-- Migration: 314_fix_locations_rls_role_column.sql
-- Description: Restore RLS on kvota.locations with current `r.slug` role check.
-- Context: Migration 024 (2026-01-15) enabled RLS on `public.locations` with 4 policies
--          (SELECT for org members, INSERT/UPDATE/DELETE for admin via `r.code = 'admin'`).
--          When the table was later moved into the `kvota` schema, the RLS settings + policies
--          were not carried over — prod currently has `relrowsecurity = f` and zero policies
--          (verified 2026-05-13 via pg_policies + pg_class). Migration 168 (2026-02-11) also
--          renamed `roles.code` → `roles.slug` project-wide, so any restored policies must
--          use `r.slug`.
--          PR #143 (Batch L row 13) added a Server Action using the admin Supabase client +
--          explicit role check to let МВЭД/МОЛ/РОЗ/РОЛ create locations. The admin client
--          bypasses RLS regardless, so re-enabling RLS does not affect that flow. Regular
--          SELECT (read in the locations registry) keeps working because the new SELECT
--          policy below scopes to the user's organization, matching the prior behavior.
-- Date: 2026-05-13

BEGIN;

-- Defensive drops in case partial state exists.
DROP POLICY IF EXISTS "Users can view own organization locations" ON kvota.locations;
DROP POLICY IF EXISTS "Admin can insert locations"               ON kvota.locations;
DROP POLICY IF EXISTS "Admin can update locations"               ON kvota.locations;
DROP POLICY IF EXISTS "Admin can delete locations"               ON kvota.locations;

ALTER TABLE kvota.locations ENABLE ROW LEVEL SECURITY;

-- SELECT: any authenticated org member can read locations in their org.
CREATE POLICY "Users can view own organization locations"
    ON kvota.locations FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles
            WHERE user_id = auth.uid()
        )
    );

-- INSERT/UPDATE/DELETE: admin only at the RLS layer (matches migration 024 intent).
-- The Server Action in PR #143 uses the admin client + explicit role check to widen this
-- for МВЭД/МОЛ/РОЗ/РОЛ at the application layer; that path bypasses RLS regardless.
CREATE POLICY "Admin can insert locations"
    ON kvota.locations FOR INSERT
    TO authenticated
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

CREATE POLICY "Admin can update locations"
    ON kvota.locations FOR UPDATE
    TO authenticated
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

CREATE POLICY "Admin can delete locations"
    ON kvota.locations FOR DELETE
    TO authenticated
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

COMMIT;
