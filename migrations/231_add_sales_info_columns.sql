-- Migration 231: Add sales info columns to quotes
-- Adds tender type, competitors, and cancellation tracking fields
-- for the sales collapsible section and client response modals.

ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS tender_type TEXT;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS competitors TEXT;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS cancellation_reason TEXT;
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS cancellation_comment TEXT;
