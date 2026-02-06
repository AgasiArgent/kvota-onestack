-- Migration 156: Add is_lpr boolean to customer_contacts
-- Multiple contacts can be ЛПР (decision makers per department)

ALTER TABLE kvota.customer_contacts ADD COLUMN IF NOT EXISTS is_lpr BOOLEAN DEFAULT false;

COMMENT ON COLUMN kvota.customer_contacts.is_lpr IS 'Whether this contact is a decision maker (ЛПР). Multiple contacts per customer can have this flag.';
