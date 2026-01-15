-- Migration: 005_create_approvals_table
-- Description: Create approvals table for tracking approval requests
-- Feature #5 from features.json
-- Created: 2025-01-15

-- Table: approvals
-- Purpose: Track approval requests from quote controller to top manager
-- Used when: Quote controller (Zhanna) needs top manager approval for:
--   - Quotes with RUB currency
--   - Non-100% prepayment terms
--   - Markup below minimum
--   - LPR rewards included

CREATE TABLE IF NOT EXISTS approvals (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to the quote being approved
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,

    -- Who requested the approval
    requested_by UUID NOT NULL REFERENCES auth.users(id),

    -- Who should approve (top_manager or other approver)
    approver_id UUID NOT NULL REFERENCES auth.users(id),

    -- Type of approval (top_manager, customs, etc.)
    -- Allows different approval workflows in the future
    approval_type VARCHAR(50) NOT NULL DEFAULT 'top_manager',

    -- Why approval is needed (shown to approver)
    reason TEXT NOT NULL,

    -- Current status of the approval request
    -- pending: waiting for decision
    -- approved: approved by approver
    -- rejected: rejected by approver
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),

    -- Comment from approver when making decision
    decision_comment TEXT,

    -- When approval was requested
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),

    -- When decision was made (null if still pending)
    decided_at TIMESTAMP WITH TIME ZONE,

    -- Constraint: decided_at must be set when status changes from pending
    CONSTRAINT approvals_decided_at_check CHECK (
        (status = 'pending' AND decided_at IS NULL) OR
        (status != 'pending' AND decided_at IS NOT NULL)
    )
);

-- Comments for documentation
COMMENT ON TABLE approvals IS 'Approval requests for quotes requiring top manager or other approval';
COMMENT ON COLUMN approvals.quote_id IS 'Reference to the quote being approved';
COMMENT ON COLUMN approvals.requested_by IS 'User who requested the approval (usually quote_controller)';
COMMENT ON COLUMN approvals.approver_id IS 'User who should approve (usually top_manager)';
COMMENT ON COLUMN approvals.approval_type IS 'Type of approval: top_manager, customs, etc.';
COMMENT ON COLUMN approvals.reason IS 'Reason why approval is required (e.g., "RUB currency", "Low markup")';
COMMENT ON COLUMN approvals.status IS 'Status: pending, approved, rejected';
COMMENT ON COLUMN approvals.decision_comment IS 'Optional comment from approver with decision';
COMMENT ON COLUMN approvals.requested_at IS 'When the approval was requested';
COMMENT ON COLUMN approvals.decided_at IS 'When the decision was made';

-- Indexes for common queries
CREATE INDEX idx_approvals_quote_id ON approvals(quote_id);
CREATE INDEX idx_approvals_requested_by ON approvals(requested_by);
CREATE INDEX idx_approvals_approver_id ON approvals(approver_id);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_requested_at ON approvals(requested_at DESC);

-- Composite index for finding pending approvals for a specific approver
CREATE INDEX idx_approvals_approver_status ON approvals(approver_id, status);

-- Enable Row Level Security
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Policy: Users can view approvals related to quotes in their organization
CREATE POLICY "Users can view approvals in their organization" ON approvals
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON q.organization_id = om.organization_id
            WHERE q.id = approvals.quote_id
            AND om.user_id = auth.uid()
        )
    );

-- Policy: Quote controllers can create approval requests
CREATE POLICY "Quote controllers can create approvals" ON approvals
    FOR INSERT
    WITH CHECK (
        -- Must be the requester
        requested_by = auth.uid()
        AND
        -- Must have quote_controller role in the organization
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON q.organization_id = om.organization_id
            JOIN user_roles ur ON ur.user_id = auth.uid() AND ur.organization_id = q.organization_id
            JOIN roles r ON ur.role_id = r.id AND r.code = 'quote_controller'
            WHERE q.id = approvals.quote_id
            AND om.user_id = auth.uid()
        )
    );

-- Policy: Approvers can update their pending approvals (to approve/reject)
CREATE POLICY "Approvers can update their approvals" ON approvals
    FOR UPDATE
    USING (
        approver_id = auth.uid()
        AND status = 'pending'
    )
    WITH CHECK (
        approver_id = auth.uid()
    );

-- Note: No DELETE policy - approvals are immutable audit records
-- Once created, approvals should not be deleted

-- Add trigger to automatically set decided_at when status changes
CREATE OR REPLACE FUNCTION set_approval_decided_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status != 'pending' AND OLD.status = 'pending' THEN
        NEW.decided_at = now();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_approval_decided_at
    BEFORE UPDATE ON approvals
    FOR EACH ROW
    EXECUTE FUNCTION set_approval_decided_at();
