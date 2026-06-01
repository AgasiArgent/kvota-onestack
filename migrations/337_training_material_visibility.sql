-- Migration 337: Per-material visibility for training videos (Testing 2 row 54)
-- Tester ask: «Обучение должно быть разделено между отделами и сотрудниками
-- с разными должностями» — split training material access by DEPARTMENT and ROLE.
--
-- Adds two array columns to kvota.training_videos:
--   visible_departments  — department slugs allowed to see the material
--   visible_role_slugs   — role slugs (kvota.roles.slug) allowed to see it
--
-- Semantics: a material is visible to a user when BOTH arrays are empty
-- (visible to everyone) OR the user's department is in visible_departments
-- OR one of the user's role slugs is in visible_role_slugs (union of the two
-- allow-lists). Filtering is enforced on the data path in the Next.js query
-- layer (see frontend/src/entities/training-video/queries.ts) using the
-- canonical department mapping in frontend/src/shared/lib/roles.ts.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS. Safe to re-run.

BEGIN;

ALTER TABLE kvota.training_videos
    ADD COLUMN IF NOT EXISTS visible_departments TEXT[] NOT NULL DEFAULT '{}'::text[];

ALTER TABLE kvota.training_videos
    ADD COLUMN IF NOT EXISTS visible_role_slugs TEXT[] NOT NULL DEFAULT '{}'::text[];

-- GIN indexes accelerate the array-overlap (&&) checks used by the viewer
-- filter when materials carry visibility restrictions.
CREATE INDEX IF NOT EXISTS idx_training_videos_visible_departments
    ON kvota.training_videos USING GIN (visible_departments);

CREATE INDEX IF NOT EXISTS idx_training_videos_visible_role_slugs
    ON kvota.training_videos USING GIN (visible_role_slugs);

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (337, '337_training_material_visibility.sql', now())
ON CONFLICT (id) DO NOTHING;

COMMIT;
