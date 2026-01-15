-- Migration: 011_create_notifications_table.sql
-- Feature #11: Create notifications table for notification history
-- Created: 2025-01-15
-- Description: Stores history of all notifications sent to users via Telegram, email, or in-app

-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Recipient
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Related entities (nullable - notification may be system-wide)
    quote_id UUID REFERENCES quotes(id) ON DELETE SET NULL,
    deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,

    -- Notification content
    type VARCHAR(50) NOT NULL,
    -- Types: task_assigned, approval_required, approval_decision, status_changed,
    --        returned_for_revision, comment_added, deadline_reminder, system_message
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,

    -- Delivery channel
    channel VARCHAR(20) NOT NULL DEFAULT 'telegram',
    -- Channels: telegram, email, in_app

    -- Delivery status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Statuses: pending, sent, delivered, read, failed

    -- Channel-specific metadata
    telegram_message_id BIGINT,  -- For updating/editing Telegram messages
    email_message_id VARCHAR(255),  -- For email tracking
    error_message TEXT,  -- Error details if status = 'failed'

    -- Timestamps
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_notification_type CHECK (
        type IN (
            'task_assigned',
            'approval_required',
            'approval_decision',
            'status_changed',
            'returned_for_revision',
            'comment_added',
            'deadline_reminder',
            'system_message'
        )
    ),
    CONSTRAINT valid_notification_channel CHECK (
        channel IN ('telegram', 'email', 'in_app')
    ),
    CONSTRAINT valid_notification_status CHECK (
        status IN ('pending', 'sent', 'delivered', 'read', 'failed')
    ),
    CONSTRAINT valid_sent_at CHECK (
        (status = 'pending' AND sent_at IS NULL) OR
        (status != 'pending' AND sent_at IS NOT NULL)
    )
);

-- Comments for documentation
COMMENT ON TABLE notifications IS 'History of all notifications sent to users';
COMMENT ON COLUMN notifications.user_id IS 'User who should receive the notification';
COMMENT ON COLUMN notifications.quote_id IS 'Related quote, if notification is quote-related';
COMMENT ON COLUMN notifications.deal_id IS 'Related deal, if notification is deal-related';
COMMENT ON COLUMN notifications.type IS 'Type of notification (task_assigned, approval_required, etc.)';
COMMENT ON COLUMN notifications.title IS 'Short title for the notification';
COMMENT ON COLUMN notifications.message IS 'Full notification message text';
COMMENT ON COLUMN notifications.channel IS 'Delivery channel (telegram, email, in_app)';
COMMENT ON COLUMN notifications.status IS 'Delivery status (pending, sent, delivered, read, failed)';
COMMENT ON COLUMN notifications.telegram_message_id IS 'Telegram message ID for message updates';
COMMENT ON COLUMN notifications.email_message_id IS 'Email message ID for tracking';
COMMENT ON COLUMN notifications.error_message IS 'Error details if delivery failed';
COMMENT ON COLUMN notifications.sent_at IS 'When notification was sent';
COMMENT ON COLUMN notifications.delivered_at IS 'When notification was confirmed delivered';
COMMENT ON COLUMN notifications.read_at IS 'When notification was marked as read';

-- Indexes for common queries
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_quote_id ON notifications(quote_id) WHERE quote_id IS NOT NULL;
CREATE INDEX idx_notifications_deal_id ON notifications(deal_id) WHERE deal_id IS NOT NULL;
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_channel ON notifications(channel);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);

-- Composite indexes for dashboard queries
CREATE INDEX idx_notifications_user_status ON notifications(user_id, status);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, created_at DESC)
    WHERE status NOT IN ('read', 'failed');
CREATE INDEX idx_notifications_pending_send ON notifications(channel, created_at)
    WHERE status = 'pending';

-- Enable Row Level Security
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Users can view their own notifications
CREATE POLICY notifications_select_own ON notifications
    FOR SELECT
    USING (auth.uid() = user_id);

-- System can insert notifications for any user in the organization
-- (This is typically done by backend services with service role key)
CREATE POLICY notifications_insert ON notifications
    FOR INSERT
    WITH CHECK (
        -- User must be in the same organization as the recipient
        -- (This check is simplified - in production, use service role key)
        EXISTS (
            SELECT 1 FROM organization_members om1
            JOIN organization_members om2 ON om1.organization_id = om2.organization_id
            WHERE om1.user_id = auth.uid() AND om2.user_id = user_id
        )
    );

-- Users can update (mark as read) their own notifications
CREATE POLICY notifications_update_own ON notifications
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- No delete - notifications are permanent audit records
-- (Admin can delete via service role key if needed)

-- Helper function to create a notification
CREATE OR REPLACE FUNCTION create_notification(
    p_user_id UUID,
    p_type VARCHAR(50),
    p_title VARCHAR(255),
    p_message TEXT,
    p_channel VARCHAR(20) DEFAULT 'telegram',
    p_quote_id UUID DEFAULT NULL,
    p_deal_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_notification_id UUID;
BEGIN
    INSERT INTO notifications (
        user_id, type, title, message, channel, quote_id, deal_id, status
    ) VALUES (
        p_user_id, p_type, p_title, p_message, p_channel, p_quote_id, p_deal_id, 'pending'
    )
    RETURNING id INTO v_notification_id;

    RETURN v_notification_id;
END;
$$;

-- Helper function to mark notification as sent
CREATE OR REPLACE FUNCTION mark_notification_sent(
    p_notification_id UUID,
    p_telegram_message_id BIGINT DEFAULT NULL,
    p_email_message_id VARCHAR(255) DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'sent',
        sent_at = NOW(),
        telegram_message_id = COALESCE(p_telegram_message_id, telegram_message_id),
        email_message_id = COALESCE(p_email_message_id, email_message_id)
    WHERE id = p_notification_id AND status = 'pending';
END;
$$;

-- Helper function to mark notification as failed
CREATE OR REPLACE FUNCTION mark_notification_failed(
    p_notification_id UUID,
    p_error_message TEXT
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'failed',
        sent_at = NOW(),
        error_message = p_error_message
    WHERE id = p_notification_id AND status = 'pending';
END;
$$;

-- Helper function to mark notification as read
CREATE OR REPLACE FUNCTION mark_notification_read(
    p_notification_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    UPDATE notifications
    SET
        status = 'read',
        read_at = NOW()
    WHERE id = p_notification_id
    AND user_id = auth.uid()
    AND status IN ('sent', 'delivered');
END;
$$;

-- Helper function to get pending notifications for a channel
CREATE OR REPLACE FUNCTION get_pending_notifications(
    p_channel VARCHAR(20),
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    notification_id UUID,
    user_id UUID,
    telegram_id BIGINT,
    type VARCHAR(50),
    title VARCHAR(255),
    message TEXT,
    quote_id UUID,
    deal_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id AS notification_id,
        n.user_id,
        tu.telegram_id,
        n.type,
        n.title,
        n.message,
        n.quote_id,
        n.deal_id
    FROM notifications n
    LEFT JOIN telegram_users tu ON n.user_id = tu.user_id AND tu.is_verified = true
    WHERE n.channel = p_channel
    AND n.status = 'pending'
    ORDER BY n.created_at ASC
    LIMIT p_limit;
END;
$$;

-- Grant execute permissions on functions
GRANT EXECUTE ON FUNCTION create_notification TO authenticated;
GRANT EXECUTE ON FUNCTION mark_notification_sent TO service_role;
GRANT EXECUTE ON FUNCTION mark_notification_failed TO service_role;
GRANT EXECUTE ON FUNCTION mark_notification_read TO authenticated;
GRANT EXECUTE ON FUNCTION get_pending_notifications TO service_role;

-- Comments on functions
COMMENT ON FUNCTION create_notification IS 'Creates a new notification for a user';
COMMENT ON FUNCTION mark_notification_sent IS 'Marks a notification as successfully sent (service role only)';
COMMENT ON FUNCTION mark_notification_failed IS 'Marks a notification as failed with error message (service role only)';
COMMENT ON FUNCTION mark_notification_read IS 'Marks a notification as read by the user';
COMMENT ON FUNCTION get_pending_notifications IS 'Gets pending notifications for a specific channel (service role only)';
