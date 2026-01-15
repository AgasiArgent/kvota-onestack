-- Migration: 004_create_workflow_transitions_table.sql
-- Description: Create workflow_transitions table for audit logging of status changes
-- Feature #4 from features.json
-- Created: 2025-01-15

-- Table: workflow_transitions
-- Purpose: Audit log for all workflow status transitions on quotes
-- This table records every status change, who made it, and why

CREATE TABLE IF NOT EXISTS workflow_transitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Reference to the quote
    quote_id UUID NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,

    -- Status transition
    from_status VARCHAR(50) NOT NULL,
    to_status VARCHAR(50) NOT NULL,

    -- Actor who made the transition
    actor_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(50) NOT NULL,

    -- Optional comment explaining the transition
    comment TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for efficient querying
-- Index for looking up transitions by quote (most common query)
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_id
    ON workflow_transitions(quote_id);

-- Index for looking up transitions by actor
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_actor_id
    ON workflow_transitions(actor_id);

-- Index for filtering by to_status (useful for analytics)
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_to_status
    ON workflow_transitions(to_status);

-- Composite index for time-based queries by quote
CREATE INDEX IF NOT EXISTS idx_workflow_transitions_quote_created
    ON workflow_transitions(quote_id, created_at DESC);

-- Enable Row Level Security
ALTER TABLE workflow_transitions ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- Policy: Users can view transitions for quotes in their organization
-- This is a read-only audit log, so we allow viewing based on organization membership
CREATE POLICY "Users can view transitions for their organization quotes"
    ON workflow_transitions
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON om.organization_id = q.organization_id
            WHERE q.id = workflow_transitions.quote_id
            AND om.user_id = auth.uid()
        )
    );

-- Policy: Only the system or authenticated users with proper role can insert transitions
-- In practice, transitions are created through the workflow service
CREATE POLICY "Authenticated users can insert transitions for their organization quotes"
    ON workflow_transitions
    FOR INSERT
    WITH CHECK (
        auth.uid() IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM quotes q
            JOIN organization_members om ON om.organization_id = q.organization_id
            WHERE q.id = workflow_transitions.quote_id
            AND om.user_id = auth.uid()
        )
    );

-- No UPDATE or DELETE policies - audit log is immutable
-- Transitions should never be modified or deleted

-- Add comments for documentation
COMMENT ON TABLE workflow_transitions IS 'Audit log of all workflow status transitions for quotes';
COMMENT ON COLUMN workflow_transitions.id IS 'Unique identifier for the transition record';
COMMENT ON COLUMN workflow_transitions.quote_id IS 'Reference to the quote that was transitioned';
COMMENT ON COLUMN workflow_transitions.from_status IS 'Previous workflow status before transition';
COMMENT ON COLUMN workflow_transitions.to_status IS 'New workflow status after transition';
COMMENT ON COLUMN workflow_transitions.actor_id IS 'User who performed the transition';
COMMENT ON COLUMN workflow_transitions.actor_role IS 'Role of the actor at the time of transition';
COMMENT ON COLUMN workflow_transitions.comment IS 'Optional comment explaining the transition reason';
COMMENT ON COLUMN workflow_transitions.created_at IS 'Timestamp when the transition occurred';
