-- Migration: 040_create_telegram_users_table.sql
-- Feature: DB-024 - Create telegram_users table
-- Description: Link Telegram accounts to system users for notifications and approvals
-- Version: 3.0

-- ============================================
-- TABLE: telegram_users
-- Links Telegram accounts to system users
-- Supports verification flow with temporary codes
-- ============================================

CREATE TABLE IF NOT EXISTS telegram_users (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Organization context (multi-tenant)
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Link to system user
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Telegram account info
    telegram_id BIGINT NOT NULL,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(100),
    telegram_last_name VARCHAR(100),
    telegram_language_code VARCHAR(10),

    -- Verification flow
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(10),
    verification_code_expires_at TIMESTAMPTZ,
    verification_attempts INTEGER DEFAULT 0,

    -- Notification preferences
    notifications_enabled BOOLEAN DEFAULT TRUE,
    notify_on_task_assigned BOOLEAN DEFAULT TRUE,
    notify_on_approval_request BOOLEAN DEFAULT TRUE,
    notify_on_status_change BOOLEAN DEFAULT TRUE,
    notify_on_deal_update BOOLEAN DEFAULT TRUE,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    blocked_at TIMESTAMPTZ,
    blocked_reason TEXT,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ,
    last_interaction_at TIMESTAMPTZ
);

-- ============================================
-- INDEXES
-- ============================================

-- Unique constraint: one Telegram account per organization
CREATE UNIQUE INDEX idx_telegram_users_telegram_org
    ON telegram_users(organization_id, telegram_id);

-- Unique constraint: one Telegram account per user
CREATE UNIQUE INDEX idx_telegram_users_user
    ON telegram_users(user_id)
    WHERE is_active = TRUE;

-- Fast lookup by telegram_id (for bot handlers)
CREATE INDEX idx_telegram_users_telegram_id
    ON telegram_users(telegram_id);

-- Lookup by username
CREATE INDEX idx_telegram_users_username
    ON telegram_users(telegram_username)
    WHERE telegram_username IS NOT NULL;

-- Pending verifications
CREATE INDEX idx_telegram_users_pending_verification
    ON telegram_users(verification_code, verification_code_expires_at)
    WHERE is_verified = FALSE
    AND verification_code IS NOT NULL;

-- Active users for notifications
CREATE INDEX idx_telegram_users_active_notifiable
    ON telegram_users(organization_id, is_active, is_verified, notifications_enabled)
    WHERE is_active = TRUE AND is_verified = TRUE AND notifications_enabled = TRUE;

-- ============================================
-- TRIGGERS
-- ============================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_telegram_users_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_telegram_users_update_timestamp
    BEFORE UPDATE ON telegram_users
    FOR EACH ROW
    EXECUTE FUNCTION update_telegram_users_timestamp();

-- Auto-set verified_at when is_verified becomes true
CREATE OR REPLACE FUNCTION set_telegram_verified_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_verified = TRUE AND OLD.is_verified = FALSE THEN
        NEW.verified_at = NOW();
        NEW.verification_code = NULL;
        NEW.verification_code_expires_at = NULL;
        NEW.verification_attempts = 0;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_telegram_users_set_verified_at
    BEFORE UPDATE ON telegram_users
    FOR EACH ROW
    EXECUTE FUNCTION set_telegram_verified_at();

-- ============================================
-- RLS POLICIES
-- ============================================

ALTER TABLE telegram_users ENABLE ROW LEVEL SECURITY;

-- Users can view their own telegram link
CREATE POLICY telegram_users_select_own ON telegram_users
    FOR SELECT
    USING (user_id = auth.uid());

-- Admins can view all telegram users in their organization
CREATE POLICY telegram_users_select_admin ON telegram_users
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id
            FROM user_organizations
            WHERE user_id = auth.uid()
            AND role IN ('admin', 'owner')
        )
    );

-- Users can create their own telegram link
CREATE POLICY telegram_users_insert_own ON telegram_users
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own telegram link
CREATE POLICY telegram_users_update_own ON telegram_users
    FOR UPDATE
    USING (user_id = auth.uid());

-- Admins can update any telegram user in their organization
CREATE POLICY telegram_users_update_admin ON telegram_users
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT organization_id
            FROM user_organizations
            WHERE user_id = auth.uid()
            AND role IN ('admin', 'owner')
        )
    );

-- Users can delete their own telegram link
CREATE POLICY telegram_users_delete_own ON telegram_users
    FOR DELETE
    USING (user_id = auth.uid());

-- Admins can delete any telegram user in their organization
CREATE POLICY telegram_users_delete_admin ON telegram_users
    FOR DELETE
    USING (
        organization_id IN (
            SELECT organization_id
            FROM user_organizations
            WHERE user_id = auth.uid()
            AND role IN ('admin', 'owner')
        )
    );

-- ============================================
-- HELPER FUNCTIONS
-- ============================================

-- Generate a random verification code (6 characters)
CREATE OR REPLACE FUNCTION generate_telegram_verification_code()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    FOR i IN 1..6 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::int, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Start verification flow for a user
CREATE OR REPLACE FUNCTION start_telegram_verification(
    p_user_id UUID,
    p_organization_id UUID,
    p_telegram_id BIGINT,
    p_telegram_username TEXT DEFAULT NULL,
    p_telegram_first_name TEXT DEFAULT NULL,
    p_telegram_last_name TEXT DEFAULT NULL,
    p_telegram_language_code TEXT DEFAULT NULL
)
RETURNS TABLE (
    telegram_user_id UUID,
    verification_code TEXT,
    expires_at TIMESTAMPTZ
) AS $$
DECLARE
    v_code TEXT;
    v_expires_at TIMESTAMPTZ;
    v_telegram_user_id UUID;
BEGIN
    v_code := generate_telegram_verification_code();
    v_expires_at := NOW() + INTERVAL '10 minutes';

    -- Insert or update (upsert)
    INSERT INTO telegram_users (
        user_id,
        organization_id,
        telegram_id,
        telegram_username,
        telegram_first_name,
        telegram_last_name,
        telegram_language_code,
        verification_code,
        verification_code_expires_at,
        is_verified,
        verification_attempts
    )
    VALUES (
        p_user_id,
        p_organization_id,
        p_telegram_id,
        p_telegram_username,
        p_telegram_first_name,
        p_telegram_last_name,
        p_telegram_language_code,
        v_code,
        v_expires_at,
        FALSE,
        0
    )
    ON CONFLICT (user_id) WHERE is_active = TRUE
    DO UPDATE SET
        telegram_id = EXCLUDED.telegram_id,
        telegram_username = EXCLUDED.telegram_username,
        telegram_first_name = EXCLUDED.telegram_first_name,
        telegram_last_name = EXCLUDED.telegram_last_name,
        telegram_language_code = EXCLUDED.telegram_language_code,
        verification_code = EXCLUDED.verification_code,
        verification_code_expires_at = EXCLUDED.verification_code_expires_at,
        is_verified = FALSE,
        verification_attempts = 0,
        updated_at = NOW()
    RETURNING id INTO v_telegram_user_id;

    RETURN QUERY SELECT v_telegram_user_id, v_code, v_expires_at;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Verify a telegram user with code
CREATE OR REPLACE FUNCTION verify_telegram_user(
    p_telegram_id BIGINT,
    p_code TEXT
)
RETURNS TABLE (
    success BOOLEAN,
    message TEXT,
    user_id UUID,
    organization_id UUID
) AS $$
DECLARE
    v_telegram_user RECORD;
    v_max_attempts CONSTANT INTEGER := 5;
BEGIN
    -- Find the telegram user
    SELECT tu.* INTO v_telegram_user
    FROM telegram_users tu
    WHERE tu.telegram_id = p_telegram_id
    AND tu.is_active = TRUE
    AND tu.is_verified = FALSE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'Telegram account not found or already verified'::TEXT, NULL::UUID, NULL::UUID;
        RETURN;
    END IF;

    -- Check if too many attempts
    IF v_telegram_user.verification_attempts >= v_max_attempts THEN
        RETURN QUERY SELECT FALSE, 'Too many verification attempts. Please request a new code.'::TEXT, NULL::UUID, NULL::UUID;
        RETURN;
    END IF;

    -- Increment attempts
    UPDATE telegram_users
    SET verification_attempts = verification_attempts + 1
    WHERE id = v_telegram_user.id;

    -- Check if code expired
    IF v_telegram_user.verification_code_expires_at < NOW() THEN
        RETURN QUERY SELECT FALSE, 'Verification code has expired. Please request a new code.'::TEXT, NULL::UUID, NULL::UUID;
        RETURN;
    END IF;

    -- Check code
    IF UPPER(v_telegram_user.verification_code) != UPPER(p_code) THEN
        RETURN QUERY SELECT FALSE, 'Invalid verification code.'::TEXT, NULL::UUID, NULL::UUID;
        RETURN;
    END IF;

    -- Success! Mark as verified
    UPDATE telegram_users
    SET is_verified = TRUE
    WHERE id = v_telegram_user.id;

    RETURN QUERY SELECT TRUE, 'Successfully verified!'::TEXT, v_telegram_user.user_id, v_telegram_user.organization_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get telegram user by telegram_id
CREATE OR REPLACE FUNCTION get_telegram_user(p_telegram_id BIGINT)
RETURNS TABLE (
    id UUID,
    user_id UUID,
    organization_id UUID,
    telegram_username VARCHAR(100),
    is_verified BOOLEAN,
    is_active BOOLEAN,
    notifications_enabled BOOLEAN,
    notify_on_task_assigned BOOLEAN,
    notify_on_approval_request BOOLEAN,
    notify_on_status_change BOOLEAN,
    notify_on_deal_update BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tu.id,
        tu.user_id,
        tu.organization_id,
        tu.telegram_username,
        tu.is_verified,
        tu.is_active,
        tu.notifications_enabled,
        tu.notify_on_task_assigned,
        tu.notify_on_approval_request,
        tu.notify_on_status_change,
        tu.notify_on_deal_update
    FROM telegram_users tu
    WHERE tu.telegram_id = p_telegram_id
    AND tu.is_active = TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get telegram_id for a system user
CREATE OR REPLACE FUNCTION get_telegram_id_for_user(p_user_id UUID)
RETURNS BIGINT AS $$
BEGIN
    RETURN (
        SELECT telegram_id
        FROM telegram_users
        WHERE user_id = p_user_id
        AND is_active = TRUE
        AND is_verified = TRUE
        AND notifications_enabled = TRUE
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get all telegram users who should receive a notification type
CREATE OR REPLACE FUNCTION get_telegram_recipients_for_notification(
    p_organization_id UUID,
    p_notification_type TEXT,
    p_user_ids UUID[] DEFAULT NULL
)
RETURNS TABLE (
    user_id UUID,
    telegram_id BIGINT,
    telegram_username VARCHAR(100),
    telegram_first_name VARCHAR(100)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        tu.user_id,
        tu.telegram_id,
        tu.telegram_username,
        tu.telegram_first_name
    FROM telegram_users tu
    WHERE tu.organization_id = p_organization_id
    AND tu.is_active = TRUE
    AND tu.is_verified = TRUE
    AND tu.notifications_enabled = TRUE
    AND (p_user_ids IS NULL OR tu.user_id = ANY(p_user_ids))
    AND (
        (p_notification_type = 'task_assigned' AND tu.notify_on_task_assigned = TRUE) OR
        (p_notification_type = 'approval_request' AND tu.notify_on_approval_request = TRUE) OR
        (p_notification_type = 'status_change' AND tu.notify_on_status_change = TRUE) OR
        (p_notification_type = 'deal_update' AND tu.notify_on_deal_update = TRUE) OR
        (p_notification_type = 'all')
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update notification preferences
CREATE OR REPLACE FUNCTION update_telegram_notification_preferences(
    p_telegram_id BIGINT,
    p_notifications_enabled BOOLEAN DEFAULT NULL,
    p_notify_on_task_assigned BOOLEAN DEFAULT NULL,
    p_notify_on_approval_request BOOLEAN DEFAULT NULL,
    p_notify_on_status_change BOOLEAN DEFAULT NULL,
    p_notify_on_deal_update BOOLEAN DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE telegram_users
    SET
        notifications_enabled = COALESCE(p_notifications_enabled, notifications_enabled),
        notify_on_task_assigned = COALESCE(p_notify_on_task_assigned, notify_on_task_assigned),
        notify_on_approval_request = COALESCE(p_notify_on_approval_request, notify_on_approval_request),
        notify_on_status_change = COALESCE(p_notify_on_status_change, notify_on_status_change),
        notify_on_deal_update = COALESCE(p_notify_on_deal_update, notify_on_deal_update)
    WHERE telegram_id = p_telegram_id
    AND is_active = TRUE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Update last interaction timestamp
CREATE OR REPLACE FUNCTION update_telegram_interaction(p_telegram_id BIGINT)
RETURNS VOID AS $$
BEGIN
    UPDATE telegram_users
    SET last_interaction_at = NOW()
    WHERE telegram_id = p_telegram_id
    AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Unlink telegram account (soft delete)
CREATE OR REPLACE FUNCTION unlink_telegram_account(p_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE telegram_users
    SET
        is_active = FALSE,
        is_verified = FALSE,
        updated_at = NOW()
    WHERE user_id = p_user_id
    AND is_active = TRUE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Block a telegram user (admin action)
CREATE OR REPLACE FUNCTION block_telegram_user(
    p_telegram_id BIGINT,
    p_reason TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE telegram_users
    SET
        is_active = FALSE,
        blocked_at = NOW(),
        blocked_reason = p_reason,
        updated_at = NOW()
    WHERE telegram_id = p_telegram_id
    AND is_active = TRUE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- VIEW: telegram_users_summary
-- For admin dashboard
-- ============================================

CREATE OR REPLACE VIEW v_telegram_users_summary AS
SELECT
    tu.id,
    tu.organization_id,
    tu.user_id,
    tu.telegram_id,
    tu.telegram_username,
    tu.telegram_first_name || COALESCE(' ' || tu.telegram_last_name, '') AS telegram_full_name,
    tu.is_verified,
    tu.is_active,
    tu.notifications_enabled,
    tu.verified_at,
    tu.last_interaction_at,
    tu.created_at,
    -- User info (requires join with profiles/users table if available)
    au.email AS user_email
FROM telegram_users tu
LEFT JOIN auth.users au ON tu.user_id = au.id
WHERE tu.is_active = TRUE;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE telegram_users IS 'Links Telegram accounts to system users for notifications and approvals (v3.0)';
COMMENT ON COLUMN telegram_users.telegram_id IS 'Unique Telegram user ID (bigint)';
COMMENT ON COLUMN telegram_users.verification_code IS 'Temporary code for account verification';
COMMENT ON COLUMN telegram_users.verification_attempts IS 'Number of failed verification attempts (max 5)';
COMMENT ON COLUMN telegram_users.notifications_enabled IS 'Master switch for all notifications';
COMMENT ON COLUMN telegram_users.notify_on_task_assigned IS 'Receive notification when task is assigned';
COMMENT ON COLUMN telegram_users.notify_on_approval_request IS 'Receive notification for approval requests (top_manager)';
COMMENT ON COLUMN telegram_users.last_interaction_at IS 'Last time user interacted with bot';

COMMENT ON FUNCTION start_telegram_verification IS 'Start verification flow: creates/updates telegram_user with new code';
COMMENT ON FUNCTION verify_telegram_user IS 'Verify telegram account with code (returns success, message, user_id)';
COMMENT ON FUNCTION get_telegram_recipients_for_notification IS 'Get list of telegram recipients for a notification type';
