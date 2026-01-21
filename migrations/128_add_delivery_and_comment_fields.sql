-- Migration 128: Add delivery dates, comment, and priority tag to specifications
-- Purpose: Add fields needed for complete ERPS registry display

-- Add new fields to specifications table
ALTER TABLE kvota.specifications
  ADD COLUMN IF NOT EXISTS comment TEXT,
  ADD COLUMN IF NOT EXISTS actual_delivery_date DATE,
  ADD COLUMN IF NOT EXISTS planned_dovoz_date DATE,
  ADD COLUMN IF NOT EXISTS priority_tag TEXT CHECK (priority_tag IN ('important', 'normal', 'problem', NULL));

-- Add indexes for query performance
CREATE INDEX IF NOT EXISTS idx_specifications_actual_delivery ON kvota.specifications(actual_delivery_date) WHERE actual_delivery_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_specifications_priority_tag ON kvota.specifications(priority_tag) WHERE priority_tag IS NOT NULL;

-- Comments for documentation
COMMENT ON COLUMN kvota.specifications.comment IS 'Комментарий финансового менеджера по спецификации';
COMMENT ON COLUMN kvota.specifications.actual_delivery_date IS 'Фактическая дата доставки (заполняется вручную)';
COMMENT ON COLUMN kvota.specifications.planned_dovoz_date IS 'Планируемая дата довоза (может меняться)';
COMMENT ON COLUMN kvota.specifications.priority_tag IS 'Тег приоритетности: important=важно, normal=обычно, problem=проблема';
