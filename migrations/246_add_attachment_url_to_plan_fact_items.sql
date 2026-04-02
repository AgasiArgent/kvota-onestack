-- Migration: 246_add_attachment_url_to_plan_fact_items.sql
-- Description: Add attachment_url column for payment receipt file uploads
--              and create payment-documents storage bucket

-- Add column to plan_fact_items
ALTER TABLE kvota.plan_fact_items
ADD COLUMN IF NOT EXISTS attachment_url TEXT;

COMMENT ON COLUMN kvota.plan_fact_items.attachment_url IS 'URL to attached payment document file (receipt/invoice) in Supabase Storage';

-- Create storage bucket for payment documents
-- Using public=true so URLs work without signed tokens
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'payment-documents',
    'payment-documents',
    true,
    10485760, -- 10 MB
    ARRAY['application/pdf', 'image/jpeg', 'image/png']
)
ON CONFLICT (id) DO NOTHING;

-- Storage policies for payment-documents bucket
CREATE POLICY IF NOT EXISTS payment_documents_select ON storage.objects
FOR SELECT TO authenticated
USING (bucket_id = 'payment-documents');

CREATE POLICY IF NOT EXISTS payment_documents_insert ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'payment-documents');

CREATE POLICY IF NOT EXISTS payment_documents_update ON storage.objects
FOR UPDATE TO authenticated
USING (bucket_id = 'payment-documents');
