-- Migration 153: Add validity_days column to quotes
-- Tracks how many days a quote remains valid after creation
ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS validity_days INTEGER DEFAULT 30;
