-- Migration 196: Quote Comments Chat
-- Adds chat functionality to quote detail pages.
-- Tables: quote_comments (messages), quote_comment_reads (read receipts)

-- =============================================================================
-- 1. Comments table
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.quote_comments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id    UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL,
    body        TEXT NOT NULL CHECK (char_length(body) > 0 AND char_length(body) <= 4000),
    mentions    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_quote_comments_quote_id_created
    ON kvota.quote_comments (quote_id, created_at);

-- =============================================================================
-- 2. Read receipts table
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.quote_comment_reads (
    quote_id     UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL,
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT pk_quote_comment_reads PRIMARY KEY (quote_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_quote_comment_reads_user
    ON kvota.quote_comment_reads (user_id, quote_id);

-- =============================================================================
-- 3. Track migration
-- =============================================================================

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (196, '196_create_quote_comments', now())
ON CONFLICT (id) DO NOTHING;
