-- Migration 144: Create user_feedback table for bug reports and suggestions
-- Date: 2026-01-30

-- Create user_feedback table
CREATE TABLE IF NOT EXISTS kvota.user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Short ID for easy search (FB-YYMMDDHHMMSS)
    short_id VARCHAR(20) UNIQUE NOT NULL,

    -- User info (no FK to auth.users to avoid cross-schema complexity)
    user_id UUID,
    user_email TEXT,
    user_name TEXT,
    organization_id UUID REFERENCES kvota.organizations(id),
    organization_name TEXT,

    -- Context
    page_url TEXT NOT NULL,
    page_title TEXT,
    user_agent TEXT,

    -- Content
    feedback_type VARCHAR(20) NOT NULL,  -- 'bug', 'suggestion', 'question'
    description TEXT NOT NULL,

    -- Debug context (console errors, requests, form state)
    debug_context JSONB,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'new',  -- 'new', 'viewed', 'resolved'

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_user_feedback_short_id ON kvota.user_feedback(short_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_created ON kvota.user_feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_feedback_status ON kvota.user_feedback(status);
CREATE INDEX IF NOT EXISTS idx_user_feedback_user_id ON kvota.user_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_org_id ON kvota.user_feedback(organization_id);

-- GIN index for searching debug_context
CREATE INDEX IF NOT EXISTS idx_user_feedback_debug_context ON kvota.user_feedback
    USING GIN (debug_context jsonb_path_ops);

-- Add comment
COMMENT ON TABLE kvota.user_feedback IS 'User bug reports, suggestions, and questions with debug context';
COMMENT ON COLUMN kvota.user_feedback.short_id IS 'Human-readable ID for easy reference (FB-YYMMDDHHMMSS)';
COMMENT ON COLUMN kvota.user_feedback.debug_context IS 'JSONB with console errors, failed requests, form state, etc.';
