-- Audit script: review location_type backfill done by migration 287.
-- Run: psql -f scripts/audit-location-types.sql (or paste into Supabase SQL editor)
--
-- Purpose: migration 287 backfilled `location_type` heuristically from
-- `is_hub`/`is_customs_point` booleans. Some rows likely need manual
-- reclassification into 'supplier' / 'own_warehouse' / 'client' based on
-- name/address patterns.
--
-- This script prints suspicious rows — admin reviews and issues targeted
-- UPDATE statements.

-- =============================================================================
-- 1. Likely misclassified: name hints at supplier/factory but set to 'hub'
-- =============================================================================

SELECT
    'LIKELY SUPPLIER (guessed hub)' AS issue,
    id,
    country,
    city,
    code,
    notes,
    location_type,
    is_hub,
    is_customs_point
FROM kvota.locations
WHERE location_type = 'hub'
  AND is_active = true
  AND (
      LOWER(COALESCE(notes, '')) SIMILAR TO '%(фабрика|завод|factory|производитель|producer|manufacturer|mfg)%'
      OR LOWER(COALESCE(code, '')) SIMILAR TO '%(fab|factory|mfg)%'
  )
ORDER BY organization_id, country, city;

-- =============================================================================
-- 2. Likely own_warehouse: name hints at "our warehouse" but set to 'hub'
-- =============================================================================

SELECT
    'LIKELY OWN_WAREHOUSE (guessed hub)' AS issue,
    id,
    country,
    city,
    code,
    notes,
    location_type
FROM kvota.locations
WHERE location_type = 'hub'
  AND is_active = true
  AND (
      LOWER(COALESCE(notes, '')) SIMILAR TO '%(наш склад|свой склад|собственный склад|own warehouse|own whs)%'
      OR LOWER(COALESCE(code, '')) SIMILAR TO '%(own|whs|скл)%'
  )
ORDER BY organization_id, country, city;

-- =============================================================================
-- 3. Likely client: name hints at specific company address (delivery point)
-- =============================================================================

SELECT
    'LIKELY CLIENT (guessed hub)' AS issue,
    id,
    country,
    city,
    code,
    notes,
    address,
    location_type
FROM kvota.locations
WHERE location_type = 'hub'
  AND is_active = true
  AND address IS NOT NULL
  AND LENGTH(TRIM(address)) > 10
  AND LOWER(COALESCE(notes, '')) NOT SIMILAR TO '%(порт|хаб|терминал|svh|port|hub|terminal)%'
ORDER BY organization_id, country, city;

-- =============================================================================
-- 4. Summary by location_type (should look balanced)
-- =============================================================================

SELECT
    location_type,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE is_active) AS active,
    COUNT(DISTINCT country) AS countries,
    COUNT(DISTINCT organization_id) AS orgs
FROM kvota.locations
GROUP BY location_type
ORDER BY total DESC;

-- =============================================================================
-- 5. Example reclassification commands (copy, paste, adjust):
-- =============================================================================
-- UPDATE kvota.locations SET location_type = 'supplier' WHERE id = '<uuid>';
-- UPDATE kvota.locations SET location_type = 'own_warehouse' WHERE id = '<uuid>';
-- UPDATE kvota.locations SET location_type = 'client' WHERE id = '<uuid>';
