-- ===========================================================================
-- OneStack Full Schema Migration
-- Generated: 2025-01-15
-- Description: Combined migration of all 17 feature migrations for fresh Supabase setup
-- ===========================================================================
--
-- INSTRUCTIONS:
-- 1. Create a new Supabase project at https://supabase.com/dashboard
-- 2. Go to SQL Editor
-- 3. Paste this entire file and run
-- 4. Create the "specifications" storage bucket manually (see end of file)
-- 5. Update your .env with new SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
--
-- PREREQUISITES (tables that must already exist):
-- - organizations (from base Supabase setup)
-- - organization_members (from base Supabase setup)
-- - quotes (core table)
-- - quote_items (core table)
-- - quote_versions (core table)
-- - customers (core table)
-- ===========================================================================

-- ===========================================================================
-- Migration 001: Create roles table
-- ===========================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_roles_code ON roles(code);

INSERT INTO roles (code, name, description) VALUES
    ('sales', 'Менеджер по продажам', 'Создание и ведение КП, работа с клиентами'),
    ('procurement', 'Менеджер по закупкам', 'Оценка закупочных цен по брендам'),
    ('logistics', 'Логист', 'Расчёт стоимости и сроков доставки'),
    ('customs', 'Менеджер ТО', 'Таможенное оформление, коды ТН ВЭД, пошлины'),
    ('quote_controller', 'Контроллер КП', 'Проверка КП перед отправкой клиенту'),
    ('spec_controller', 'Контроллер спецификаций', 'Подготовка и проверка спецификаций'),
    ('finance', 'Финансовый менеджер', 'Ведение план-факта по сделкам'),
    ('top_manager', 'Топ-менеджер', 'Согласование и отчётность'),
    ('admin', 'Администратор', 'Управление пользователями и настройками')
ON CONFLICT (code) DO NOTHING;

ALTER TABLE roles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "roles_select_policy" ON roles
    FOR SELECT
    TO authenticated
    USING (true);

COMMENT ON TABLE roles IS 'Reference table for user roles in the workflow system';
COMMENT ON COLUMN roles.code IS 'Unique role identifier used in code';
COMMENT ON COLUMN roles.name IS 'Human-readable role name in Russian';
COMMENT ON COLUMN roles.description IS 'Role description and responsibilities';

-- ===========================================================================
-- Migration 002: Create user_roles table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS user_roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_roles_unique
    ON user_roles(user_id, organization_id, role_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_id
    ON user_roles(user_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_organization_id
    ON user_roles(organization_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_role_id
    ON user_roles(role_id);

CREATE INDEX IF NOT EXISTS idx_user_roles_user_org
    ON user_roles(user_id, organization_id);

ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_roles_select_own" ON user_roles
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "user_roles_select_org" ON user_roles
    FOR SELECT
    TO authenticated
    USING (
        organization_id IN (
            SELECT organization_id FROM user_roles WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "user_roles_admin_insert" ON user_roles
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = organization_id
            AND r.code = 'admin'
        )
    );

CREATE POLICY "user_roles_admin_delete" ON user_roles
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = user_roles.organization_id
            AND r.code = 'admin'
        )
    );

COMMENT ON TABLE user_roles IS 'Junction table linking users to roles within organizations';
COMMENT ON COLUMN user_roles.user_id IS 'Reference to auth.users';
COMMENT ON COLUMN user_roles.organization_id IS 'Reference to organizations - roles are organization-specific';
COMMENT ON COLUMN user_roles.role_id IS 'Reference to roles table';
COMMENT ON COLUMN user_roles.created_by IS 'User who assigned this role (admin)';

-- ===========================================================================
-- Migration 003: Create brand_assignments table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS brand_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    brand VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,

    CONSTRAINT unique_brand_per_org UNIQUE (organization_id, brand)
);

CREATE INDEX IF NOT EXISTS idx_brand_assignments_user_id ON brand_assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_brand_assignments_org_id ON brand_assignments(organization_id);
CREATE INDEX IF NOT EXISTS idx_brand_assignments_org_brand ON brand_assignments(organization_id, brand);

ALTER TABLE brand_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY brand_assignments_select_policy ON brand_assignments
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY brand_assignments_insert_policy ON brand_assignments
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

CREATE POLICY brand_assignments_update_policy ON brand_assignments
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

CREATE POLICY brand_assignments_delete_policy ON brand_assignments
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = brand_assignments.organization_id
            AND r.code = 'admin'
        )
    );

COMMENT ON TABLE brand_assignments IS 'Assigns brands to procurement managers - each brand can have only one manager per organization';

-- ===========================================================================
-- Migration 004: Create workflow_transitions table
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

CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_id
    ON workflow_transitions(quote_id);
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_actor_id
    ON workflow_transitions(actor_id);
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_to_status
    ON workflow_transitions(to_status);
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_created
    ON workflow_transitions(quote_id, created_at DESC);

ALTER TABLE workflow_transitions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view transitions for their organization quotes"
    ON workflow_transitions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON om.organization_id = q.organization_id
            WHERE q.id = workflow_transitions.quote_id
            AND om.user_id = auth.uid()
        )
    );

CREATE POLICY "Authenticated users can insert transitions for their organization quotes"
    ON workflow_transitions
    FOR INSERT
    WITH CHECK (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON om.organization_id = q.organization_id
            WHERE q.id = workflow_transitions.quote_id
            AND om.user_id = auth.uid()
        )
    );

COMMENT ON TABLE workflow_transitions IS 'Audit log of all workflow status transitions for quotes';

-- ===========================================================================
-- Migration 005: Create approvals table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    requested_by UUID NOT NULL REFERENCES auth.users(id),
    approver_id UUID NOT NULL REFERENCES auth.users(id),
    approval_type VARCHAR(50) NOT NULL DEFAULT 'top_manager',
    reason TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    decision_comment TEXT,
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    decided_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT approvals_decided_at_check CHECK (
        (status = 'pending' AND decided_at IS NULL) OR
        (status != 'pending' AND decided_at IS NOT NULL)
    )
);

COMMENT ON TABLE approvals IS 'Approval requests for quotes requiring top manager or other approval';

CREATE INDEX idx_approvals_quote_id ON approvals(quote_id);
CREATE INDEX idx_approvals_requested_by ON approvals(requested_by);
CREATE INDEX idx_approvals_approver_id ON approvals(approver_id);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_requested_at ON approvals(requested_at DESC);
CREATE INDEX idx_approvals_approver_status ON approvals(approver_id, status);

ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view approvals in their organization" ON approvals
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON q.organization_id = om.organization_id
            WHERE q.id = approvals.quote_id
            AND om.user_id = auth.uid()
        )
    );

CREATE POLICY "Quote controllers can create approvals" ON approvals
    FOR INSERT
    WITH CHECK (
        requested_by = auth.uid()
        AND
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON q.organization_id = om.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = q.organization_id
            JOIN roles r ON ur.role_id = r.id AND r.code = 'quote_controller'
            WHERE q.id = approvals.quote_id
            AND om.user_id = auth.uid()
        )
    );

CREATE POLICY "Approvers can update their approvals" ON approvals
    FOR UPDATE
    USING (
        approver_id = auth.uid()
        AND status = 'pending'
    )
    WITH CHECK (
        approver_id = auth.uid()
    );

CREATE OR REPLACE FUNCTION set_approval_decided_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status != 'pending' AND OLD.status = 'pending' THEN
        NEW.decided_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_approval_decided_at
    BEFORE UPDATE ON approvals
    FOR EACH ROW
    EXECUTE FUNCTION set_approval_decided_at();

-- ===========================================================================
-- Migration 006: Create specifications table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS specifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    quote_version_id UUID REFERENCES quote_versions(id) ON DELETE SET NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    specification_number VARCHAR(100),
    proposal_idn VARCHAR(100),
    item_ind_sku VARCHAR(100),
    sign_date DATE,
    validity_period VARCHAR(100),
    specification_currency VARCHAR(10),
    exchange_rate_to_ruble DECIMAL(15, 6),
    client_payment_term_after_upd INTEGER,
    client_payment_terms TEXT,
    cargo_pickup_country VARCHAR(100),
    readiness_period VARCHAR(100),
    goods_shipment_country VARCHAR(100),
    delivery_city_russia VARCHAR(255),
    cargo_type VARCHAR(100),
    logistics_period VARCHAR(100),
    our_legal_entity VARCHAR(255),
    client_legal_entity VARCHAR(255),
    supplier_payment_country VARCHAR(100),
    signed_scan_url TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'pending_review', 'approved', 'signed')),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE specifications IS 'Specification data for quotes ready to be sent to clients';

CREATE INDEX IF NOT EXISTS idx_specifications_quote_id ON specifications(quote_id);
CREATE INDEX IF NOT EXISTS idx_specifications_organization_id ON specifications(organization_id);
CREATE INDEX IF NOT EXISTS idx_specifications_status ON specifications(status);
CREATE INDEX IF NOT EXISTS idx_specifications_created_at ON specifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_specifications_specification_number ON specifications(specification_number);
CREATE INDEX IF NOT EXISTS idx_specifications_org_status ON specifications(organization_id, status);

ALTER TABLE specifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view specifications in their organization"
    ON specifications
    FOR SELECT
    USING (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert specifications in their organization"
    ON specifications
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update specifications in their organization"
    ON specifications
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    )
    WITH CHECK (
        organization_id IN (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = auth.uid()
        )
    );

CREATE POLICY "Admins can delete specifications"
    ON specifications
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = specifications.organization_id
            AND r.code = 'admin'
        )
    );

CREATE OR REPLACE FUNCTION update_specifications_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_specifications_updated_at
    BEFORE UPDATE ON specifications
    FOR EACH ROW
    EXECUTE FUNCTION update_specifications_updated_at();

-- ===========================================================================
-- Migration 007: Create deals table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.deals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    specification_id UUID NOT NULL REFERENCES public.specifications(id) ON DELETE RESTRICT,
    quote_id UUID NOT NULL REFERENCES public.quotes(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
    deal_number VARCHAR(100) NOT NULL,
    signed_at DATE NOT NULL,
    total_amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    created_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE public.deals IS 'Сделки - подписанные спецификации с финансовым учётом';

CREATE INDEX IF NOT EXISTS idx_deals_specification_id ON public.deals(specification_id);
CREATE INDEX IF NOT EXISTS idx_deals_quote_id ON public.deals(quote_id);
CREATE INDEX IF NOT EXISTS idx_deals_organization_id ON public.deals(organization_id);
CREATE INDEX IF NOT EXISTS idx_deals_status ON public.deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_signed_at ON public.deals(signed_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_deal_number ON public.deals(deal_number);
CREATE INDEX IF NOT EXISTS idx_deals_created_at ON public.deals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_org_status ON public.deals(organization_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_deals_unique_specification ON public.deals(specification_id);

ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view deals in their organization"
    ON public.deals
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
    );

CREATE POLICY "Authorized users can create deals"
    ON public.deals
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
        AND (
            EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = public.deals.organization_id
                AND r.code IN ('spec_controller', 'admin')
            )
        )
    );

CREATE POLICY "Finance users can update deals"
    ON public.deals
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id FROM public.organization_members
            WHERE user_id = auth.uid()
        )
        AND (
            EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = public.deals.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

CREATE POLICY "Only admins can delete deals"
    ON public.deals
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.user_roles ur
            JOIN public.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND ur.organization_id = public.deals.organization_id
            AND r.code = 'admin'
        )
    );

CREATE OR REPLACE FUNCTION public.update_deals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_deals_updated_at
    BEFORE UPDATE ON public.deals
    FOR EACH ROW
    EXECUTE FUNCTION public.update_deals_updated_at();

CREATE OR REPLACE FUNCTION public.generate_deal_number(org_id UUID)
RETURNS TEXT AS $$
DECLARE
    year_prefix TEXT;
    seq_num INT;
    deal_num TEXT;
BEGIN
    year_prefix := TO_CHAR(CURRENT_DATE, 'YYYY');
    SELECT COUNT(*) + 1 INTO seq_num
    FROM public.deals
    WHERE organization_id = org_id
    AND EXTRACT(YEAR FROM signed_at) = EXTRACT(YEAR FROM CURRENT_DATE);
    deal_num := 'DEAL-' || year_prefix || '-' || LPAD(seq_num::TEXT, 4, '0');
    RETURN deal_num;
END;
$$ LANGUAGE plpgsql;

-- ===========================================================================
-- Migration 008: Create plan_fact_categories table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS plan_fact_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    is_income BOOLEAN NOT NULL DEFAULT false,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE plan_fact_categories IS 'Reference table for payment categories in plan-fact financial tracking';

CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_code ON plan_fact_categories(code);
CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_is_income ON plan_fact_categories(is_income);
CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_sort_order ON plan_fact_categories(sort_order);

ALTER TABLE plan_fact_categories ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view all payment categories"
    ON plan_fact_categories
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Only admins can insert payment categories"
    ON plan_fact_categories
    FOR INSERT
    TO authenticated
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

CREATE POLICY "Only admins can update payment categories"
    ON plan_fact_categories
    FOR UPDATE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

CREATE POLICY "Only admins can delete payment categories"
    ON plan_fact_categories
    FOR DELETE
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
        )
    );

-- ===========================================================================
-- Migration 009: Create plan_fact_items table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS public.plan_fact_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deal_id UUID NOT NULL REFERENCES public.deals(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES public.plan_fact_categories(id) ON DELETE RESTRICT,
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

COMMENT ON TABLE public.plan_fact_items IS 'Записи план-факта - плановые и фактические платежи по сделкам';

CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_id ON public.plan_fact_items(deal_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_category_id ON public.plan_fact_items(category_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_planned_date ON public.plan_fact_items(planned_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_actual_date ON public.plan_fact_items(actual_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_created_at ON public.plan_fact_items(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_category ON public.plan_fact_items(deal_id, category_id);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_deal_planned_date ON public.plan_fact_items(deal_id, planned_date);
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_unpaid ON public.plan_fact_items(deal_id) WHERE actual_amount IS NULL;

ALTER TABLE public.plan_fact_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view plan_fact_items in their organization"
    ON public.plan_fact_items
    FOR SELECT
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT organization_id FROM public.organization_members
                WHERE user_id = auth.uid()
            )
        )
    );

CREATE POLICY "Finance users can create plan_fact_items"
    ON public.plan_fact_items
    FOR INSERT
    WITH CHECK (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT om.organization_id FROM public.organization_members om
                WHERE om.user_id = auth.uid()
            )
            AND EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

CREATE POLICY "Finance users can update plan_fact_items"
    ON public.plan_fact_items
    FOR UPDATE
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE d.organization_id IN (
                SELECT om.organization_id FROM public.organization_members om
                WHERE om.user_id = auth.uid()
            )
            AND EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code IN ('finance', 'admin')
            )
        )
    );

CREATE POLICY "Only admins can delete plan_fact_items"
    ON public.plan_fact_items
    FOR DELETE
    USING (
        deal_id IN (
            SELECT d.id FROM public.deals d
            WHERE EXISTS (
                SELECT 1 FROM public.user_roles ur
                JOIN public.roles r ON ur.role_id = r.id
                WHERE ur.user_id = auth.uid()
                AND ur.organization_id = d.organization_id
                AND r.code = 'admin'
            )
        )
    );

CREATE OR REPLACE FUNCTION public.update_plan_fact_items_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_plan_fact_items_updated_at
    BEFORE UPDATE ON public.plan_fact_items
    FOR EACH ROW
    EXECUTE FUNCTION public.update_plan_fact_items_updated_at();

CREATE OR REPLACE FUNCTION public.calculate_plan_fact_variance()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.actual_amount IS NOT NULL AND NEW.actual_date IS NOT NULL THEN
        IF NEW.actual_currency = 'RUB' OR NEW.actual_currency IS NULL THEN
            NEW.variance_amount := NEW.actual_amount - NEW.planned_amount;
        ELSE
            IF NEW.actual_exchange_rate IS NOT NULL AND NEW.actual_exchange_rate > 0 THEN
                NEW.variance_amount := (NEW.actual_amount * NEW.actual_exchange_rate) - NEW.planned_amount;
            ELSE
                NEW.variance_amount := NEW.actual_amount - NEW.planned_amount;
            END IF;
        END IF;
    ELSE
        NEW.variance_amount := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_calculate_variance
    BEFORE INSERT OR UPDATE ON public.plan_fact_items
    FOR EACH ROW
    EXECUTE FUNCTION public.calculate_plan_fact_variance();

-- ===========================================================================
-- Migration 010: Create telegram_users table
-- ===========================================================================

CREATE TABLE IF NOT EXISTS telegram_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL,
    telegram_username VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(32),
    verification_code_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_users_telegram_id
    ON telegram_users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_telegram_users_user_id
    ON telegram_users(user_id);
CREATE INDEX IF NOT EXISTS idx_telegram_users_verification_code
    ON telegram_users(verification_code)
    WHERE verification_code IS NOT NULL AND is_verified = FALSE;
CREATE INDEX IF NOT EXISTS idx_telegram_users_verified
    ON telegram_users(user_id)
    WHERE is_verified = TRUE;

ALTER TABLE telegram_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "telegram_users_select_own" ON telegram_users
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "telegram_users_select_admin" ON telegram_users
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
            AND ur.organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = telegram_users.user_id
            )
        )
    );

CREATE POLICY "telegram_users_insert_own" ON telegram_users
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "telegram_users_update_own" ON telegram_users
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "telegram_users_delete_own" ON telegram_users
    FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());

CREATE OR REPLACE FUNCTION generate_telegram_verification_code()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    FOR i IN 1..6 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::integer, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION request_telegram_verification(p_user_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_code TEXT;
    v_existing RECORD;
BEGIN
    SELECT * INTO v_existing FROM telegram_users
    WHERE user_id = p_user_id AND is_verified = TRUE;

    IF FOUND THEN
        RETURN NULL;
    END IF;

    v_code := generate_telegram_verification_code();

    INSERT INTO telegram_users (user_id, telegram_id, verification_code, verification_code_expires_at)
    VALUES (p_user_id, 0, v_code, NOW() + INTERVAL '30 minutes')
    ON CONFLICT (user_id)
    WHERE telegram_id = 0 OR is_verified = FALSE
    DO UPDATE SET
        verification_code = v_code,
        verification_code_expires_at = NOW() + INTERVAL '30 minutes';

    RETURN v_code;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION verify_telegram_account(
    p_verification_code TEXT,
    p_telegram_id BIGINT,
    p_telegram_username TEXT DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    user_id UUID,
    message TEXT
) AS $$
DECLARE
    v_record RECORD;
BEGIN
    SELECT * INTO v_record FROM telegram_users
    WHERE verification_code = p_verification_code
    AND is_verified = FALSE
    AND verification_code_expires_at > NOW();

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, 'Invalid or expired verification code'::TEXT;
        RETURN;
    END IF;

    IF EXISTS (SELECT 1 FROM telegram_users WHERE telegram_id = p_telegram_id AND is_verified = TRUE) THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, 'This Telegram account is already linked to another user'::TEXT;
        RETURN;
    END IF;

    UPDATE telegram_users SET
        telegram_id = p_telegram_id,
        telegram_username = p_telegram_username,
        is_verified = TRUE,
        verification_code = NULL,
        verification_code_expires_at = NULL,
        verified_at = NOW()
    WHERE id = v_record.id;

    RETURN QUERY SELECT TRUE, v_record.user_id, 'Telegram account verified successfully'::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON TABLE telegram_users IS 'Links Telegram accounts to system users for notifications and approvals';

-- ===========================================================================
-- Migration 011: Create notifications table
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
    email_message_id VARCHAR(255),
    error_message TEXT,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    CONSTRAINT valid_notification_type CHECK (
        type IN (
            'task_assigned',
            'approval_required',
            'approval_decision',
            'status_changed',
            'returned_for_revision',
            'comment_added',
            'deadline_reminder',
            'system_message'
        )
    ),
    CONSTRAINT valid_notification_channel CHECK (
        channel IN ('telegram', 'email', 'in_app')
    ),
    CONSTRAINT valid_notification_status CHECK (
        status IN ('pending', 'sent', 'delivered', 'read', 'failed')
    ),
    CONSTRAINT valid_sent_at CHECK (
        (status = 'pending' AND sent_at IS NULL) OR
        (status != 'pending' AND sent_at IS NOT NULL)
    )
);

COMMENT ON TABLE notifications IS 'History of all notifications sent to users';

CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_quote_id ON notifications(quote_id) WHERE quote_id IS NOT NULL;
CREATE INDEX idx_notifications_deal_id ON notifications(deal_id) WHERE deal_id IS NOT NULL;
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_channel ON notifications(channel);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, created_at DESC)
    WHERE status NOT IN ('read', 'failed');
CREATE INDEX idx_notifications_pending_send ON notifications(channel, created_at)
    WHERE status = 'pending';

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY notifications_select_own ON notifications
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY notifications_insert ON notifications
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM organization_members om1
            JOIN organization_members om2 ON om1.organization_id = om2.organization_id
            WHERE om1.user_id = auth.uid() AND om2.user_id = user_id
        )
    );

CREATE POLICY notifications_update_own ON notifications
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION create_notification(
    p_user_id UUID,
    p_type VARCHAR(50),
    p_title VARCHAR(255),
    p_message TEXT,
    p_channel VARCHAR(20) DEFAULT 'telegram',
    p_quote_id UUID DEFAULT NULL,
    p_deal_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_notification_id UUID;
BEGIN
    INSERT INTO notifications (
        user_id, type, title, message, channel, quote_id, deal_id, status
    ) VALUES (
        p_user_id, p_type, p_title, p_message, p_channel, p_quote_id, p_deal_id, 'pending'
    )
    RETURNING id INTO v_notification_id;

    RETURN v_notification_id;
END;
$$;

CREATE OR REPLACE FUNCTION mark_notification_sent(
    p_notification_id UUID,
    p_telegram_message_id BIGINT DEFAULT NULL,
    p_email_message_id VARCHAR(255) DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'sent',
        sent_at = NOW(),
        telegram_message_id = COALESCE(p_telegram_message_id, telegram_message_id),
        email_message_id = COALESCE(p_email_message_id, email_message_id)
    WHERE id = p_notification_id AND status = 'pending';
END;
$$;

CREATE OR REPLACE FUNCTION mark_notification_failed(
    p_notification_id UUID,
    p_error_message TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'failed',
        sent_at = NOW(),
        error_message = p_error_message
    WHERE id = p_notification_id AND status = 'pending';
END;
$$;

CREATE OR REPLACE FUNCTION mark_notification_read(
    p_notification_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'read',
        read_at = NOW()
    WHERE id = p_notification_id
    AND user_id = auth.uid()
    AND status IN ('sent', 'delivered');
END;
$$;

CREATE OR REPLACE FUNCTION get_pending_notifications(
    p_channel VARCHAR(20),
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    notification_id UUID,
    user_id UUID,
    telegram_id BIGINT,
    type VARCHAR(50),
    title VARCHAR(255),
    message TEXT,
    quote_id UUID,
    deal_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id AS notification_id,
        n.user_id,
        tu.telegram_id,
        n.type,
        n.title,
        n.message,
        n.quote_id,
        n.deal_id
    FROM notifications n
    LEFT JOIN telegram_users tu ON n.user_id = tu.user_id AND tu.is_verified = true
    WHERE n.channel = p_channel
    AND n.status = 'pending'
    ORDER BY n.created_at ASC
    LIMIT p_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION create_notification TO authenticated;
GRANT EXECUTE ON FUNCTION mark_notification_sent TO service_role;
GRANT EXECUTE ON FUNCTION mark_notification_failed TO service_role;
GRANT EXECUTE ON FUNCTION mark_notification_read TO authenticated;
GRANT EXECUTE ON FUNCTION get_pending_notifications TO service_role;

-- ===========================================================================
-- Migration 012: Extend quotes table with workflow fields
-- ===========================================================================

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS workflow_status VARCHAR(50) DEFAULT 'draft';

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS deal_type VARCHAR(20) DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_procurement_users UUID[] DEFAULT '{}';

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_logistics_user UUID DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS assigned_customs_user UUID DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS logistics_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS customs_completed_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

ALTER TABLE quotes
ADD COLUMN IF NOT EXISTS current_version_id UUID DEFAULT NULL;

ALTER TABLE quotes
DROP CONSTRAINT IF EXISTS quotes_workflow_status_check;

ALTER TABLE quotes
ADD CONSTRAINT quotes_workflow_status_check CHECK (
    workflow_status IS NULL OR
    workflow_status IN (
        'draft',
        'pending_procurement',
        'pending_logistics',
        'pending_customs',
        'pending_sales_review',
        'pending_quote_control',
        'pending_approval',
        'approved',
        'sent_to_client',
        'client_negotiation',
        'pending_spec_control',
        'pending_signature',
        'deal',
        'rejected',
        'cancelled'
    )
);

ALTER TABLE quotes
DROP CONSTRAINT IF EXISTS quotes_deal_type_check;

ALTER TABLE quotes
ADD CONSTRAINT quotes_deal_type_check CHECK (
    deal_type IS NULL OR
    deal_type IN ('supply', 'transit')
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_current_version_id_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_current_version_id_fkey
        FOREIGN KEY (current_version_id)
        REFERENCES quote_versions(id)
        ON DELETE SET NULL;
    END IF;
EXCEPTION
    WHEN undefined_table THEN
        RAISE NOTICE 'quote_versions table not found, skipping FK constraint';
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_assigned_logistics_user_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_assigned_logistics_user_fkey
        FOREIGN KEY (assigned_logistics_user)
        REFERENCES auth.users(id)
        ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quotes_assigned_customs_user_fkey'
    ) THEN
        ALTER TABLE quotes
        ADD CONSTRAINT quotes_assigned_customs_user_fkey
        FOREIGN KEY (assigned_customs_user)
        REFERENCES auth.users(id)
        ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_quotes_workflow_status
ON quotes(workflow_status);

CREATE INDEX IF NOT EXISTS idx_quotes_deal_type
ON quotes(deal_type);

CREATE INDEX IF NOT EXISTS idx_quotes_assigned_logistics_user
ON quotes(assigned_logistics_user)
WHERE assigned_logistics_user IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quotes_assigned_customs_user
ON quotes(assigned_customs_user)
WHERE assigned_customs_user IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quotes_organization_workflow_status
ON quotes(organization_id, workflow_status);

CREATE INDEX IF NOT EXISTS idx_quotes_assigned_procurement_users
ON quotes USING GIN(assigned_procurement_users);

UPDATE quotes
SET workflow_status = 'draft'
WHERE workflow_status IS NULL;

COMMENT ON TABLE quotes IS 'Commercial proposals (КП) with multi-role workflow support.';

-- ===========================================================================
-- Migration 013: Extend quote_items table with workflow fields
-- ===========================================================================

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS assigned_procurement_user UUID REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_status VARCHAR(20) DEFAULT 'pending';

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_completed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_completed_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS hs_code VARCHAR(20);

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_duty DECIMAL(15, 4) DEFAULT 0;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS customs_extra DECIMAL(15, 2) DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_procurement_status_check'
    ) THEN
        ALTER TABLE quote_items
        ADD CONSTRAINT quote_items_procurement_status_check
        CHECK (procurement_status IN ('pending', 'in_progress', 'completed'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_quote_items_assigned_procurement_user
ON quote_items(assigned_procurement_user)
WHERE assigned_procurement_user IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_status
ON quote_items(procurement_status);

CREATE INDEX IF NOT EXISTS idx_quote_items_procurement_user_status
ON quote_items(assigned_procurement_user, procurement_status)
WHERE assigned_procurement_user IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_quote_items_quote_procurement_status
ON quote_items(quote_id, procurement_status);

COMMENT ON COLUMN quote_items.assigned_procurement_user IS 'Procurement manager assigned to this item (based on brand)';
COMMENT ON COLUMN quote_items.procurement_status IS 'Procurement evaluation status: pending, in_progress, completed';
COMMENT ON COLUMN quote_items.procurement_completed_at IS 'When procurement evaluation was completed';
COMMENT ON COLUMN quote_items.procurement_completed_by IS 'User who completed the procurement evaluation';
COMMENT ON COLUMN quote_items.hs_code IS 'Customs HS code (ТН ВЭД) for this product';
COMMENT ON COLUMN quote_items.customs_duty IS 'Customs duty percentage or amount';
COMMENT ON COLUMN quote_items.customs_extra IS 'Additional customs-related charges';

CREATE OR REPLACE FUNCTION assign_procurement_user_by_brand()
RETURNS TRIGGER AS $$
DECLARE
    v_org_id UUID;
    v_assigned_user UUID;
BEGIN
    SELECT organization_id INTO v_org_id
    FROM quotes
    WHERE id = NEW.quote_id;

    IF NEW.brand IS NOT NULL AND v_org_id IS NOT NULL THEN
        SELECT user_id INTO v_assigned_user
        FROM brand_assignments
        WHERE organization_id = v_org_id
          AND LOWER(brand) = LOWER(NEW.brand);

        IF v_assigned_user IS NOT NULL THEN
            NEW.assigned_procurement_user := v_assigned_user;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trigger_assign_procurement_user ON quote_items;
CREATE TRIGGER trigger_assign_procurement_user
    BEFORE INSERT OR UPDATE OF brand ON quote_items
    FOR EACH ROW
    WHEN (NEW.brand IS NOT NULL)
    EXECUTE FUNCTION assign_procurement_user_by_brand();

CREATE OR REPLACE FUNCTION complete_item_procurement(
    p_item_id UUID,
    p_user_id UUID
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE quote_items
    SET procurement_status = 'completed',
        procurement_completed_at = NOW(),
        procurement_completed_by = p_user_id
    WHERE id = p_item_id
      AND assigned_procurement_user = p_user_id
      AND procurement_status != 'completed';

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION check_quote_procurement_complete(p_quote_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_pending_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO v_pending_count
    FROM quote_items
    WHERE quote_id = p_quote_id
      AND procurement_status != 'completed';

    RETURN v_pending_count = 0;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION assign_procurement_user_by_brand() TO authenticated;
GRANT EXECUTE ON FUNCTION complete_item_procurement(UUID, UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION check_quote_procurement_complete(UUID) TO authenticated;

-- ===========================================================================
-- Migration 014: Seed plan_fact_categories
-- ===========================================================================

INSERT INTO plan_fact_categories (code, name, is_income, sort_order) VALUES
    ('client_payment', 'Оплата от клиента', true, 1),
    ('supplier_payment', 'Оплата поставщику', false, 2),
    ('logistics', 'Логистика', false, 3),
    ('customs', 'Таможня', false, 4),
    ('tax', 'Налоги', false, 5),
    ('finance_commission', 'Банковская комиссия', false, 6),
    ('other', 'Прочее', false, 7)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    is_income = EXCLUDED.is_income,
    sort_order = EXCLUDED.sort_order;

-- ===========================================================================
-- Migration 015: Verify RLS policies - Helper functions
-- ===========================================================================

CREATE OR REPLACE FUNCTION public.user_has_role_in_org(
    p_user_id UUID,
    p_org_id UUID,
    p_role_codes TEXT[]
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = p_user_id
          AND ur.organization_id = p_org_id
          AND r.code = ANY(p_role_codes)
    );
END;
$$;

COMMENT ON FUNCTION public.user_has_role_in_org IS 'Check if a user has any of the specified roles in an organization';
GRANT EXECUTE ON FUNCTION public.user_has_role_in_org TO authenticated;

CREATE OR REPLACE FUNCTION public.user_organization_ids(p_user_id UUID DEFAULT NULL)
RETURNS UUID[]
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
DECLARE
    v_user_id UUID;
BEGIN
    v_user_id := COALESCE(p_user_id, auth.uid());
    RETURN ARRAY(
        SELECT DISTINCT organization_id
        FROM organization_members
        WHERE user_id = v_user_id
    );
END;
$$;

COMMENT ON FUNCTION public.user_organization_ids IS 'Get array of organization IDs where user is a member';
GRANT EXECUTE ON FUNCTION public.user_organization_ids TO authenticated;

CREATE OR REPLACE FUNCTION public.user_is_admin_in_org(p_org_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM user_roles ur
        JOIN roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid()
          AND ur.organization_id = p_org_id
          AND r.code = 'admin'
    );
END;
$$;

COMMENT ON FUNCTION public.user_is_admin_in_org IS 'Check if current user has admin role in specified organization';
GRANT EXECUTE ON FUNCTION public.user_is_admin_in_org TO authenticated;

-- ===========================================================================
-- Migration 016: Add procurement data fields to quote_items
-- ===========================================================================

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_city VARCHAR(255);

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS production_time_days INTEGER DEFAULT 0;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS supplier_payment_terms TEXT;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS payer_company VARCHAR(255);

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS advance_to_supplier_percent DECIMAL(5, 2) DEFAULT 100;

ALTER TABLE quote_items
ADD COLUMN IF NOT EXISTS procurement_notes TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'quote_items_advance_supplier_check'
    ) THEN
        ALTER TABLE quote_items
        ADD CONSTRAINT quote_items_advance_supplier_check
        CHECK (advance_to_supplier_percent >= 0 AND advance_to_supplier_percent <= 100);
    END IF;
END $$;

COMMENT ON COLUMN quote_items.supplier_city IS 'City where the supplier is located';
COMMENT ON COLUMN quote_items.production_time_days IS 'Production lead time in days';
COMMENT ON COLUMN quote_items.supplier_payment_terms IS 'Payment terms with the supplier';
COMMENT ON COLUMN quote_items.payer_company IS 'Our legal entity that will pay the supplier';
COMMENT ON COLUMN quote_items.advance_to_supplier_percent IS 'Percentage of advance payment to supplier (0-100)';
COMMENT ON COLUMN quote_items.procurement_notes IS 'Notes from procurement manager about this item';

-- ===========================================================================
-- Migration 017: Setup specifications storage (manual step required)
-- ===========================================================================

DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'MANUAL STEP REQUIRED: Create specifications storage bucket';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'Go to Supabase Dashboard → Storage → New bucket';
    RAISE NOTICE 'Settings:';
    RAISE NOTICE '  - Name: specifications';
    RAISE NOTICE '  - Public bucket: Yes';
    RAISE NOTICE '  - File size limit: 10MB (10485760 bytes)';
    RAISE NOTICE '  - Allowed MIME types: application/pdf, image/jpeg, image/png';
    RAISE NOTICE '=====================================================';
END $$;

-- ===========================================================================
-- MIGRATION COMPLETE
-- ===========================================================================
--
-- Next steps:
-- 1. Create "specifications" storage bucket manually in Supabase Dashboard
-- 2. Update your .env file with:
--    - SUPABASE_URL=<your-new-project-url>
--    - SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
--    - SUPABASE_ANON_KEY=<your-anon-key>
-- 3. Restart your application
-- 4. Create test users using: python scripts/create_test_users.py
--
-- ===========================================================================
