-- ===========================================================================
-- OneStack: Add Missing Tables Migration
-- For existing Supabase with roles table using 'slug' column
-- ===========================================================================

-- ===========================================================================
-- 1. USER_ROLES TABLE (multi-role support)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    UNIQUE(user_id, organization_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_organization_id ON user_roles(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user_org ON user_roles(user_id, organization_id);

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "user_roles_select_own" ON user_roles;
CREATE POLICY "user_roles_select_own" ON user_roles FOR SELECT TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "user_roles_select_org" ON user_roles;
CREATE POLICY "user_roles_select_org" ON user_roles FOR SELECT TO authenticated
    USING (organization_id IN (SELECT organization_id FROM user_roles WHERE user_id = auth.uid()));

-- ===========================================================================
-- 2. BRAND_ASSIGNMENTS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS brand_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    brand VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    UNIQUE(organization_id, brand)
);

CREATE INDEX IF NOT EXISTS idx_brand_assignments_user_id ON brand_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_brand_assignments_org_id ON brand_assignments(organization_id);

ALTER TABLE brand_assignments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "brand_assignments_select" ON brand_assignments;
CREATE POLICY "brand_assignments_select" ON brand_assignments FOR SELECT
    USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

-- ===========================================================================
-- 3. WORKFLOW_TRANSITIONS TABLE (audit log)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS workflow_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    from_status VARCHAR(50) NOT NULL,
    to_status VARCHAR(50) NOT NULL,
    actor_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_id ON workflow_transitions(quote_id);
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_created ON workflow_transitions(quote_id, created_at DESC);

ALTER TABLE workflow_transitions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workflow_transitions_select" ON workflow_transitions;
CREATE POLICY "workflow_transitions_select" ON workflow_transitions FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM quotes q
        JOIN organization_members om ON om.organization_id = q.organization_id
        WHERE q.id = workflow_transitions.quote_id AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "workflow_transitions_insert" ON workflow_transitions;
CREATE POLICY "workflow_transitions_insert" ON workflow_transitions FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM quotes q
        JOIN organization_members om ON om.organization_id = q.organization_id
        WHERE q.id = workflow_transitions.quote_id AND om.user_id = auth.uid()
    ));

-- ===========================================================================
-- 4. APPROVALS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES auth.users(id),
    approver_id UUID NOT NULL REFERENCES auth.users(id),
    approval_type VARCHAR(50) NOT NULL DEFAULT 'top_manager',
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    decision_comment TEXT,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_approvals_quote_id ON approvals(quote_id);
CREATE INDEX IF NOT EXISTS idx_approvals_approver_status ON approvals(approver_id, status);

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "approvals_select" ON approvals;
CREATE POLICY "approvals_select" ON approvals FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM quotes q
        JOIN organization_members om ON q.organization_id = om.organization_id
        WHERE q.id = approvals.quote_id AND om.user_id = auth.uid()
    ));

DROP POLICY IF EXISTS "approvals_insert" ON approvals;
CREATE POLICY "approvals_insert" ON approvals FOR INSERT
    WITH CHECK (requested_by = auth.uid());

DROP POLICY IF EXISTS "approvals_update" ON approvals;
CREATE POLICY "approvals_update" ON approvals FOR UPDATE
    USING (approver_id = auth.uid() AND status = 'pending');

-- ===========================================================================
-- 5. SPECIFICATIONS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS specifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    quote_version_id UUID REFERENCES quote_versions(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    specification_number VARCHAR(100),
    proposal_idn VARCHAR(100),
    sign_date DATE,
    validity_period VARCHAR(100),
    specification_currency VARCHAR(10),
    exchange_rate_to_ruble DECIMAL(15, 6),
    client_payment_terms TEXT,
    cargo_pickup_country VARCHAR(100),
    readiness_period VARCHAR(100),
    delivery_city_russia VARCHAR(255),
    cargo_type VARCHAR(100),
    logistics_period VARCHAR(100),
    our_legal_entity VARCHAR(255),
    client_legal_entity VARCHAR(255),
    signed_scan_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_review', 'approved', 'signed')),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_specifications_quote_id ON specifications(quote_id);
CREATE INDEX IF NOT EXISTS idx_specifications_organization_id ON specifications(organization_id);
CREATE INDEX IF NOT EXISTS idx_specifications_org_status ON specifications(organization_id, status);

ALTER TABLE specifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "specifications_select" ON specifications;
CREATE POLICY "specifications_select" ON specifications FOR SELECT
    USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "specifications_insert" ON specifications;
CREATE POLICY "specifications_insert" ON specifications FOR INSERT
    WITH CHECK (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "specifications_update" ON specifications;
CREATE POLICY "specifications_update" ON specifications FOR UPDATE
    USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

-- ===========================================================================
-- 6. DEALS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    specification_id UUID NOT NULL REFERENCES specifications(id) ON DELETE RESTRICT,
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    deal_number VARCHAR(100) NOT NULL,
    signed_at DATE NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(specification_id)
);

CREATE INDEX IF NOT EXISTS idx_deals_organization_id ON deals(organization_id);
CREATE INDEX IF NOT EXISTS idx_deals_org_status ON deals(organization_id, status);

ALTER TABLE deals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "deals_select" ON deals;
CREATE POLICY "deals_select" ON deals FOR SELECT
    USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "deals_insert" ON deals;
CREATE POLICY "deals_insert" ON deals FOR INSERT
    WITH CHECK (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

DROP POLICY IF EXISTS "deals_update" ON deals;
CREATE POLICY "deals_update" ON deals FOR UPDATE
    USING (organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid()));

-- ===========================================================================
-- 7. PLAN_FACT_CATEGORIES TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS plan_fact_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    is_income BOOLEAN NOT NULL DEFAULT false,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

ALTER TABLE plan_fact_categories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "plan_fact_categories_select" ON plan_fact_categories;
CREATE POLICY "plan_fact_categories_select" ON plan_fact_categories FOR SELECT TO authenticated USING (true);

-- Seed categories
INSERT INTO plan_fact_categories (code, name, is_income, sort_order) VALUES
    ('client_payment', 'Оплата от клиента', true, 1),
    ('supplier_payment', 'Оплата поставщику', false, 2),
    ('logistics', 'Логистика', false, 3),
    ('customs', 'Таможня', false, 4),
    ('tax', 'Налоги', false, 5),
    ('finance_commission', 'Банковская комиссия', false, 6),
    ('other', 'Прочее', false, 7)
ON CONFLICT (code) DO NOTHING;

-- ===========================================================================
-- 8. PLAN_FACT_ITEMS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS plan_fact_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES plan_fact_categories(id) ON DELETE RESTRICT,
    description TEXT,
    planned_amount DECIMAL(15, 2) NOT NULL,
    planned_currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    planned_date DATE NOT NULL,
    actual_amount DECIMAL(15, 2),
    actual_currency VARCHAR(10),
    actual_date DATE,
    actual_exchange_rate DECIMAL(15, 6),
    variance_amount DECIMAL(15, 2),
    payment_document VARCHAR(255),
    notes TEXT,
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_id ON plan_fact_items(deal_id);

ALTER TABLE plan_fact_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "plan_fact_items_select" ON plan_fact_items;
CREATE POLICY "plan_fact_items_select" ON plan_fact_items FOR SELECT
    USING (deal_id IN (
        SELECT d.id FROM deals d
        WHERE d.organization_id IN (SELECT organization_id FROM organization_members WHERE user_id = auth.uid())
    ));

-- ===========================================================================
-- 9. TELEGRAM_USERS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS telegram_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL UNIQUE,
    telegram_username VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(32),
    verification_code_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_telegram_users_user_id ON telegram_users(user_id);

ALTER TABLE telegram_users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "telegram_users_select_own" ON telegram_users;
CREATE POLICY "telegram_users_select_own" ON telegram_users FOR SELECT TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "telegram_users_insert_own" ON telegram_users;
CREATE POLICY "telegram_users_insert_own" ON telegram_users FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "telegram_users_update_own" ON telegram_users;
CREATE POLICY "telegram_users_update_own" ON telegram_users FOR UPDATE TO authenticated
    USING (user_id = auth.uid());

-- ===========================================================================
-- 10. NOTIFICATIONS TABLE
-- ===========================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    quote_id UUID REFERENCES quotes(id) ON DELETE SET NULL,
    deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    channel VARCHAR(20) NOT NULL DEFAULT 'telegram',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    telegram_message_id BIGINT,
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_user_status ON notifications(user_id, status);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "notifications_select_own" ON notifications;
CREATE POLICY "notifications_select_own" ON notifications FOR SELECT
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS "notifications_update_own" ON notifications;
CREATE POLICY "notifications_update_own" ON notifications FOR UPDATE
    USING (user_id = auth.uid());

-- ===========================================================================
-- 11. EXTEND QUOTES TABLE
-- ===========================================================================
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS workflow_status VARCHAR(50) DEFAULT 'draft';
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS deal_type VARCHAR(20);
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS assigned_procurement_users UUID[] DEFAULT '{}';
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS assigned_logistics_user UUID;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS assigned_customs_user UUID;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS customs_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE quotes ADD COLUMN IF NOT EXISTS current_version_id UUID;

CREATE INDEX IF NOT EXISTS idx_quotes_workflow_status ON quotes(workflow_status);
CREATE INDEX IF NOT EXISTS idx_quotes_org_workflow ON quotes(organization_id, workflow_status);

-- ===========================================================================
-- 12. EXTEND QUOTE_ITEMS TABLE
-- ===========================================================================
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS assigned_procurement_user UUID;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS procurement_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS procurement_completed_by UUID;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS hs_code VARCHAR(20);
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS customs_duty DECIMAL(15, 4) DEFAULT 0;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS customs_extra DECIMAL(15, 2) DEFAULT 0;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS supplier_city VARCHAR(255);
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS production_time_days INTEGER DEFAULT 0;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS supplier_payment_terms TEXT;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS payer_company VARCHAR(255);
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS advance_to_supplier_percent DECIMAL(5, 2) DEFAULT 100;
ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS procurement_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_user ON quote_items(assigned_procurement_user) WHERE assigned_procurement_user IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_status ON quote_items(procurement_status);

-- ===========================================================================
-- DONE!
-- ===========================================================================
