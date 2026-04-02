-- Migration 247: Add cancellation tracking columns to quotes
-- Adds cancelled_at timestamp and cancelled_by user reference
-- for the quote cancellation feature.

ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS cancelled_by UUID REFERENCES auth.users(id);
