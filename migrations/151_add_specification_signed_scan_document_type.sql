-- Migration 151: Add specification_signed_scan to documents document_type constraint
-- Feature #71: Signed scan upload for specifications needs this document type

-- Drop and recreate the check constraint with the new document type
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
        'specification_signed_scan',  -- NEW: For specification signed scans
        'other'
    )
);

-- Also add specification to allowed entity_types if not present
ALTER TABLE kvota.documents
DROP CONSTRAINT IF EXISTS documents_entity_type_check;

ALTER TABLE kvota.documents
ADD CONSTRAINT documents_entity_type_check CHECK (
    entity_type IN (
        'quote',
        'specification',  -- Ensure specification is allowed
        'deal',
        'supplier_invoice',
        'customer',
        'supplier',
        'seller_company',
        'buyer_company'
    )
);
