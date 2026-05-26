-- Migration 330: widen invoice_items + invoice_item_coverage SELECT RLS to
--                customs + logistics tiers (Testing 2 row 71 follow-up)
--
-- The PR #216 cargo-info refactor introduced four totals (Валюта / Стоимость /
-- Кол-во / Ед.изм.) that hang off `items_aggregate`, computed in
-- `fetchQuoteInvoices` by reading kvota.invoice_items joined with
-- kvota.invoice_item_coverage → kvota.quote_items.
--
-- Tester reported (FB-260524, post-deploy of #216) that the four fields appear
-- under admin but stay empty for the customs lead (head_of_customs / МВЭД) and
-- the customs manager (customs). Root cause: the existing SELECT policies on
-- both tables grant access to sales / procurement / finance / controllers /
-- admin / top_manager but NOT to customs or logistics tiers, so PostgREST
-- silently returns an empty result set and the rollup ends up with
-- `aggregate = null`. The InvoiceCargoSummary then renders without the four
-- fields. The cargo summary itself is gated on the same component used on the
-- logistics step where the same RLS gap would bite.
--
-- Fix: expand SELECT RLS on both tables to include customs / head_of_customs
-- and logistics / head_of_logistics. WRITE policies (INSERT / UPDATE /
-- DELETE) stay narrow — only procurement tier + admin can mutate
-- invoice_items, since the cargo data is owned by procurement. Customs /
-- logistics need read-only visibility for sanity-checking what they are
-- moving / clearing.
--
-- Roles added to SELECT scope on BOTH tables:
--   - customs           (МОТ / customs manager)
--   - head_of_customs   (МВЭД)
--   - logistics         (МОЛ)
--   - head_of_logistics (МОЛ lead — already covered for some adjacent tables)
--
-- Migration is idempotent: DROP POLICY IF EXISTS + CREATE POLICY.

SET search_path TO kvota;

-- ---------------------------------------------------------------------------
-- invoice_items.invoice_items_select
-- ---------------------------------------------------------------------------
DROP POLICY IF EXISTS invoice_items_select ON kvota.invoice_items;
CREATE POLICY invoice_items_select ON kvota.invoice_items
    FOR SELECT
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN (
                  'admin',
                  'top_manager',
                  'procurement',
                  'procurement_senior',
                  'head_of_procurement',
                  'sales',
                  'head_of_sales',
                  'finance',
                  'quote_controller',
                  'spec_controller',
                  -- Testing 2 row 71 follow-up: read-only access for customs +
                  -- logistics tiers so the cargo-info panel («Валюта /
                  -- Стоимость / Кол-во / Ед.изм.» per КПП) renders for these
                  -- roles too.
                  'customs',
                  'head_of_customs',
                  'logistics',
                  'head_of_logistics'
              )
        )
    );

-- ---------------------------------------------------------------------------
-- invoice_item_coverage.invoice_item_coverage_select
-- ---------------------------------------------------------------------------
-- Required because the cargo aggregate query embeds invoice_item_coverage
-- via `!inner` (PostgREST FK embed) to pull quote_items.unit. RLS-gated
-- embeds become empty arrays at the parent row when the child policy
-- denies — the parent row still loads (invoice_items SELECT passes for
-- the role) but `invoice_item_coverage` arrives as `[]`, so the Ед.изм.
-- aggregate is empty. We mirror the parent table's role list verbatim.
DROP POLICY IF EXISTS invoice_item_coverage_select ON kvota.invoice_item_coverage;
CREATE POLICY invoice_item_coverage_select ON kvota.invoice_item_coverage
    FOR SELECT
    USING (
        invoice_item_id IN (
            SELECT ii.id
            FROM kvota.invoice_items ii
            WHERE ii.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON r.id = ur.role_id
                WHERE ur.user_id = auth.uid()
                  AND r.slug IN (
                      'admin',
                      'top_manager',
                      'procurement',
                      'procurement_senior',
                      'head_of_procurement',
                      'sales',
                      'head_of_sales',
                      'finance',
                      'quote_controller',
                      'spec_controller',
                      'customs',
                      'head_of_customs',
                      'logistics',
                      'head_of_logistics'
                  )
            )
        )
    );

COMMENT ON POLICY invoice_items_select ON kvota.invoice_items IS
    'Read access for admin / top_manager / procurement tier / sales tier / finance / controllers + customs + logistics (Testing 2 row 71 follow-up — cargo info panel needs items_aggregate visible to customs / logistics).';

COMMENT ON POLICY invoice_item_coverage_select ON kvota.invoice_item_coverage IS
    'Mirrors invoice_items_select role list — the cargo aggregate embed (`invoice_item_coverage!inner(quote_items!inner(unit))`) would return [] under RLS otherwise and Ед.изм. would never populate for customs / logistics.';
