-- Migration 149: Add delivery_days to specifications
-- Created: 2026-02-01
-- Feature: Store editable delivery days (pre-filled from calc_variables.delivery_time, can be overwritten)

-- Add delivery_days column to specifications table
ALTER TABLE kvota.specifications
ADD COLUMN IF NOT EXISTS delivery_days INTEGER;

-- Add comment for documentation
COMMENT ON COLUMN kvota.specifications.delivery_days IS 'Number of delivery days. Pre-filled from calc_variables.delivery_time on creation, can be overwritten by user.';
