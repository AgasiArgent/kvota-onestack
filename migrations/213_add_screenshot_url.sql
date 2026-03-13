-- Add screenshot_url column for Supabase Storage URLs (Next.js widget)
-- Existing screenshot_data (base64) kept for backward compat with FastHTML widget
ALTER TABLE kvota.user_feedback ADD COLUMN IF NOT EXISTS screenshot_url TEXT;
