-- Migration 135: Fix workflow status constraint
-- The constraint 'valid_status' is outdated and needs to be replaced with the proper one

-- Drop old constraint if exists (might have different name in production)
ALTER TABLE kvota.quotes DROP CONSTRAINT IF EXISTS valid_status;
ALTER TABLE kvota.quotes DROP CONSTRAINT IF EXISTS quotes_workflow_status_check;

-- Add updated constraint with all workflow statuses
ALTER TABLE kvota.quotes
ADD CONSTRAINT quotes_workflow_status_check CHECK (
    workflow_status IS NULL OR
    workflow_status IN (
        'draft',
        'pending_procurement',
        'pending_logistics',
        'pending_customs',
        'pending_logistics_and_customs',
        'pending_sales_review',
        'pending_quote_control',
        'pending_approval',
        'approved',
        'sent_to_client',
        'client_negotiation',
        'pending_spec_control',
        'pending_signature',
        'deal',
        'rejected',
        'cancelled'
    )
);

COMMENT ON CONSTRAINT quotes_workflow_status_check ON kvota.quotes IS 'Ensures workflow_status contains only valid status values';
