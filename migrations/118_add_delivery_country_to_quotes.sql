-- Migration: Add delivery_country column to quotes table
-- Description: Adds delivery country field for better delivery location tracking
-- Created: 2026-01-20

SET search_path TO kvota;

-- Add delivery_country column
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS delivery_country TEXT;

COMMENT ON COLUMN kvota.quotes.delivery_country IS 'Country of delivery for the quote';
