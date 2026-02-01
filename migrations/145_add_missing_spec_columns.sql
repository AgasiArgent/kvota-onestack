-- Migration 145: Add missing columns to specifications table
-- These columns were defined in the original schema but may be missing

-- Add client_payment_term_after_upd if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota'
        AND table_name = 'specifications'
        AND column_name = 'client_payment_term_after_upd'
    ) THEN
        ALTER TABLE kvota.specifications ADD COLUMN client_payment_term_after_upd INTEGER;
        COMMENT ON COLUMN kvota.specifications.client_payment_term_after_upd IS 'Payment term in days after UPD';
    END IF;
END $$;

-- Verify the column was added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'kvota'
AND table_name = 'specifications'
AND column_name = 'client_payment_term_after_upd';
