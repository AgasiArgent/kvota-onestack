-- Migration 166: Backfill logistics_stages for all existing deals
-- P2.7+P2.8: Every deal should have 7 logistics stages initialized
-- This ensures existing deals get the logistics section on their detail page

INSERT INTO kvota.logistics_stages (deal_id, stage_code, status)
SELECT d.id, s.stage_code, 'pending'
FROM kvota.deals d
CROSS JOIN (
    VALUES
        ('first_mile'),
        ('hub'),
        ('hub_hub'),
        ('transit'),
        ('post_transit'),
        ('gtd_upload'),
        ('last_mile')
) AS s(stage_code)
WHERE NOT EXISTS (
    SELECT 1 FROM kvota.logistics_stages ls
    WHERE ls.deal_id = d.id AND ls.stage_code = s.stage_code
);
