-- Migration 130: Create user_settings table for storing user preferences
-- Used for: custom column selections, view preferences, etc.

CREATE TABLE IF NOT EXISTS kvota.user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES kvota.users(id) ON DELETE CASCADE,
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Each user can have only one setting per key
    UNIQUE(user_id, setting_key)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON kvota.user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_key ON kvota.user_settings(setting_key);

-- RLS Policies
ALTER TABLE kvota.user_settings ENABLE ROW LEVEL SECURITY;

-- Users can only see their own settings
CREATE POLICY "Users can view own settings" ON kvota.user_settings
    FOR SELECT USING (user_id = auth.uid());

-- Users can insert their own settings
CREATE POLICY "Users can insert own settings" ON kvota.user_settings
    FOR INSERT WITH CHECK (user_id = auth.uid());

-- Users can update their own settings
CREATE POLICY "Users can update own settings" ON kvota.user_settings
    FOR UPDATE USING (user_id = auth.uid());

-- Users can delete their own settings
CREATE POLICY "Users can delete own settings" ON kvota.user_settings
    FOR DELETE USING (user_id = auth.uid());

-- Comment
COMMENT ON TABLE kvota.user_settings IS 'User-specific preferences and settings (column selections, view modes, etc.)';
COMMENT ON COLUMN kvota.user_settings.setting_key IS 'Unique key for the setting, e.g., quote_control_columns, dashboard_layout';
COMMENT ON COLUMN kvota.user_settings.setting_value IS 'JSON value containing the setting data';
