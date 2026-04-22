-- Migration 287: Add location_type enum-like column to kvota.locations.
-- Wave 1 Task 1 of logistics-customs-redesign spec (Requirements R15).
--
-- Background: kvota.locations currently classifies locations via two booleans
--   - is_hub (logistics hub)
--   - is_customs_point (customs clearance point)
-- The new model uses a single `location_type` enum column with 5 values:
--   supplier      — the factory / producer
--   hub           — transshipment node (first or intermediate hub)
--   customs       — customs clearance point
--   own_warehouse — our own warehouse in RF (intermediate before final delivery)
--   client        — client's final address
--
-- Compatibility: old booleans are preserved untouched for 6 months so that
-- `search_locations()` RPC + `idx_locations_hub` / `idx_locations_customs`
-- partial indexes continue to work. A follow-up migration will drop them.
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §3.1 (location types)
--   - .kiro/specs/logistics-customs-redesign/design.md §5.2 ALTER locations
--   - .kiro/specs/logistics-customs-redesign/requirements.md R15
--
-- Backfill strategy: best-effort heuristic — is_customs_point true → 'customs',
-- else is_hub true → 'hub', else → 'hub' (default). This is lossy; admins must
-- review and reclassify via scripts/audit-location-types.sql.

ALTER TABLE kvota.locations
    ADD COLUMN IF NOT EXISTS location_type VARCHAR(20);

-- Backfill from existing booleans BEFORE setting NOT NULL + CHECK
UPDATE kvota.locations
   SET location_type = CASE
       WHEN is_customs_point = true THEN 'customs'
       WHEN is_hub = true THEN 'hub'
       ELSE 'hub'  -- conservative default; admin reclassifies via audit
   END
 WHERE location_type IS NULL;

-- Now enforce NOT NULL + CHECK
ALTER TABLE kvota.locations
    ALTER COLUMN location_type SET NOT NULL,
    ALTER COLUMN location_type SET DEFAULT 'hub';

ALTER TABLE kvota.locations
    ADD CONSTRAINT locations_location_type_check
    CHECK (location_type IN ('supplier', 'hub', 'customs', 'own_warehouse', 'client'));

-- Comment
COMMENT ON COLUMN kvota.locations.location_type IS
    'Location role in route graph. Values: supplier, hub, customs, own_warehouse, client. Replaces is_hub + is_customs_point booleans (deprecated, kept for 6 months backwards compat).';

-- Index for filtering by type (common query: "give me all hub locations")
CREATE INDEX IF NOT EXISTS idx_locations_type_active
    ON kvota.locations(organization_id, location_type)
    WHERE is_active = true;

-- Update search_locations() to optionally filter by location_type.
-- Keep old p_hub_only / p_customs_only params for backwards compat — they map
-- to the new column. Add new p_location_type param (NULL = any).
CREATE OR REPLACE FUNCTION kvota.search_locations(
    p_organization_id UUID,
    p_query TEXT,
    p_limit INTEGER DEFAULT 20,
    p_hub_only BOOLEAN DEFAULT false,
    p_customs_only BOOLEAN DEFAULT false,
    p_location_type VARCHAR DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    display_name VARCHAR(255),
    country VARCHAR(100),
    city VARCHAR(100),
    code VARCHAR(10),
    is_hub BOOLEAN,
    is_customs_point BOOLEAN,
    location_type VARCHAR(20)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        l.id,
        l.display_name,
        l.country,
        l.city,
        l.code,
        l.is_hub,
        l.is_customs_point,
        l.location_type
    FROM kvota.locations l
    WHERE l.organization_id = p_organization_id
        AND l.is_active = true
        AND (p_hub_only = false OR l.location_type = 'hub')
        AND (p_customs_only = false OR l.location_type = 'customs')
        AND (p_location_type IS NULL OR l.location_type = p_location_type)
        AND (
            p_query IS NULL
            OR p_query = ''
            OR l.search_text ILIKE '%' || LOWER(p_query) || '%'
        )
    ORDER BY
        CASE WHEN l.code IS NOT NULL AND UPPER(l.code) = UPPER(p_query) THEN 0 ELSE 1 END,
        CASE WHEN l.location_type IN ('hub', 'own_warehouse') THEN 0 ELSE 1 END,
        l.display_name
    LIMIT p_limit;
END;
$$;

COMMENT ON FUNCTION kvota.search_locations IS
    'Search locations for dropdown with optional type filter. Legacy p_hub_only/p_customs_only params mapped to location_type enum for backwards compat.';

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (287, '287_locations_location_type', now())
ON CONFLICT (id) DO NOTHING;
