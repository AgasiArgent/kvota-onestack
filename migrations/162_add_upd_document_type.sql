-- Migration 162: Add 'upd' (УПД) document type to documents CHECK constraint
-- P2.10: Universal Transfer Document (Универсальный передаточный документ)

-- Drop and recreate the document_type check constraint with 'upd' added
ALTER TABLE kvota.documents
DROP CONSTRAINT IF EXISTS documents_document_type_check;

ALTER TABLE kvota.documents
ADD CONSTRAINT documents_document_type_check CHECK (
    document_type IS NULL OR document_type IN (
        'invoice_scan',
        'proforma_scan',
        'payment_order',
        'contract',
        'certificate',
        'ttn',
        'cmr',
        'bill_of_lading',
        'customs_declaration',
        'founding_docs',
        'license',
        'specification_signed_scan',
        'upd',
        'other'
    )
);
