-- Migration 165: Add logistics_stage_id FK to plan_fact_items + logistics categories
-- P2.8: Per-stage expenses linked to logistics stages

-- Step 1: Add logistics_stage_id column to plan_fact_items
ALTER TABLE kvota.plan_fact_items
    ADD COLUMN IF NOT EXISTS logistics_stage_id UUID REFERENCES kvota.logistics_stages(id) ON DELETE SET NULL;

-- Index for fast lookup by logistics stage
CREATE INDEX IF NOT EXISTS idx_plan_fact_items_logistics_stage_id
    ON kvota.plan_fact_items(logistics_stage_id);

-- Step 2: Insert 6 logistics expense categories (one per expense-capable stage)
INSERT INTO kvota.plan_fact_categories (code, name, is_income, sort_order) VALUES
    ('logistics_first_mile', 'Логистика: Первая миля', false, 10),
    ('logistics_hub', 'Логистика: Хаб', false, 11),
    ('logistics_hub_hub', 'Логистика: Хаб-Хаб', false, 12),
    ('logistics_transit', 'Логистика: Транзит', false, 13),
    ('logistics_post_transit', 'Логистика: Пост-транзит', false, 14),
    ('logistics_last_mile', 'Логистика: Последняя миля', false, 15)
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    is_income = EXCLUDED.is_income,
    sort_order = EXCLUDED.sort_order;
