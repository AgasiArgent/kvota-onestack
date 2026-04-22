-- Migration 289: Logistics operational events (per-deal) + route templates.
-- Wave 1 Task 4.2 of logistics-customs-redesign spec (Requirements R5.5-7, R6.1-2).
--
-- Three tables:
--   - logistics_operational_events       — status-only events per-deal
--                                          (gtd_uploaded, customs_cleared, delivered)
--                                          Separate from pricing (§3.2 design decision).
--   - logistics_route_templates          — org-scoped reusable route scaffolds
--   - logistics_route_template_segments  — typed scaffold segments
--                                          (stores location_type, not concrete location id)
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §3.2 operational vs pricing
--   - .kiro/specs/logistics-customs-redesign/design.md §5.1 table defs
--   - .kiro/specs/logistics-customs-redesign/design.md §3.13 templates CRUD by logistics

-- =============================================================================
-- logistics_operational_events — per-deal status events
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.logistics_operational_events (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id    UUID NOT NULL REFERENCES kvota.deals(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'in_progress', 'completed')),
    event_date TIMESTAMPTZ,
    notes      TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE kvota.logistics_operational_events IS
    'Per-deal operational status markers (ГТД загружена, таможня пройдена, доставлено). Separate from pricing segments for clear responsibility split.';
COMMENT ON COLUMN kvota.logistics_operational_events.event_type IS
    'Free-form type slug. Conventions: gtd_uploaded, customs_cleared, delivered, procurement_data_changed (smart-delta audit).';

CREATE INDEX IF NOT EXISTS idx_logistics_operational_events_deal_id
    ON kvota.logistics_operational_events(deal_id, event_type);

ALTER TABLE kvota.logistics_operational_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "op_events_org_members_select" ON kvota.logistics_operational_events
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.deals d
            JOIN kvota.quotes q ON q.id = d.specification_id
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            WHERE d.id = logistics_operational_events.deal_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "op_events_logistics_admin_mutate" ON kvota.logistics_operational_events
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.deals d
            JOIN kvota.quotes q ON q.id = d.specification_id
            JOIN kvota.user_roles ur ON ur.organization_id = q.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE d.id = logistics_operational_events.deal_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('logistics', 'customs', 'head_of_logistics', 'head_of_customs', 'admin')
        )
    );

-- =============================================================================
-- logistics_route_templates — reusable route scaffolds (org-scoped)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.logistics_route_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    created_by      UUID REFERENCES auth.users(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (organization_id, name)
);

COMMENT ON TABLE kvota.logistics_route_templates IS
    'Org-scoped reusable logistics route scaffolds. CRUD by logistics / head_of_logistics / admin roles.';

CREATE INDEX IF NOT EXISTS idx_logistics_route_templates_org
    ON kvota.logistics_route_templates(organization_id);

ALTER TABLE kvota.logistics_route_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "templates_org_members_select" ON kvota.logistics_route_templates
    FOR SELECT TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "templates_logistics_admin_mutate" ON kvota.logistics_route_templates
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND ur.organization_id = logistics_route_templates.organization_id
              AND r.slug IN ('logistics', 'head_of_logistics', 'admin')
        )
    );

-- updated_at trigger
DROP TRIGGER IF EXISTS trg_logistics_route_templates_updated_at
    ON kvota.logistics_route_templates;
CREATE TRIGGER trg_logistics_route_templates_updated_at
    BEFORE UPDATE ON kvota.logistics_route_templates
    FOR EACH ROW EXECUTE FUNCTION kvota.set_updated_at();

-- =============================================================================
-- logistics_route_template_segments — scaffold segments (location types)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.logistics_route_template_segments (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id        UUID NOT NULL REFERENCES kvota.logistics_route_templates(id) ON DELETE CASCADE,
    sequence_order     INT NOT NULL,
    from_location_type VARCHAR(20) NOT NULL
        CHECK (from_location_type IN ('supplier', 'hub', 'customs', 'own_warehouse', 'client')),
    to_location_type   VARCHAR(20) NOT NULL
        CHECK (to_location_type IN ('supplier', 'hub', 'customs', 'own_warehouse', 'client')),
    default_label      TEXT,
    default_days       INT,
    UNIQUE (template_id, sequence_order)
);

COMMENT ON TABLE kvota.logistics_route_template_segments IS
    'Template scaffold: stores location_type pairs (not concrete locations). Logistician picks concrete locations when applying template.';

CREATE INDEX IF NOT EXISTS idx_logistics_route_template_segments_tpl
    ON kvota.logistics_route_template_segments(template_id, sequence_order);

ALTER TABLE kvota.logistics_route_template_segments ENABLE ROW LEVEL SECURITY;

-- RLS through template — same permissions as parent
CREATE POLICY "template_segments_org_members_select" ON kvota.logistics_route_template_segments
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM kvota.logistics_route_templates t
            JOIN kvota.organization_members om ON om.organization_id = t.organization_id
            WHERE t.id = logistics_route_template_segments.template_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "template_segments_logistics_admin_mutate" ON kvota.logistics_route_template_segments
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.logistics_route_templates t
            JOIN kvota.user_roles ur ON ur.organization_id = t.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE t.id = logistics_route_template_segments.template_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('logistics', 'head_of_logistics', 'admin')
        )
    );

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (289, '289_logistics_operational_and_templates', now())
ON CONFLICT (id) DO NOTHING;
