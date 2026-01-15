-- Migration: 035_add_modifications_to_approvals.sql
-- Description: Add modifications JSONB column to approvals table for v3.0
-- Feature: DB-019 (enhancement to existing approvals table)
-- Created: 2026-01-15

-- Purpose: Allow top_manager to make modifications during approval
-- The modifications are stored as JSONB and applied to the quote
-- when the approval is confirmed.

-- Add modifications column to store changes made during approval
ALTER TABLE approvals
ADD COLUMN IF NOT EXISTS modifications JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN approvals.modifications IS 'JSON object containing modifications made by approver during approval (e.g., {"margin_percent": 15, "payment_terms": "50% advance"})';

-- Example modifications structure:
-- {
--   "margin_percent": 15,           -- Changed margin
--   "payment_terms": "50% advance", -- Changed payment terms
--   "items": [                      -- Item-level changes
--     {
--       "item_id": "uuid-here",
--       "sale_price": 1500.00,
--       "notes": "Reduced price per manager request"
--     }
--   ],
--   "notes": "Approved with margin adjustment"
-- }

-- Create helper function to apply modifications to quote
CREATE OR REPLACE FUNCTION apply_approval_modifications(
    p_approval_id UUID
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_approval RECORD;
    v_mods JSONB;
    v_item JSONB;
BEGIN
    -- Get approval with modifications
    SELECT a.*, q.id as quote_id
    INTO v_approval
    FROM approvals a
    JOIN quotes q ON q.id = a.quote_id
    WHERE a.id = p_approval_id
    AND a.status = 'approved'
    AND a.modifications IS NOT NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    v_mods := v_approval.modifications;

    -- Apply quote-level modifications
    -- (These would be specific fields that top_manager can modify)
    -- For now, we just return true - actual field updates would be
    -- handled by the application layer after checking modifications

    RETURN TRUE;
END;
$$;

-- Create view to see pending approvals with their modifications
CREATE OR REPLACE VIEW v_approvals_with_modifications AS
SELECT
    a.id,
    a.quote_id,
    a.requested_by,
    a.approver_id,
    a.approval_type,
    a.reason,
    a.status,
    a.decision_comment,
    a.modifications,
    a.requested_at,
    a.decided_at,
    q.idn as quote_idn,
    q.workflow_status as quote_status,
    req_user.email as requester_email,
    app_user.email as approver_email,
    CASE
        WHEN a.modifications IS NOT NULL THEN jsonb_array_length(COALESCE(a.modifications->'items', '[]'::jsonb))
        ELSE 0
    END as modified_items_count
FROM approvals a
JOIN quotes q ON q.id = a.quote_id
LEFT JOIN auth.users req_user ON req_user.id = a.requested_by
LEFT JOIN auth.users app_user ON app_user.id = a.approver_id;

-- Create function to get approval history for a quote
CREATE OR REPLACE FUNCTION get_approval_history(p_quote_id UUID)
RETURNS TABLE (
    approval_id UUID,
    approval_type VARCHAR(50),
    status VARCHAR(20),
    reason TEXT,
    decision_comment TEXT,
    has_modifications BOOLEAN,
    modifications_summary TEXT,
    requester_email TEXT,
    approver_email TEXT,
    requested_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        a.id,
        a.approval_type,
        a.status,
        a.reason,
        a.decision_comment,
        a.modifications IS NOT NULL,
        CASE
            WHEN a.modifications IS NOT NULL THEN
                COALESCE(
                    array_to_string(
                        ARRAY(SELECT key FROM jsonb_object_keys(a.modifications) AS key LIMIT 5),
                        ', '
                    ),
                    'No changes'
                )
            ELSE NULL
        END,
        req_user.email,
        app_user.email,
        a.requested_at,
        a.decided_at
    FROM approvals a
    LEFT JOIN auth.users req_user ON req_user.id = a.requested_by
    LEFT JOIN auth.users app_user ON app_user.id = a.approver_id
    WHERE a.quote_id = p_quote_id
    ORDER BY a.requested_at DESC;
$$;

-- Grant appropriate permissions
GRANT EXECUTE ON FUNCTION apply_approval_modifications(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION get_approval_history(UUID) TO authenticated;
