-- Migration: 024_create_locations_table.sql
-- Description: Справочник локаций (города/страны) для выпадающих списков с поиском
-- Feature: DB-007
-- Created: 2026-01-15

-- =====================================================
-- EXTENSION: pg_trgm for trigram-based search
-- Required for gin_trgm_ops index on search_text
-- =====================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =====================================================
-- LOCATIONS TABLE
-- Используется для dropdown с поиском при выборе локации
-- забора/доставки в quote_items (pickup_location_id)
-- =====================================================

CREATE TABLE IF NOT EXISTS locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Location identification
    country VARCHAR(100) NOT NULL,
    city VARCHAR(100),
    code VARCHAR(10),  -- Short code for quick selection (e.g., "MSK", "SPB", "SH")

    -- Full address (optional, for specific pickup points)
    address TEXT,

    -- Classification
    is_hub BOOLEAN DEFAULT false,  -- Is this a logistics hub?
    is_customs_point BOOLEAN DEFAULT false,  -- Is this a customs clearance point?
    is_active BOOLEAN DEFAULT true,

    -- Search optimization
    display_name VARCHAR(255) GENERATED ALWAYS AS (
        CASE
            WHEN code IS NOT NULL AND city IS NOT NULL THEN code || ' - ' || city || ', ' || country
            WHEN city IS NOT NULL THEN city || ', ' || country
            ELSE country
        END
    ) STORED,

    -- Search text (lowercase, for faster searching)
    search_text VARCHAR(500) GENERATED ALWAYS AS (
        LOWER(
            COALESCE(code, '') || ' ' ||
            COALESCE(city, '') || ' ' ||
            country || ' ' ||
            COALESCE(address, '')
        )
    ) STORED,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id)
);

-- Comments
COMMENT ON TABLE locations IS 'Справочник локаций для dropdown-поиска в формах';
COMMENT ON COLUMN locations.code IS 'Короткий код локации (MSK, SPB, SH)';
COMMENT ON COLUMN locations.is_hub IS 'Является ли логистическим хабом';
COMMENT ON COLUMN locations.is_customs_point IS 'Является ли пунктом таможенной очистки';
COMMENT ON COLUMN locations.display_name IS 'Computed display name for UI';
COMMENT ON COLUMN locations.search_text IS 'Lowercase search text for fast matching';

-- =====================================================
-- INDEXES
-- =====================================================

-- Primary search index on search_text for LIKE queries
CREATE INDEX idx_locations_search_text ON locations USING gin(search_text gin_trgm_ops);

-- Exact match indexes
CREATE INDEX idx_locations_organization ON locations(organization_id);
CREATE INDEX idx_locations_country ON locations(country);
CREATE INDEX idx_locations_city ON locations(city);
CREATE INDEX idx_locations_code ON locations(code);
CREATE INDEX idx_locations_active ON locations(organization_id, is_active) WHERE is_active = true;
CREATE INDEX idx_locations_hub ON locations(organization_id, is_hub) WHERE is_hub = true;
CREATE INDEX idx_locations_customs ON locations(organization_id, is_customs_point) WHERE is_customs_point = true;

-- Composite index for common query pattern
CREATE INDEX idx_locations_org_display ON locations(organization_id, display_name) WHERE is_active = true;

-- =====================================================
-- RLS POLICIES
-- =====================================================

ALTER TABLE locations ENABLE ROW LEVEL SECURITY;

-- Users can view locations in their organization
CREATE POLICY "Users can view own organization locations"
    ON locations FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles
            WHERE user_id = auth.uid()
        )
    );

-- Admin can manage locations
CREATE POLICY "Admin can insert locations"
    ON locations FOR INSERT
    TO authenticated
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.code = 'admin'
        )
    );

CREATE POLICY "Admin can update locations"
    ON locations FOR UPDATE
    TO authenticated
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.code = 'admin'
        )
    );

CREATE POLICY "Admin can delete locations"
    ON locations FOR DELETE
    TO authenticated
    USING (
        organization_id IN (
            SELECT ur.organization_id FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid() AND r.code = 'admin'
        )
    );

-- =====================================================
-- HELPER FUNCTION: Search locations
-- =====================================================

CREATE OR REPLACE FUNCTION search_locations(
    p_organization_id UUID,
    p_query TEXT,
    p_limit INTEGER DEFAULT 20,
    p_hub_only BOOLEAN DEFAULT false,
    p_customs_only BOOLEAN DEFAULT false
)
RETURNS TABLE (
    id UUID,
    display_name VARCHAR(255),
    country VARCHAR(100),
    city VARCHAR(100),
    code VARCHAR(10),
    is_hub BOOLEAN,
    is_customs_point BOOLEAN
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
        l.is_customs_point
    FROM locations l
    WHERE l.organization_id = p_organization_id
        AND l.is_active = true
        AND (p_hub_only = false OR l.is_hub = true)
        AND (p_customs_only = false OR l.is_customs_point = true)
        AND (
            p_query IS NULL
            OR p_query = ''
            OR l.search_text ILIKE '%' || LOWER(p_query) || '%'
        )
    ORDER BY
        -- Exact code match first
        CASE WHEN l.code IS NOT NULL AND UPPER(l.code) = UPPER(p_query) THEN 0 ELSE 1 END,
        -- Hubs first
        CASE WHEN l.is_hub THEN 0 ELSE 1 END,
        -- Then alphabetically
        l.display_name
    LIMIT p_limit;
END;
$$;

COMMENT ON FUNCTION search_locations IS 'Search locations for dropdown with optional hub/customs filters';

-- =====================================================
-- TRIGGER: Update timestamp
-- =====================================================

CREATE OR REPLACE FUNCTION update_locations_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_locations_updated_at
    BEFORE UPDATE ON locations
    FOR EACH ROW
    EXECUTE FUNCTION update_locations_timestamp();

-- =====================================================
-- SEED DATA: Common locations
-- =====================================================

-- Note: Seed data should be inserted per organization after org creation
-- Below is a template for reference, not actual insertion

/*
INSERT INTO locations (organization_id, country, city, code, is_hub) VALUES
-- China
(org_id, 'Китай', 'Шанхай', 'SH', true),
(org_id, 'Китай', 'Шэньчжэнь', 'SZ', true),
(org_id, 'Китай', 'Гуанчжоу', 'GZ', true),
(org_id, 'Китай', 'Иу', 'YW', true),
(org_id, 'Китай', 'Нинбо', 'NB', true),
(org_id, 'Китай', 'Пекин', 'BJ', false),

-- Russia
(org_id, 'Россия', 'Москва', 'MSK', true),
(org_id, 'Россия', 'Санкт-Петербург', 'SPB', true),
(org_id, 'Россия', 'Владивосток', 'VVO', true),
(org_id, 'Россия', 'Новосибирск', 'OVB', false),
(org_id, 'Россия', 'Екатеринбург', 'SVX', false),

-- Customs points in Russia
(org_id, 'Россия', 'Забайкальск', 'ZBK', false),
(org_id, 'Россия', 'Благовещенск', 'BQS', false),

-- CIS
(org_id, 'Казахстан', 'Алматы', 'ALA', true),
(org_id, 'Казахстан', 'Хоргос', 'KHG', false),

-- Europe
(org_id, 'Германия', 'Гамбург', 'HAM', true),
(org_id, 'Нидерланды', 'Роттердам', 'RTM', true),

-- Other
(org_id, 'Турция', 'Стамбул', 'IST', true)
ON CONFLICT DO NOTHING;
*/

-- =====================================================
-- UTILITY: Create default locations for organization
-- =====================================================

CREATE OR REPLACE FUNCTION create_default_locations(p_organization_id UUID, p_created_by UUID DEFAULT NULL)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    -- China
    INSERT INTO locations (organization_id, country, city, code, is_hub, created_by) VALUES
    (p_organization_id, 'Китай', 'Шанхай', 'SH', true, p_created_by),
    (p_organization_id, 'Китай', 'Шэньчжэнь', 'SZ', true, p_created_by),
    (p_organization_id, 'Китай', 'Гуанчжоу', 'GZ', true, p_created_by),
    (p_organization_id, 'Китай', 'Иу', 'YW', true, p_created_by),
    (p_organization_id, 'Китай', 'Нинбо', 'NB', true, p_created_by),
    (p_organization_id, 'Китай', 'Пекин', 'BJ', false, p_created_by),
    (p_organization_id, 'Китай', 'Циндао', 'TAO', true, p_created_by),
    (p_organization_id, 'Китай', 'Тяньцзинь', 'TSN', true, p_created_by)
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_count = ROW_COUNT;

    -- Russia
    INSERT INTO locations (organization_id, country, city, code, is_hub, is_customs_point, created_by) VALUES
    (p_organization_id, 'Россия', 'Москва', 'MSK', true, false, p_created_by),
    (p_organization_id, 'Россия', 'Санкт-Петербург', 'SPB', true, false, p_created_by),
    (p_organization_id, 'Россия', 'Владивосток', 'VVO', true, true, p_created_by),
    (p_organization_id, 'Россия', 'Новосибирск', 'OVB', true, false, p_created_by),
    (p_organization_id, 'Россия', 'Екатеринбург', 'SVX', true, false, p_created_by),
    (p_organization_id, 'Россия', 'Забайкальск', 'ZBK', false, true, p_created_by),
    (p_organization_id, 'Россия', 'Благовещенск', 'BQS', false, true, p_created_by)
    ON CONFLICT DO NOTHING;
    v_count := v_count + ROW_COUNT;

    -- CIS
    INSERT INTO locations (organization_id, country, city, code, is_hub, is_customs_point, created_by) VALUES
    (p_organization_id, 'Казахстан', 'Алматы', 'ALA', true, false, p_created_by),
    (p_organization_id, 'Казахстан', 'Хоргос', 'KHG', false, true, p_created_by)
    ON CONFLICT DO NOTHING;
    v_count := v_count + ROW_COUNT;

    -- Europe
    INSERT INTO locations (organization_id, country, city, code, is_hub, created_by) VALUES
    (p_organization_id, 'Германия', 'Гамбург', 'HAM', true, p_created_by),
    (p_organization_id, 'Нидерланды', 'Роттердам', 'RTM', true, p_created_by),
    (p_organization_id, 'Италия', 'Милан', 'MXP', true, p_created_by)
    ON CONFLICT DO NOTHING;
    v_count := v_count + ROW_COUNT;

    -- Turkey
    INSERT INTO locations (organization_id, country, city, code, is_hub, created_by) VALUES
    (p_organization_id, 'Турция', 'Стамбул', 'IST', true, p_created_by)
    ON CONFLICT DO NOTHING;
    v_count := v_count + ROW_COUNT;

    RETURN v_count;
END;
$$;

COMMENT ON FUNCTION create_default_locations IS 'Creates default location entries for a new organization';
