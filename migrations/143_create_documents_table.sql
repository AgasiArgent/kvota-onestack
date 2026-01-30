-- ===========================================================================
-- Migration 143: Create documents table in kvota schema
-- ===========================================================================
-- Description: Universal document storage metadata table for file attachments
-- Prerequisites: Supabase Storage bucket 'kvota-documents' must exist
-- Created: 2026-01-30
-- ===========================================================================

-- ============================================
-- DOCUMENTS TABLE
-- ============================================
-- Polymorphic document storage - files stored in Supabase Storage,
-- metadata stored here with references to parent entities

CREATE TABLE IF NOT EXISTS kvota.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id) ON DELETE CASCADE,

    -- Polymorphic entity binding
    entity_type VARCHAR(50) NOT NULL,  -- 'supplier_invoice', 'quote', 'specification', 'quote_item', 'supplier', 'customer', 'seller_company', 'buyer_company'
    entity_id UUID NOT NULL,

    -- File information
    storage_path TEXT NOT NULL,         -- Path in Supabase Storage bucket
    original_filename TEXT NOT NULL,    -- Original filename as uploaded
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),

    -- Document classification
    document_type VARCHAR(50),          -- 'invoice_scan', 'proforma_scan', 'payment_order', 'contract', 'certificate', 'ttn', 'cmr', 'bill_of_lading', 'customs_declaration', 'founding_docs', 'license', 'other'

    -- Additional metadata
    description TEXT,

    -- Audit
    uploaded_by UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT documents_storage_path_unique UNIQUE (storage_path),
    CONSTRAINT documents_entity_type_check CHECK (
        entity_type IN (
            'supplier_invoice',
            'quote',
            'specification',
            'quote_item',
            'supplier',
            'customer',
            'seller_company',
            'buyer_company'
        )
    ),
    CONSTRAINT documents_document_type_check CHECK (
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
            'other'
        )
    ),
    CONSTRAINT documents_file_size_positive CHECK (
        file_size_bytes IS NULL OR file_size_bytes > 0
    )
);

-- ============================================
-- INDEXES
-- ============================================

-- Primary lookup: find documents for an entity
CREATE INDEX IF NOT EXISTS idx_documents_entity
ON kvota.documents(entity_type, entity_id);

-- Organization filter
CREATE INDEX IF NOT EXISTS idx_documents_organization
ON kvota.documents(organization_id);

-- Document type filter
CREATE INDEX IF NOT EXISTS idx_documents_type
ON kvota.documents(organization_id, document_type)
WHERE document_type IS NOT NULL;

-- Recent documents
CREATE INDEX IF NOT EXISTS idx_documents_created
ON kvota.documents(organization_id, created_at DESC);

-- ============================================
-- ROW LEVEL SECURITY
-- ============================================

ALTER TABLE kvota.documents ENABLE ROW LEVEL SECURITY;

-- Users can view documents in their organization
CREATE POLICY documents_select_policy ON kvota.documents
    FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM kvota.user_roles WHERE user_id = auth.uid()
        )
    );

-- Users with appropriate roles can insert documents
CREATE POLICY documents_insert_policy ON kvota.documents
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'sales', 'sales_manager', 'procurement', 'quote_controller', 'finance', 'logistics', 'customs')
        )
    );

-- Users with appropriate roles can update documents (mainly description)
CREATE POLICY documents_update_policy ON kvota.documents
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'sales', 'sales_manager', 'procurement', 'quote_controller', 'finance', 'logistics', 'customs')
        )
    );

-- Users with appropriate roles can delete documents
CREATE POLICY documents_delete_policy ON kvota.documents
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON ur.role_id = r.id
            WHERE ur.user_id = auth.uid()
            AND r.slug IN ('admin', 'sales_manager', 'quote_controller', 'finance')
        )
    );

-- ============================================
-- COMMENTS
-- ============================================

COMMENT ON TABLE kvota.documents IS 'Universal document metadata storage - files in Supabase Storage, metadata here';
COMMENT ON COLUMN kvota.documents.entity_type IS 'Type of parent entity: supplier_invoice, quote, specification, quote_item, supplier, customer, seller_company, buyer_company';
COMMENT ON COLUMN kvota.documents.entity_id IS 'UUID of the parent entity';
COMMENT ON COLUMN kvota.documents.storage_path IS 'Full path to file in Supabase Storage bucket kvota-documents';
COMMENT ON COLUMN kvota.documents.original_filename IS 'Original filename as uploaded by user';
COMMENT ON COLUMN kvota.documents.document_type IS 'Classification: invoice_scan, proforma_scan, payment_order, contract, certificate, ttn, cmr, bill_of_lading, customs_declaration, founding_docs, license, other';

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 143: documents table created successfully in kvota schema';
END $$;
