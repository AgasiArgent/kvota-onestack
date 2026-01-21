-- Migration: Add delivery_method column to quotes table
-- Description: Adds delivery method field (air, auto, sea, multimodal) for transport selection
-- Created: 2026-01-21

SET search_path TO kvota;

-- Add delivery_method column
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS delivery_method TEXT;

COMMENT ON COLUMN kvota.quotes.delivery_method IS 'Delivery method: Авиа, Авто, Море, or Мультимодально (все)';
