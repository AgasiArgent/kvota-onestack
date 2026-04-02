-- Backfill organization_id for user_feedback records where it's NULL
-- Joins user_feedback.user_id to organization_members.user_id to find the org
UPDATE kvota.user_feedback uf
SET organization_id = om.organization_id,
    updated_at = NOW()
FROM kvota.organization_members om
WHERE uf.user_id = om.user_id
  AND uf.organization_id IS NULL
  AND om.status = 'active';
