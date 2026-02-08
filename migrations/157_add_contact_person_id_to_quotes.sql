-- Migration 157: Add contact_person_id to quotes
-- Links a quote to a specific customer contact (ЛПР)

ALTER TABLE kvota.quotes ADD COLUMN IF NOT EXISTS contact_person_id UUID REFERENCES kvota.customer_contacts(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_quotes_contact_person_id ON kvota.quotes(contact_person_id);
