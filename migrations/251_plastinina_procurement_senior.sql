-- Remove head_of_procurement role from Plastinina, leaving only procurement_senior.
-- Per access-control steering: procurement_senior tier = PROCUREMENT_STAGE_ONLY
-- (sees only quotes currently in procurement stage). head_of_procurement tier =
-- PROCUREMENT_ALL_STAGES (sees all quotes across all stages). She should have the
-- stage-only view, not the all-stages view. The procurement_senior role itself was
-- added in migration 245; this migration just cleans up the duplicate assignment.

DELETE FROM kvota.user_roles
WHERE user_id = (
  SELECT id FROM auth.users WHERE email = 'ekaterina.pl@masterbearing.ru'
)
AND role_id = (
  SELECT id FROM kvota.roles
  WHERE slug = 'head_of_procurement'
    AND organization_id = '69ff6eda-3fd6-4d24-88b7-a9977c7a08b0'
);
