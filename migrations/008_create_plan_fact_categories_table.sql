-- Migration: 008_create_plan_fact_categories_table.sql
-- Description: Create plan_fact_categories table for payment category reference data
-- Feature #8: Создать таблицу plan_fact_categories
-- Created: 2025-01-15

-- ============================================
-- Table: plan_fact_categories
-- Purpose: Reference table for payment categories used in plan-fact tracking
-- Categories classify payments as income or expense for financial reporting
-- ============================================

CREATE TABLE IF NOT EXISTS plan_fact_categories (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Category code (unique identifier for use in code)
    code VARCHAR(50) NOT NULL UNIQUE,

    -- Human-readable name
    name VARCHAR(255) NOT NULL,

    -- Is this category income (true) or expense (false)?
    is_income BOOLEAN NOT NULL DEFAULT false,

    -- Sort order for display
    sort_order INTEGER NOT NULL DEFAULT 0,

    -- Audit timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================
-- Table Comments
-- ============================================
COMMENT ON TABLE plan_fact_categories IS 'Reference table for payment categories in plan-fact financial tracking';
COMMENT ON COLUMN plan_fact_categories.id IS 'Primary key (UUID)';
COMMENT ON COLUMN plan_fact_categories.code IS 'Unique code for category (client_payment, supplier_payment, etc.)';
COMMENT ON COLUMN plan_fact_categories.name IS 'Human-readable category name in Russian';
COMMENT ON COLUMN plan_fact_categories.is_income IS 'True for income categories, false for expense categories';
COMMENT ON COLUMN plan_fact_categories.sort_order IS 'Display order in UI (lower numbers first)';
COMMENT ON COLUMN plan_fact_categories.created_at IS 'Timestamp when category was created';

-- ============================================
-- Indexes
-- ============================================

-- Index on code for fast lookups by code
CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_code ON plan_fact_categories(code);

-- Index on is_income for filtering income vs expense
CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_is_income ON plan_fact_categories(is_income);

-- Index on sort_order for ordered queries
CREATE INDEX IF NOT EXISTS idx_plan_fact_categories_sort_order ON plan_fact_categories(sort_order);

-- ============================================
-- Row Level Security (RLS)
-- ============================================

ALTER TABLE plan_fact_categories ENABLE ROW LEVEL SECURITY;

-- Allow all authenticated users to read categories (reference data)
CREATE POLICY "Users can view all payment categories"
    ON plan_fact_categories
    FOR SELECT
    TO authenticated
    USING (true);

-- Only admins can insert new categories
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

-- Only admins can update categories
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

-- Only admins can delete categories
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

-- ============================================
-- Seed Data - Predefined Payment Categories
-- Note: Feature #15 will handle the actual data population
-- This section is commented out as it belongs to Feature #15
-- ============================================

/*
INSERT INTO plan_fact_categories (code, name, is_income, sort_order) VALUES
    ('client_payment', 'Оплата от клиента', true, 1),
    ('supplier_payment', 'Оплата поставщику', false, 2),
    ('logistics', 'Логистика', false, 3),
    ('customs', 'Таможня', false, 4),
    ('tax', 'Налоги', false, 5),
    ('finance_commission', 'Банковская комиссия', false, 6),
    ('other', 'Прочее', false, 7)
ON CONFLICT (code) DO NOTHING;
*/

-- ============================================
-- Verification query (can be run after migration)
-- ============================================
-- SELECT * FROM plan_fact_categories ORDER BY sort_order;
