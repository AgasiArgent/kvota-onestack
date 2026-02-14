-- Migration 176: Add workflow tracking columns for quote and spec control
-- Tracks who completed the control step and when

ALTER TABLE kvota.quotes
ADD COLUMN IF NOT EXISTS quote_controller_id UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS quote_control_completed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS spec_controller_id UUID REFERENCES auth.users(id),
ADD COLUMN IF NOT EXISTS spec_control_completed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_quotes_quote_controller ON kvota.quotes(quote_controller_id);
CREATE INDEX IF NOT EXISTS idx_quotes_spec_controller ON kvota.quotes(spec_controller_id);
