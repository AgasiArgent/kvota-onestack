-- Migration 038: Create plan_fact_categories table with seed data
-- Created: 2026-01-15
-- Feature: DB-022 - Plan-fact payment categories reference table

-- ============================================
-- TABLE: plan_fact_categories
-- ============================================
-- Reference table for categorizing planned and actual payments in deal tracking.
-- Used by finance role to track income vs expenses by category.

CREATE TABLE IF NOT EXISTS plan_fact_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Category identification
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    name_ru VARCHAR(100),  -- Russian name for UI display

    -- Financial classification
    is_income BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE = income, FALSE = expense

    -- Display order for consistent UI presentation
    display_order INTEGER DEFAULT 0,

    -- Active flag for soft deletes
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_plan_fact_categories_code UNIQUE (code)
);

-- Comment on table
COMMENT ON TABLE plan_fact_categories IS 'Reference table for plan-fact payment categories (income/expense types)';

-- Comments on columns
COMMENT ON COLUMN plan_fact_categories.code IS 'Unique category code (e.g., client_payment, supplier_payment)';
COMMENT ON COLUMN plan_fact_categories.name IS 'English name for code reference';
COMMENT ON COLUMN plan_fact_categories.name_ru IS 'Russian name for UI display';
COMMENT ON COLUMN plan_fact_categories.is_income IS 'TRUE for income categories (payments from client), FALSE for expenses';
COMMENT ON COLUMN plan_fact_categories.display_order IS 'Order for displaying in UI lists';

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_code
ON plan_fact_categories(code);

CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_is_income
ON plan_fact_categories(is_income);

CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_active_order
ON plan_fact_categories(is_active, display_order)
WHERE is_active = TRUE;

-- ============================================
-- SEED DATA: Default payment categories
-- ============================================
-- Based on spec: client_payment (income), supplier_payment, logistics_cost,
-- customs_cost, tax, finance_commission, lpr_reward, other_expense (all expenses)

INSERT INTO plan_fact_categories (code, name, name_ru, is_income, display_order)
VALUES
    -- Income categories
    ('client_payment', 'Client Payment', 'Платёж от клиента', TRUE, 1),
    ('client_advance', 'Client Advance Payment', 'Аванс от клиента', TRUE, 2),
    ('client_final', 'Client Final Payment', 'Финальный платёж от клиента', TRUE, 3),

    -- Expense categories - Suppliers
    ('supplier_payment', 'Supplier Payment', 'Платёж поставщику', FALSE, 10),
    ('supplier_advance', 'Supplier Advance', 'Аванс поставщику', FALSE, 11),
    ('supplier_balance', 'Supplier Balance Payment', 'Остаток поставщику', FALSE, 12),

    -- Expense categories - Logistics
    ('logistics_cost', 'Logistics Cost', 'Логистика', FALSE, 20),
    ('logistics_supplier_hub', 'Logistics: Supplier to Hub', 'Логистика: поставщик → хаб', FALSE, 21),
    ('logistics_hub_customs', 'Logistics: Hub to Customs', 'Логистика: хаб → таможня', FALSE, 22),
    ('logistics_customs_customer', 'Logistics: Customs to Customer', 'Логистика: таможня → клиент', FALSE, 23),

    -- Expense categories - Customs
    ('customs_cost', 'Customs Cost', 'Таможня (общее)', FALSE, 30),
    ('customs_duty', 'Customs Duty', 'Таможенная пошлина', FALSE, 31),
    ('customs_fee', 'Customs Fee', 'Таможенный сбор', FALSE, 32),
    ('customs_broker', 'Customs Broker Fee', 'Услуги брокера', FALSE, 33),

    -- Expense categories - Other
    ('tax', 'Tax', 'Налоги', FALSE, 40),
    ('vat', 'VAT', 'НДС', FALSE, 41),
    ('finance_commission', 'Finance Agent Commission', 'Комиссия финагента', FALSE, 50),
    ('lpr_reward', 'LPR Reward', 'Вознаграждение ЛПР', FALSE, 60),
    ('bank_commission', 'Bank Commission', 'Банковская комиссия', FALSE, 70),
    ('currency_conversion', 'Currency Conversion Loss', 'Курсовая разница', FALSE, 71),
    ('other_expense', 'Other Expense', 'Прочие расходы', FALSE, 90)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    name_ru = EXCLUDED.name_ru,
    is_income = EXCLUDED.is_income,
    display_order = EXCLUDED.display_order;

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Function: Get all active categories
CREATE OR REPLACE FUNCTION get_plan_fact_categories(
    p_is_income BOOLEAN DEFAULT NULL  -- NULL = all, TRUE = income only, FALSE = expense only
)
RETURNS TABLE (
    id UUID,
    code VARCHAR(50),
    name VARCHAR(100),
    name_ru VARCHAR(100),
    is_income BOOLEAN,
    display_order INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        pfc.id,
        pfc.code,
        pfc.name,
        pfc.name_ru,
        pfc.is_income,
        pfc.display_order
    FROM plan_fact_categories pfc
    WHERE pfc.is_active = TRUE
      AND (p_is_income IS NULL OR pfc.is_income = p_is_income)
    ORDER BY pfc.display_order, pfc.name;
$$;

COMMENT ON FUNCTION get_plan_fact_categories IS 'Get active plan-fact categories, optionally filtered by income/expense';


-- Function: Get category by code
CREATE OR REPLACE FUNCTION get_category_by_code(
    p_code VARCHAR(50)
)
RETURNS TABLE (
    id UUID,
    code VARCHAR(50),
    name VARCHAR(100),
    name_ru VARCHAR(100),
    is_income BOOLEAN
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        pfc.id,
        pfc.code,
        pfc.name,
        pfc.name_ru,
        pfc.is_income
    FROM plan_fact_categories pfc
    WHERE pfc.code = p_code
      AND pfc.is_active = TRUE
    LIMIT 1;
$$;

COMMENT ON FUNCTION get_category_by_code IS 'Get category details by code';


-- Function: Get income categories
CREATE OR REPLACE FUNCTION get_income_categories()
RETURNS TABLE (
    id UUID,
    code VARCHAR(50),
    name_ru VARCHAR(100)
)
LANGUAGE sql
STABLE
AS $$
    SELECT id, code, name_ru
    FROM plan_fact_categories
    WHERE is_income = TRUE AND is_active = TRUE
    ORDER BY display_order;
$$;

COMMENT ON FUNCTION get_income_categories IS 'Get all income categories for dropdown selection';


-- Function: Get expense categories
CREATE OR REPLACE FUNCTION get_expense_categories()
RETURNS TABLE (
    id UUID,
    code VARCHAR(50),
    name_ru VARCHAR(100)
)
LANGUAGE sql
STABLE
AS $$
    SELECT id, code, name_ru
    FROM plan_fact_categories
    WHERE is_income = FALSE AND is_active = TRUE
    ORDER BY display_order;
$$;

COMMENT ON FUNCTION get_expense_categories IS 'Get all expense categories for dropdown selection';


-- Function: Get category statistics for a deal
CREATE OR REPLACE FUNCTION get_deal_category_stats(
    p_deal_id UUID
)
RETURNS TABLE (
    category_code VARCHAR(50),
    category_name_ru VARCHAR(100),
    is_income BOOLEAN,
    planned_total DECIMAL(15,2),
    actual_total DECIMAL(15,2),
    variance DECIMAL(15,2),
    item_count INTEGER
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        pfc.code AS category_code,
        pfc.name_ru AS category_name_ru,
        pfc.is_income,
        COALESCE(SUM(pfi.planned_amount), 0)::DECIMAL(15,2) AS planned_total,
        COALESCE(SUM(pfi.actual_amount), 0)::DECIMAL(15,2) AS actual_total,
        COALESCE(SUM(pfi.variance_amount), 0)::DECIMAL(15,2) AS variance,
        COUNT(pfi.id)::INTEGER AS item_count
    FROM plan_fact_categories pfc
    LEFT JOIN plan_fact_items pfi ON pfi.category_id = pfc.id AND pfi.deal_id = p_deal_id
    WHERE pfc.is_active = TRUE
    GROUP BY pfc.id, pfc.code, pfc.name_ru, pfc.is_income, pfc.display_order
    HAVING COUNT(pfi.id) > 0
    ORDER BY pfc.display_order;
$$;

COMMENT ON FUNCTION get_deal_category_stats IS 'Get plan-fact statistics by category for a deal';


-- ============================================
-- RLS POLICIES (if applicable)
-- ============================================
-- Note: plan_fact_categories is a reference table, not organization-specific.
-- All users can read categories. Only admins should modify.

ALTER TABLE plan_fact_categories ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to read
CREATE POLICY "plan_fact_categories_select_policy"
ON plan_fact_categories
FOR SELECT
USING (TRUE);  -- Everyone can read categories

-- Only allow service role to modify (admin via API)
CREATE POLICY "plan_fact_categories_admin_all"
ON plan_fact_categories
FOR ALL
USING (auth.role() = 'service_role');


-- ============================================
-- VERIFICATION
-- ============================================

DO $$
DECLARE
    v_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM plan_fact_categories WHERE is_active = TRUE;

    IF v_count >= 8 THEN  -- At least the 8 core categories from spec
        RAISE NOTICE '✓ plan_fact_categories table created with % seed categories', v_count;
    ELSE
        RAISE WARNING 'plan_fact_categories has only % categories (expected at least 8)', v_count;
    END IF;

    -- Verify required categories from spec
    IF EXISTS (
        SELECT 1 FROM plan_fact_categories
        WHERE code IN ('client_payment', 'supplier_payment', 'logistics_cost', 'customs_cost',
                       'tax', 'finance_commission', 'lpr_reward', 'other_expense')
        GROUP BY TRUE
        HAVING COUNT(*) = 8
    ) THEN
        RAISE NOTICE '✓ All 8 core categories from spec exist';
    ELSE
        RAISE WARNING 'Some core categories are missing';
    END IF;
END $$;
