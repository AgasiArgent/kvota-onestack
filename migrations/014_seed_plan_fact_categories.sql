-- Migration: 014_seed_plan_fact_categories.sql
-- Description: Seed predefined payment categories for plan-fact tracking
-- Feature #15: Заполнить справочник plan_fact_categories
-- Created: 2025-01-15

-- ============================================
-- Seed Data: Payment Categories
-- ============================================
-- These categories are used to classify payments in the plan-fact
-- financial tracking system. Categories are divided into:
-- - Income (is_income = true): Payments received from clients
-- - Expense (is_income = false): Payments made to suppliers, logistics, etc.

INSERT INTO plan_fact_categories (code, name, is_income, sort_order) VALUES
    -- Income categories
    ('client_payment', 'Оплата от клиента', true, 1),

    -- Expense categories (in typical payment order)
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

-- ============================================
-- Verification
-- ============================================
-- Run this query to verify the seed data:
-- SELECT code, name, is_income, sort_order FROM plan_fact_categories ORDER BY sort_order;

-- ============================================
-- Category Descriptions (for documentation)
-- ============================================
-- client_payment:     Incoming payments from clients (typically in tranches)
-- supplier_payment:   Payments to suppliers for goods
-- logistics:          Shipping, freight, and delivery costs
-- customs:            Customs duties, fees, and brokerage
-- tax:                VAT and other applicable taxes
-- finance_commission: Bank fees, currency exchange fees, financial agent fees
-- other:              Miscellaneous expenses not covered by other categories
