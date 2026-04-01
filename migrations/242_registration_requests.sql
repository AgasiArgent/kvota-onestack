-- Registration requests: staging table for new user onboarding.
-- Admin reviews these and manually creates accounts.

CREATE TABLE IF NOT EXISTS kvota.registration_requests (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT,
  position TEXT,
  department TEXT,
  manager TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.registration_requests IS 'Self-registration requests from new users awaiting admin approval';

-- No RLS — accessed only via service role from the API route
