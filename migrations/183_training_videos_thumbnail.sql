-- Migration 183: Add thumbnail_url column to training_videos
-- Stores fetched thumbnail URLs (from Loom oEmbed, YouTube CDN, etc.)
ALTER TABLE kvota.training_videos ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (183, '183_training_videos_thumbnail.sql', now())
ON CONFLICT (id) DO NOTHING;
