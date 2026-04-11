-- Phase 3: Shipping country code (ISO-2) and supplier Incoterms on procurement invoices.
-- Additive only. Coexists with the existing pickup_country text column.

ALTER TABLE kvota.invoices
    ADD COLUMN IF NOT EXISTS pickup_country_code CHAR(2),
    ADD COLUMN IF NOT EXISTS supplier_incoterms TEXT;

COMMENT ON COLUMN kvota.invoices.pickup_country_code IS
    'ISO 3166-1 alpha-2 code of the supplier pickup country. Populated alongside the legacy pickup_country text field by the Phase 3 dual-write logic. Used by Phase 4 VAT auto-detection.';

COMMENT ON COLUMN kvota.invoices.supplier_incoterms IS
    'Incoterms 2020 code (EXW/FCA/CPT/CIP/DAP/DPU/DDP/FAS/FOB/CFR/CIF) agreed with the supplier for this invoice. Informational only — not a calculation engine input.';

ALTER TABLE kvota.invoices
    DROP CONSTRAINT IF EXISTS invoices_pickup_country_code_format;

ALTER TABLE kvota.invoices
    ADD CONSTRAINT invoices_pickup_country_code_format
    CHECK (pickup_country_code IS NULL OR pickup_country_code ~ '^[A-Z]{2}$');
