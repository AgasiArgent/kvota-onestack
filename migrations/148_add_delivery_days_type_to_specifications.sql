-- Migration 148: Add delivery_days_type to specifications
-- Created: 2026-02-01
-- Feature: Allow selection of "рабочих дней" or "календарных дней" for delivery time

-- Add delivery_days_type column to specifications table
ALTER TABLE kvota.specifications
ADD COLUMN IF NOT EXISTS delivery_days_type VARCHAR(50) DEFAULT 'рабочих дней';

-- Add comment for documentation
COMMENT ON COLUMN kvota.specifications.delivery_days_type IS 'Type of days for delivery period: рабочих дней (working days) or календарных дней (calendar days)';

-- Add check constraint for valid values
ALTER TABLE kvota.specifications
ADD CONSTRAINT chk_delivery_days_type
CHECK (delivery_days_type IN ('рабочих дней', 'календарных дней'));
