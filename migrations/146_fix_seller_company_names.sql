-- Migration: Fix seller company names to match calculation engine enum
-- Created: 2026-02-01
-- Problem: Database has "ООО Мастер Бэринг" but calc engine enum expects "МАСТЕР БЭРИНГ ООО"
-- Solution: Rename to match the exact format expected by SellerCompany enum

SET search_path TO kvota;

-- Rename seller company to match enum format
UPDATE kvota.seller_companies
SET name = 'МАСТЕР БЭРИНГ ООО'
WHERE name = 'ООО Мастер Бэринг';

-- Also update any specifications that might have the old format
UPDATE kvota.specifications
SET our_legal_entity = 'МАСТЕР БЭРИНГ ООО'
WHERE our_legal_entity = 'ООО Мастер Бэринг';

-- Valid SellerCompany enum values (for reference):
-- - МАСТЕР БЭРИНГ ООО
-- - ЦМТО1 ООО
-- - РАД РЕСУРС ООО
-- - TEXCEL OTOMOTİV TİCARET LİMİTED ŞİRKETİ
-- - GESTUS DIŞ TİCARET LİMİTED ŞİRKETİ
-- - UPDOOR Limited
