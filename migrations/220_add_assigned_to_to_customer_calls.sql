-- Add assigned_to column to calls for call assignment tracking
ALTER TABLE kvota.calls ADD COLUMN IF NOT EXISTS assigned_to UUID REFERENCES auth.users(id);
