-- Add supervisor_id to organization_members for department section in profile
ALTER TABLE kvota.organization_members
  ADD COLUMN IF NOT EXISTS supervisor_id UUID REFERENCES auth.users(id);
