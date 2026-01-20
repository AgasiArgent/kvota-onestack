-- ===========================================================================
-- Migration 100: Create kvota schema
-- ===========================================================================
-- Description: Create separate PostgreSQL schema for OneStack project
--              to isolate it from other projects in shared Supabase instance
-- Created: 2026-01-20
-- ===========================================================================

-- ===========================================================================
-- STEP 1: Create kvota schema
-- ===========================================================================

CREATE SCHEMA IF NOT EXISTS kvota;

COMMENT ON SCHEMA kvota IS 'OneStack application schema - isolated from other projects';

-- ===========================================================================
-- STEP 2: Grant permissions
-- ===========================================================================

-- Grant usage to authenticated users
GRANT USAGE ON SCHEMA kvota TO authenticated;
GRANT USAGE ON SCHEMA kvota TO service_role;

-- Grant permissions on all tables in schema
GRANT ALL ON ALL TABLES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL SEQUENCES IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA kvota TO authenticated;
GRANT ALL ON ALL ROUTINES IN SCHEMA kvota TO authenticated;

-- Grant permissions on all tables in schema to service_role
GRANT ALL ON ALL TABLES IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA kvota TO service_role;
GRANT ALL ON ALL ROUTINES IN SCHEMA kvota TO service_role;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON TABLES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON SEQUENCES TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON FUNCTIONS TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON ROUTINES TO authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON FUNCTIONS TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA kvota GRANT ALL ON ROUTINES TO service_role;

-- ===========================================================================
-- STEP 3: Set search_path for convenience
-- ===========================================================================

-- This allows queries to find tables in kvota schema without explicit schema prefix
-- Applications should set this in their connection string or session
-- Example: SET search_path TO kvota, public;

COMMENT ON SCHEMA kvota IS 'OneStack schema. Use: SET search_path TO kvota, public;';

-- ===========================================================================
-- VERIFICATION
-- ===========================================================================

-- Verify schema was created
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.schemata
        WHERE schema_name = 'kvota'
    ) THEN
        RAISE EXCEPTION 'Schema kvota was not created!';
    END IF;

    RAISE NOTICE 'Schema kvota created successfully!';
    RAISE NOTICE 'Next step: Run migration 101 to move existing tables to kvota schema';
END $$;

-- ===========================================================================
-- END OF MIGRATION
-- ===========================================================================
