-- Migration: 041_extend_notifications_v3.sql
-- Feature: DB-025 - Extend notifications table for v3.0
-- Description: Verify notifications table exists, add organization_id and v3.0 enhancements
-- Version: 3.0

-- ============================================
-- VERIFY EXISTING TABLE
-- The notifications table was created in migration 011
-- We need to add organization_id for multi-tenant isolation
-- ============================================

-- Add organization_id column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'organization_id'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

        -- Backfill organization_id from user's primary organization
        UPDATE notifications n
        SET organization_id = (
            SELECT om.organization_id
            FROM organization_members om
            WHERE om.user_id = n.user_id
            LIMIT 1
        )
        WHERE n.organization_id IS NULL;

        RAISE NOTICE 'Added organization_id column to notifications table';
    END IF;
END $$;

-- Add specification_id column for specification-related notifications
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'specification_id'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN specification_id UUID REFERENCES specifications(id) ON DELETE SET NULL;

        RAISE NOTICE 'Added specification_id column to notifications table';
    END IF;
END $$;

-- Add approval_id column for approval-related notifications
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'approval_id'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN approval_id UUID REFERENCES approvals(id) ON DELETE SET NULL;

        RAISE NOTICE 'Added approval_id column to notifications table';
    END IF;
END $$;

-- Add priority column for urgent notifications
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'priority'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN priority VARCHAR(20) DEFAULT 'normal'
        CHECK (priority IN ('low', 'normal', 'high', 'urgent'));

        RAISE NOTICE 'Added priority column to notifications table';
    END IF;
END $$;

-- Add metadata column for additional context
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'metadata'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN metadata JSONB DEFAULT '{}';

        RAISE NOTICE 'Added metadata column to notifications table';
    END IF;
END $$;

-- Add expires_at column for time-sensitive notifications
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'notifications'
        AND column_name = 'expires_at'
    ) THEN
        ALTER TABLE notifications
        ADD COLUMN expires_at TIMESTAMPTZ;

        RAISE NOTICE 'Added expires_at column to notifications table';
    END IF;
END $$;

-- Update type constraint to include v3.0 notification types
-- First check existing constraint
DO $$
BEGIN
    -- Drop old constraint if exists
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'valid_notification_type'
    ) THEN
        ALTER TABLE notifications DROP CONSTRAINT valid_notification_type;
    END IF;

    -- Add new constraint with v3.0 types
    ALTER TABLE notifications ADD CONSTRAINT valid_notification_type CHECK (
        type IN (
            -- Original types
            'task_assigned',
            'approval_required',
            'approval_decision',
            'status_changed',
            'returned_for_revision',
            'comment_added',
            'deadline_reminder',
            'system_message',
            -- v3.0 new types
            'workflow_transition',      -- Quote moved to next status
            'procurement_complete',     -- All brands evaluated
            'logistics_complete',       -- Logistics data filled
            'customs_complete',         -- Customs data filled
            'spec_ready',               -- Specification ready for review
            'spec_signed',              -- Specification signed
            'deal_created',             -- New deal created
            'payment_due',              -- Payment deadline approaching
            'payment_received',         -- Payment registered
            'invoice_received',         -- New supplier invoice
            'invoice_overdue'           -- Supplier invoice overdue
        )
    );

    RAISE NOTICE 'Updated notification type constraint for v3.0';
END $$;

-- ============================================
-- INDEXES
-- ============================================

-- Index on organization_id for multi-tenant queries
CREATE INDEX IF NOT EXISTS idx_notifications_organization_id
    ON notifications(organization_id);

-- Index on specification_id
CREATE INDEX IF NOT EXISTS idx_notifications_specification_id
    ON notifications(specification_id)
    WHERE specification_id IS NOT NULL;

-- Index on approval_id
CREATE INDEX IF NOT EXISTS idx_notifications_approval_id
    ON notifications(approval_id)
    WHERE approval_id IS NOT NULL;

-- Index on priority for urgent notifications
CREATE INDEX IF NOT EXISTS idx_notifications_priority
    ON notifications(priority)
    WHERE priority IN ('high', 'urgent');

-- Index on expires_at for cleanup jobs
CREATE INDEX IF NOT EXISTS idx_notifications_expires_at
    ON notifications(expires_at)
    WHERE expires_at IS NOT NULL;

-- Composite index for organization + user queries
CREATE INDEX IF NOT EXISTS idx_notifications_org_user
    ON notifications(organization_id, user_id);

-- ============================================
-- RLS POLICY UPDATES
-- ============================================

-- Drop old policies that don't include organization_id
DROP POLICY IF EXISTS notifications_select_own ON notifications;
DROP POLICY IF EXISTS notifications_insert ON notifications;
DROP POLICY IF EXISTS notifications_update_own ON notifications;

-- New policy: Users can view their own notifications in their organization
CREATE POLICY notifications_select_own ON notifications
    FOR SELECT
    USING (
        auth.uid() = user_id
        OR organization_id IN (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
            AND role IN ('admin', 'owner')
        )
    );

-- New policy: System can insert notifications within organization context
CREATE POLICY notifications_insert ON notifications
    FOR INSERT
    WITH CHECK (
        -- Either service role or user in same organization
        organization_id IN (
            SELECT organization_id
            FROM organization_members
            WHERE user_id = auth.uid()
        )
    );

-- New policy: Users can update (mark as read) their own notifications
CREATE POLICY notifications_update_own ON notifications
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ============================================
-- HELPER FUNCTIONS (v3.0)
-- ============================================

-- Enhanced create_notification with organization_id
CREATE OR REPLACE FUNCTION create_notification_v3(
    p_organization_id UUID,
    p_user_id UUID,
    p_type VARCHAR(50),
    p_title VARCHAR(255),
    p_message TEXT,
    p_channel VARCHAR(20) DEFAULT 'telegram',
    p_priority VARCHAR(20) DEFAULT 'normal',
    p_quote_id UUID DEFAULT NULL,
    p_deal_id UUID DEFAULT NULL,
    p_specification_id UUID DEFAULT NULL,
    p_approval_id UUID DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}',
    p_expires_at TIMESTAMPTZ DEFAULT NULL
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
        organization_id, user_id, type, title, message, channel, priority,
        quote_id, deal_id, specification_id, approval_id, metadata, expires_at, status
    ) VALUES (
        p_organization_id, p_user_id, p_type, p_title, p_message, p_channel, p_priority,
        p_quote_id, p_deal_id, p_specification_id, p_approval_id, p_metadata, p_expires_at, 'pending'
    )
    RETURNING id INTO v_notification_id;

    RETURN v_notification_id;
END;
$$;

-- Create workflow transition notification
CREATE OR REPLACE FUNCTION create_workflow_notification(
    p_quote_id UUID,
    p_from_status VARCHAR(50),
    p_to_status VARCHAR(50),
    p_actor_id UUID,
    p_target_user_ids UUID[] DEFAULT NULL
)
RETURNS SETOF UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_quote RECORD;
    v_user_id UUID;
    v_notification_id UUID;
    v_title TEXT;
    v_message TEXT;
BEGIN
    -- Get quote info
    SELECT q.*, c.name as customer_name
    INTO v_quote
    FROM quotes q
    LEFT JOIN customers c ON q.customer_id = c.id
    WHERE q.id = p_quote_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Build notification content
    v_title := 'KП ' || COALESCE(v_quote.idn, v_quote.id::text) || ': ' || p_to_status;
    v_message := 'Статус изменён: ' || COALESCE(p_from_status, 'новый') || ' → ' || p_to_status;
    IF v_quote.customer_name IS NOT NULL THEN
        v_message := v_message || E'\nКлиент: ' || v_quote.customer_name;
    END IF;

    -- Notify target users
    IF p_target_user_ids IS NOT NULL THEN
        FOREACH v_user_id IN ARRAY p_target_user_ids LOOP
            SELECT create_notification_v3(
                v_quote.organization_id,
                v_user_id,
                'workflow_transition',
                v_title,
                v_message,
                'telegram',
                'normal',
                p_quote_id,
                NULL,  -- deal_id
                NULL,  -- specification_id
                NULL,  -- approval_id
                jsonb_build_object(
                    'from_status', p_from_status,
                    'to_status', p_to_status,
                    'actor_id', p_actor_id
                )
            ) INTO v_notification_id;

            RETURN NEXT v_notification_id;
        END LOOP;
    END IF;
END;
$$;

-- Create approval request notification (for top_manager)
CREATE OR REPLACE FUNCTION create_approval_notification(
    p_approval_id UUID,
    p_priority VARCHAR(20) DEFAULT 'high'
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_approval RECORD;
    v_quote RECORD;
    v_notification_id UUID;
    v_title TEXT;
    v_message TEXT;
BEGIN
    -- Get approval info
    SELECT a.*, q.idn as quote_idn, q.organization_id, c.name as customer_name
    INTO v_approval
    FROM approvals a
    JOIN quotes q ON a.quote_id = q.id
    LEFT JOIN customers c ON q.customer_id = c.id
    WHERE a.id = p_approval_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    -- Build notification content
    v_title := 'Требуется согласование: КП ' || COALESCE(v_approval.quote_idn, v_approval.quote_id::text);
    v_message := 'Тип: ' || v_approval.approval_type;
    IF v_approval.reason IS NOT NULL THEN
        v_message := v_message || E'\nПричина: ' || v_approval.reason;
    END IF;
    IF v_approval.customer_name IS NOT NULL THEN
        v_message := v_message || E'\nКлиент: ' || v_approval.customer_name;
    END IF;

    -- Create notification for approver
    SELECT create_notification_v3(
        v_approval.organization_id,
        v_approval.approver_id,
        'approval_required',
        v_title,
        v_message,
        'telegram',
        p_priority,
        v_approval.quote_id,
        NULL,
        NULL,
        p_approval_id,
        jsonb_build_object(
            'approval_type', v_approval.approval_type,
            'requested_by', v_approval.requested_by
        )
    ) INTO v_notification_id;

    RETURN v_notification_id;
END;
$$;

-- Get pending notifications for sending (enhanced for v3.0)
CREATE OR REPLACE FUNCTION get_pending_notifications_v3(
    p_channel VARCHAR(20),
    p_organization_id UUID DEFAULT NULL,
    p_priority VARCHAR(20) DEFAULT NULL,
    p_limit INTEGER DEFAULT 100
)
RETURNS TABLE (
    notification_id UUID,
    organization_id UUID,
    user_id UUID,
    telegram_id BIGINT,
    type VARCHAR(50),
    title VARCHAR(255),
    message TEXT,
    priority VARCHAR(20),
    quote_id UUID,
    deal_id UUID,
    specification_id UUID,
    approval_id UUID,
    metadata JSONB
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        n.id AS notification_id,
        n.organization_id,
        n.user_id,
        tu.telegram_id,
        n.type,
        n.title,
        n.message,
        n.priority,
        n.quote_id,
        n.deal_id,
        n.specification_id,
        n.approval_id,
        n.metadata
    FROM notifications n
    LEFT JOIN telegram_users tu ON n.user_id = tu.user_id
        AND tu.is_verified = true
        AND tu.is_active = true
    WHERE n.channel = p_channel
    AND n.status = 'pending'
    AND (n.expires_at IS NULL OR n.expires_at > NOW())
    AND (p_organization_id IS NULL OR n.organization_id = p_organization_id)
    AND (p_priority IS NULL OR n.priority = p_priority)
    ORDER BY
        CASE n.priority
            WHEN 'urgent' THEN 1
            WHEN 'high' THEN 2
            WHEN 'normal' THEN 3
            WHEN 'low' THEN 4
            ELSE 5
        END,
        n.created_at ASC
    LIMIT p_limit;
END;
$$;

-- Get notification counts by status for user dashboard
CREATE OR REPLACE FUNCTION get_notification_counts(
    p_user_id UUID,
    p_organization_id UUID DEFAULT NULL
)
RETURNS TABLE (
    total INTEGER,
    pending INTEGER,
    unread INTEGER,
    urgent INTEGER
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::INTEGER AS total,
        COUNT(*) FILTER (WHERE status = 'pending')::INTEGER AS pending,
        COUNT(*) FILTER (WHERE status NOT IN ('read', 'failed'))::INTEGER AS unread,
        COUNT(*) FILTER (WHERE priority IN ('high', 'urgent') AND status NOT IN ('read', 'failed'))::INTEGER AS urgent
    FROM notifications
    WHERE user_id = p_user_id
    AND (p_organization_id IS NULL OR organization_id = p_organization_id);
END;
$$;

-- Mark all notifications as read for user
CREATE OR REPLACE FUNCTION mark_all_notifications_read(
    p_user_id UUID,
    p_organization_id UUID DEFAULT NULL
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH updated AS (
        UPDATE notifications
        SET
            status = 'read',
            read_at = NOW()
        WHERE user_id = p_user_id
        AND (p_organization_id IS NULL OR organization_id = p_organization_id)
        AND status IN ('sent', 'delivered')
        RETURNING id
    )
    SELECT COUNT(*) INTO v_count FROM updated;

    RETURN v_count;
END;
$$;

-- Cleanup expired notifications
CREATE OR REPLACE FUNCTION cleanup_expired_notifications()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    WITH deleted AS (
        DELETE FROM notifications
        WHERE expires_at IS NOT NULL
        AND expires_at < NOW()
        AND status = 'pending'
        RETURNING id
    )
    SELECT COUNT(*) INTO v_count FROM deleted;

    RETURN v_count;
END;
$$;

-- ============================================
-- VIEW: notifications_list
-- For dashboard and notification center
-- ============================================

CREATE OR REPLACE VIEW v_notifications_list AS
SELECT
    n.id,
    n.organization_id,
    n.user_id,
    n.type,
    n.title,
    n.message,
    n.channel,
    n.priority,
    n.status,
    n.quote_id,
    n.deal_id,
    n.specification_id,
    n.approval_id,
    n.metadata,
    n.telegram_message_id,
    n.sent_at,
    n.delivered_at,
    n.read_at,
    n.expires_at,
    n.created_at,
    -- Related quote info
    q.idn AS quote_idn,
    -- Related deal info
    d.deal_number,
    -- Related approval info
    a.approval_type,
    a.status AS approval_status
FROM notifications n
LEFT JOIN quotes q ON n.quote_id = q.id
LEFT JOIN deals d ON n.deal_id = d.id
LEFT JOIN approvals a ON n.approval_id = a.id;

-- ============================================
-- GRANTS
-- ============================================

GRANT EXECUTE ON FUNCTION create_notification_v3 TO authenticated;
GRANT EXECUTE ON FUNCTION create_workflow_notification TO authenticated;
GRANT EXECUTE ON FUNCTION create_approval_notification TO authenticated;
GRANT EXECUTE ON FUNCTION get_pending_notifications_v3 TO service_role;
GRANT EXECUTE ON FUNCTION get_notification_counts TO authenticated;
GRANT EXECUTE ON FUNCTION mark_all_notifications_read TO authenticated;
GRANT EXECUTE ON FUNCTION cleanup_expired_notifications TO service_role;

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON COLUMN notifications.organization_id IS 'Organization context for multi-tenant isolation (v3.0)';
COMMENT ON COLUMN notifications.specification_id IS 'Related specification for spec notifications (v3.0)';
COMMENT ON COLUMN notifications.approval_id IS 'Related approval for approval notifications (v3.0)';
COMMENT ON COLUMN notifications.priority IS 'Notification priority: low, normal, high, urgent (v3.0)';
COMMENT ON COLUMN notifications.metadata IS 'Additional context data as JSONB (v3.0)';
COMMENT ON COLUMN notifications.expires_at IS 'Expiration time for time-sensitive notifications (v3.0)';

COMMENT ON FUNCTION create_notification_v3 IS 'Create notification with full v3.0 parameters';
COMMENT ON FUNCTION create_workflow_notification IS 'Create workflow transition notifications for target users';
COMMENT ON FUNCTION create_approval_notification IS 'Create approval request notification for approver';
COMMENT ON FUNCTION get_pending_notifications_v3 IS 'Get pending notifications with priority ordering (v3.0)';
COMMENT ON FUNCTION get_notification_counts IS 'Get notification counts for user dashboard';
COMMENT ON FUNCTION mark_all_notifications_read IS 'Mark all user notifications as read';
COMMENT ON FUNCTION cleanup_expired_notifications IS 'Delete expired pending notifications (service role)';
