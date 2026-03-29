-- Migration 236: Add INSERT/UPDATE policies for kvota-documents storage bucket
-- Fix: specification signed scan upload fails because no INSERT policy exists
-- Date: 2026-03-29

CREATE POLICY IF NOT EXISTS kvota_documents_insert ON storage.objects
FOR INSERT TO authenticated
WITH CHECK (bucket_id = 'kvota-documents');

CREATE POLICY IF NOT EXISTS kvota_documents_update ON storage.objects
FOR UPDATE TO authenticated
USING (bucket_id = 'kvota-documents');
