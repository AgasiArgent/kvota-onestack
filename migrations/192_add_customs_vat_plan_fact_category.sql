-- Migration 192: Add customs_vat category to plan_fact_categories
-- Feature: [86aftzmne] Загрузка таможенных деклараций (ДТ) из XML + учёт пошлин в план-факте
--
-- Existing categories: customs_duty (2010), customs_fee (1010)
-- New category: customs_vat (5010 - VAT from GTD)

INSERT INTO kvota.plan_fact_categories (code, name, description, sort_order)
VALUES (
    'customs_vat',
    'Таможенный НДС',
    'НДС при импорте (код платежа 5010 из ДТ)',
    55  -- After customs_duty (50) and customs_fee
)
ON CONFLICT (code) DO NOTHING;
