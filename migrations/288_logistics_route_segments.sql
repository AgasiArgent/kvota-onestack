-- Migration 288: Logistics route segments + segment expenses.
-- Wave 1 Task 4.1 of logistics-customs-redesign spec (Requirements R5, R6).
--
-- Replaces the deprecated 7-stage fixed model (m163 logistics_stages) with a
-- flexible per-invoice route constructor:
--   - logistics_route_segments     — ordered chain per invoice
--   - logistics_segment_expenses   — freeform cost lines inside a segment
--
-- Calc engine reads through view v_logistics_plan_fact_items (created later
-- in migration 290). Old logistics_stages table preserved read-only for
-- historical deals (hybrid approach, design §9.5).
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §5.1 table defs
--   - .kiro/specs/logistics-customs-redesign/requirements.md R5, R6
--   - .kiro/specs/logistics-customs-redesign/design.md §3.1 per-invoice model

-- =============================================================================
-- logistics_route_segments — pricing nodes (per-invoice)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.logistics_route_segments (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id        UUID NOT NULL REFERENCES kvota.invoices(id) ON DELETE CASCADE,
    sequence_order    INT  NOT NULL,
    from_location_id  UUID NOT NULL REFERENCES kvota.locations(id),
    to_location_id    UUID NOT NULL REFERENCES kvota.locations(id),
    label             TEXT,
    transit_days      INT,
    main_cost_rub     DECIMAL(15, 2) NOT NULL DEFAULT 0 CHECK (main_cost_rub >= 0),
    carrier           TEXT,
    notes             TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    created_by        UUID REFERENCES auth.users(id),
    UNIQUE (invoice_id, sequence_order)
);

COMMENT ON TABLE kvota.logistics_route_segments IS
    'Per-invoice logistics route segments. Ordered chain (supplier → hub → customs → client etc). Replaces fixed-7-stage logistics_stages.';
COMMENT ON COLUMN kvota.logistics_route_segments.invoice_id IS 'One route per invoice (supports 2+ suppliers with different paths).';
COMMENT ON COLUMN kvota.logistics_route_segments.sequence_order IS '1-based order within the invoice''s route.';
COMMENT ON COLUMN kvota.logistics_route_segments.main_cost_rub IS 'Main transport cost in RUB. Additional expenses in logistics_segment_expenses.';

CREATE INDEX IF NOT EXISTS idx_logistics_route_segments_invoice_id
    ON kvota.logistics_route_segments(invoice_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION kvota.logistics_route_segments_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_logistics_route_segments_updated_at
    ON kvota.logistics_route_segments;
CREATE TRIGGER trg_logistics_route_segments_updated_at
    BEFORE UPDATE ON kvota.logistics_route_segments
    FOR EACH ROW EXECUTE FUNCTION kvota.logistics_route_segments_timestamp();

-- RLS
ALTER TABLE kvota.logistics_route_segments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "segments_org_members_select" ON kvota.logistics_route_segments
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.invoices i
            JOIN kvota.quotes q ON q.id = i.quote_id
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            WHERE i.id = logistics_route_segments.invoice_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "segments_logistics_admin_mutate" ON kvota.logistics_route_segments
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.invoices i
            JOIN kvota.quotes q ON q.id = i.quote_id
            JOIN kvota.user_roles ur ON ur.organization_id = q.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE i.id = logistics_route_segments.invoice_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('logistics', 'head_of_logistics', 'admin')
        )
    );

-- =============================================================================
-- logistics_segment_expenses — freeform costs within a segment
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.logistics_segment_expenses (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    segment_id UUID NOT NULL REFERENCES kvota.logistics_route_segments(id) ON DELETE CASCADE,
    label      TEXT NOT NULL,
    cost_rub   DECIMAL(15, 2) NOT NULL DEFAULT 0 CHECK (cost_rub >= 0),
    days       INT,
    notes      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE kvota.logistics_segment_expenses IS
    'Freeform extra costs inside a route segment (СВХ, re-paperwork, insurance, etc). Multiple rows per segment allowed. RUB only.';

CREATE INDEX IF NOT EXISTS idx_logistics_segment_expenses_segment_id
    ON kvota.logistics_segment_expenses(segment_id);

ALTER TABLE kvota.logistics_segment_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "segment_expenses_org_members_select" ON kvota.logistics_segment_expenses
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.logistics_route_segments rs
            JOIN kvota.invoices i ON i.id = rs.invoice_id
            JOIN kvota.quotes q ON q.id = i.quote_id
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            WHERE rs.id = logistics_segment_expenses.segment_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "segment_expenses_logistics_admin_mutate" ON kvota.logistics_segment_expenses
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.logistics_route_segments rs
            JOIN kvota.invoices i ON i.id = rs.invoice_id
            JOIN kvota.quotes q ON q.id = i.quote_id
            JOIN kvota.user_roles ur ON ur.organization_id = q.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE rs.id = logistics_segment_expenses.segment_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('logistics', 'head_of_logistics', 'admin')
        )
    );

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (288, '288_logistics_route_segments', now())
ON CONFLICT (id) DO NOTHING;
