-- Migration: 119_extend_user_profiles
-- Description: Add additional fields to user_profiles table
-- Created: 2026-01-21

SET search_path TO kvota;

-- Add new fields to user_profiles
ALTER TABLE kvota.user_profiles
ADD COLUMN IF NOT EXISTS date_of_birth DATE,
ADD COLUMN IF NOT EXISTS hire_date DATE,
ADD COLUMN IF NOT EXISTS timezone VARCHAR(50) DEFAULT 'Europe/Moscow',
ADD COLUMN IF NOT EXISTS bio TEXT;

-- Add comments
COMMENT ON COLUMN kvota.user_profiles.date_of_birth IS 'User date of birth';
COMMENT ON COLUMN kvota.user_profiles.hire_date IS 'Date when user was hired';
COMMENT ON COLUMN kvota.user_profiles.timezone IS 'User preferred timezone (e.g., Europe/Moscow, Asia/Shanghai)';
COMMENT ON COLUMN kvota.user_profiles.bio IS 'User biography or about section';
