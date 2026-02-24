-- Migration 182: Add multi-platform support for training videos (Rutube, YouTube, Loom)
-- Widen youtube_id to handle Rutube hashes (32+ chars)
ALTER TABLE kvota.training_videos ALTER COLUMN youtube_id TYPE VARCHAR(100);

-- Add platform column
ALTER TABLE kvota.training_videos ADD COLUMN IF NOT EXISTS platform VARCHAR(20) NOT NULL DEFAULT 'rutube';

-- All pre-existing records were YouTube test videos — mark them correctly
UPDATE kvota.training_videos SET platform = 'youtube';

-- Track migration
INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (182, '182_training_videos_multi_platform.sql', now())
ON CONFLICT (id) DO NOTHING;
