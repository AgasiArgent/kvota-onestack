-- Migration: 315_add_pickup_address_and_supplier_contact_to_invoices
-- Description: Add pickup_address (free-text) and supplier_contact_id (FK to
--   supplier_contacts) to kvota.invoices so the КПП creation modal can
--   capture both before sending the КПП to the supplier (Testing 2 row 21).
-- Date: 2026-05-13

BEGIN;

SET search_path TO kvota;

-- 1. Free-text pickup address. Distinct from pickup_city/pickup_country —
--    those are structured columns wired to logistics auto-assignment, this
--    is the literal street address the driver will visit.
ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS pickup_address text;

COMMENT ON COLUMN kvota.invoices.pickup_address IS
    'Free-text pickup address for cargo, captured at КПП creation time. '
    'Distinct from pickup_city/pickup_country which feed logistics routing.';

-- 2. Selected supplier contact for the КПП. Nullable — legacy rows have
--    no contact and the field stays optional even on new КПП (the user can
--    fill it after picking the supplier). ON DELETE SET NULL keeps the
--    invoice if the contact is later removed.
ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS supplier_contact_id uuid
        REFERENCES kvota.supplier_contacts(id) ON DELETE SET NULL;

COMMENT ON COLUMN kvota.invoices.supplier_contact_id IS
    'Selected contact at the supplier (FK to supplier_contacts). Shown on '
    'the КПП together with the contact''s phone/email.';

CREATE INDEX IF NOT EXISTS idx_invoices_supplier_contact_id
    ON kvota.invoices(supplier_contact_id);

COMMIT;
