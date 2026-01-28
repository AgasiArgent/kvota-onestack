-- Migration 124: Create quote_change_requests table
-- For tracking client change requests and their resolution

CREATE TABLE IF NOT EXISTS kvota.quote_change_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    change_type VARCHAR(50) NOT NULL CHECK (change_type IN ('add_item', 'logistics', 'price', 'full')),
    client_comment TEXT,
    requested_by UUID REFERENCES kvota.users(id),
    requested_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_quote_change_requests_quote ON kvota.quote_change_requests(quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_change_requests_type ON kvota.quote_change_requests(change_type);
CREATE INDEX IF NOT EXISTS idx_quote_change_requests_requested_by ON kvota.quote_change_requests(requested_by);

-- Add comments for documentation
COMMENT ON TABLE kvota.quote_change_requests IS 'Tracks client change requests for quotes';
COMMENT ON COLUMN kvota.quote_change_requests.change_type IS 'Type of change: add_item, logistics, price, full';
COMMENT ON COLUMN kvota.quote_change_requests.client_comment IS 'Client comment explaining the change request';
COMMENT ON COLUMN kvota.quote_change_requests.resolved_at IS 'Timestamp when change request was resolved';
