-- Migration: 316_logistics_segment_locations_nullable
-- Description: Drop NOT NULL on kvota.logistics_route_segments.from_location_id
--   and to_location_id so a route template with an intentionally-empty FIRST
--   (Откуда) or LAST (Куда) location can be applied without the API falling
--   back to a default location. The logistician fills the empty slots based
--   on МОЗ data after applying the template (Testing 2 row 30 #3).
-- Date: 2026-05-15
--
-- The FK references to kvota.locations(id) are preserved — a NULL value is
-- allowed by a FK column, it simply means "not linked yet". The frontend
-- already renders missing from/to locations as a placeholder chip
-- (SegmentNode), and the loader maps a NULL FK to `undefined`.

BEGIN;

SET search_path TO kvota;

ALTER TABLE kvota.logistics_route_segments
    ALTER COLUMN from_location_id DROP NOT NULL;

ALTER TABLE kvota.logistics_route_segments
    ALTER COLUMN to_location_id DROP NOT NULL;

COMMENT ON COLUMN kvota.logistics_route_segments.from_location_id IS
    'Origin location (FK to locations). Nullable since m316: an applied '
    'route template may leave the first segment''s origin empty for the '
    'logistician to fill from МОЗ data.';

COMMENT ON COLUMN kvota.logistics_route_segments.to_location_id IS
    'Destination location (FK to locations). Nullable since m316: an applied '
    'route template may leave the last segment''s destination empty for the '
    'logistician to fill from МОЗ data.';

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (316, '316_logistics_segment_locations_nullable', now())
ON CONFLICT (id) DO NOTHING;

COMMIT;
