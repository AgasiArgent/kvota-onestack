-- Migration 171: Add sales_checklist JSONB column to quotes
-- Stores pre-procurement checklist answers filled by sales before submitting to procurement
-- JSON structure: {is_estimate, is_tender, direct_request, trading_org_request, equipment_description, completed_at, completed_by}

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS sales_checklist JSONB;

COMMENT ON COLUMN kvota.quotes.sales_checklist IS 'Pre-procurement sales checklist: {is_estimate, is_tender, direct_request, trading_org_request, equipment_description, completed_at, completed_by}';
