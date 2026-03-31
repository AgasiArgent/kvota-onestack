-- Migration 240: Seed default deadline hours for all organizations
-- Each stage gets a 48-hour deadline. Admins can adjust per-org via settings.
-- ON CONFLICT DO NOTHING ensures idempotency if some orgs already have entries.
-- Date: 2026-03-30

INSERT INTO kvota.stage_deadlines (organization_id, stage, deadline_hours)
SELECT o.id, s.stage, 48
FROM kvota.organizations o
CROSS JOIN (VALUES
    ('pending_procurement'),
    ('pending_logistics'),
    ('pending_customs'),
    ('pending_logistics_and_customs'),
    ('pending_sales_review'),
    ('pending_quote_control'),
    ('pending_approval'),
    ('sent_to_client'),
    ('client_negotiation'),
    ('pending_spec_control'),
    ('pending_signature')
) AS s(stage)
ON CONFLICT (organization_id, stage) DO NOTHING;
