-- Migration: 010_create_telegram_users_table
-- Description: Create table to link Telegram accounts with system users
-- Author: Claude (autonomous session)
-- Date: 2025-01-15
-- Depends on: auth.users (Supabase built-in)

-- Create telegram_users table
-- This table links Telegram accounts to users for notifications and approvals
CREATE TABLE IF NOT EXISTS telegram_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    telegram_id BIGINT NOT NULL,
    telegram_username VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    verification_code VARCHAR(32),
    verification_code_expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE
);

-- Unique constraint: one Telegram account can only be linked to one user
CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_users_telegram_id
    ON telegram_users(telegram_id);

-- Index for fast lookups by user (to check if user has Telegram linked)
CREATE INDEX IF NOT EXISTS idx_telegram_users_user_id
    ON telegram_users(user_id);

-- Index for verification code lookups (during verification process)
CREATE INDEX IF NOT EXISTS idx_telegram_users_verification_code
    ON telegram_users(verification_code)
    WHERE verification_code IS NOT NULL AND is_verified = FALSE;

-- Index for finding verified users (for sending notifications)
CREATE INDEX IF NOT EXISTS idx_telegram_users_verified
    ON telegram_users(user_id)
    WHERE is_verified = TRUE;

-- Enable Row Level Security
ALTER TABLE telegram_users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can see their own Telegram link
CREATE POLICY "telegram_users_select_own" ON telegram_users
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

-- Policy: Admins can see all Telegram links in their organization
CREATE POLICY "telegram_users_select_admin" ON telegram_users
    FOR SELECT
    TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM user_roles ur
            JOIN roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.code = 'admin'
            AND ur.organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = telegram_users.user_id
            )
        )
    );

-- Policy: Users can insert their own Telegram link
CREATE POLICY "telegram_users_insert_own" ON telegram_users
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

-- Policy: Users can update their own Telegram link
CREATE POLICY "telegram_users_update_own" ON telegram_users
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Policy: Users can delete their own Telegram link
CREATE POLICY "telegram_users_delete_own" ON telegram_users
    FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());

-- Function to generate a random verification code
CREATE OR REPLACE FUNCTION generate_telegram_verification_code()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    -- Generate 6-character code (excluding confusing characters like 0, O, 1, I)
    FOR i IN 1..6 LOOP
        result := result || substr(chars, floor(random() * length(chars) + 1)::integer, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Function to request Telegram verification
-- Returns the verification code or NULL if already verified
CREATE OR REPLACE FUNCTION request_telegram_verification(p_user_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_code TEXT;
    v_existing RECORD;
BEGIN
    -- Check if user already has a verified Telegram account
    SELECT * INTO v_existing FROM telegram_users
    WHERE user_id = p_user_id AND is_verified = TRUE;

    IF FOUND THEN
        -- Already verified, return NULL
        RETURN NULL;
    END IF;

    -- Generate new verification code
    v_code := generate_telegram_verification_code();

    -- Insert or update the telegram_users record
    INSERT INTO telegram_users (user_id, telegram_id, verification_code, verification_code_expires_at)
    VALUES (p_user_id, 0, v_code, NOW() + INTERVAL '30 minutes')
    ON CONFLICT (user_id)
    WHERE telegram_id = 0 OR is_verified = FALSE
    DO UPDATE SET
        verification_code = v_code,
        verification_code_expires_at = NOW() + INTERVAL '30 minutes';

    RETURN v_code;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to verify Telegram account
-- Called when user sends verification code to the bot
CREATE OR REPLACE FUNCTION verify_telegram_account(
    p_verification_code TEXT,
    p_telegram_id BIGINT,
    p_telegram_username TEXT DEFAULT NULL
)
RETURNS TABLE (
    success BOOLEAN,
    user_id UUID,
    message TEXT
) AS $$
DECLARE
    v_record RECORD;
BEGIN
    -- Find the pending verification
    SELECT * INTO v_record FROM telegram_users
    WHERE verification_code = p_verification_code
    AND is_verified = FALSE
    AND verification_code_expires_at > NOW();

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, 'Invalid or expired verification code'::TEXT;
        RETURN;
    END IF;

    -- Check if telegram_id is already linked to another user
    IF EXISTS (SELECT 1 FROM telegram_users WHERE telegram_id = p_telegram_id AND is_verified = TRUE) THEN
        RETURN QUERY SELECT FALSE, NULL::UUID, 'This Telegram account is already linked to another user'::TEXT;
        RETURN;
    END IF;

    -- Update the record to mark as verified
    UPDATE telegram_users SET
        telegram_id = p_telegram_id,
        telegram_username = p_telegram_username,
        is_verified = TRUE,
        verification_code = NULL,
        verification_code_expires_at = NULL,
        verified_at = NOW()
    WHERE id = v_record.id;

    RETURN QUERY SELECT TRUE, v_record.user_id, 'Telegram account verified successfully'::TEXT;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Add comments to table and columns
COMMENT ON TABLE telegram_users IS 'Links Telegram accounts to system users for notifications and approvals';
COMMENT ON COLUMN telegram_users.user_id IS 'Reference to auth.users - the system user';
COMMENT ON COLUMN telegram_users.telegram_id IS 'Telegram user ID (BigInt) for sending messages';
COMMENT ON COLUMN telegram_users.telegram_username IS 'Telegram username (without @) for display purposes';
COMMENT ON COLUMN telegram_users.is_verified IS 'Whether the Telegram account has been verified';
COMMENT ON COLUMN telegram_users.verification_code IS 'Temporary code for account verification';
COMMENT ON COLUMN telegram_users.verification_code_expires_at IS 'Expiration time for verification code';
COMMENT ON COLUMN telegram_users.verified_at IS 'Timestamp when the account was verified';

COMMENT ON FUNCTION generate_telegram_verification_code() IS 'Generates a random 6-character verification code';
COMMENT ON FUNCTION request_telegram_verification(UUID) IS 'Creates or updates a verification code for Telegram linking';
COMMENT ON FUNCTION verify_telegram_account(TEXT, BIGINT, TEXT) IS 'Verifies a Telegram account using the verification code';
