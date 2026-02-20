-- Migration 179: Enhance user_feedback for beta testing
-- Adds screenshot storage, ClickUp integration, expanded status

-- 1. Add screenshot column (base64 PNG)
ALTER TABLE kvota.user_feedback
ADD COLUMN IF NOT EXISTS screenshot_data TEXT;

-- 2. Add ClickUp task ID
ALTER TABLE kvota.user_feedback
ADD COLUMN IF NOT EXISTS clickup_task_id TEXT;

-- 3. Add updated_at column
ALTER TABLE kvota.user_feedback
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Comments
COMMENT ON COLUMN kvota.user_feedback.screenshot_data IS 'Base64-encoded annotated screenshot PNG';
COMMENT ON COLUMN kvota.user_feedback.clickup_task_id IS 'ClickUp task ID for tracking';
COMMENT ON COLUMN kvota.user_feedback.updated_at IS 'Last status update timestamp';
