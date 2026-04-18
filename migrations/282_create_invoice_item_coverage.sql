-- migrations/282_create_invoice_item_coverage.sql
-- Phase 5c Task 2: M:N junction between invoice_items and quote_items.
--
-- Carries a `ratio` coefficient (invoice_item units per quote_item unit)
-- so the calculation engine can express:
--   1:1     (ratio=1) — no structural change
--   split   (1 qi → N ii, each with its own ratio)
--   merge   (N qi → 1 ii, N coverage rows each ratio=1)
--
-- Both FKs CASCADE: deleting an invoice_item or a quote_item drops the
-- coverage row automatically (no orphans possible).
--
-- RLS pattern (per design.md §5.2):
--   Org boundary is resolved via invoice_items (already RLS-scoped by
--   mig 281). Role check mirrors invoice_items — 10 SELECT roles,
--   4 INSERT/UPDATE, 2 DELETE. Explicit role check is retained for
--   defense-in-depth when PostgREST runs without service_role bypass.
--
-- Source of truth: .kiro/specs/phase-5c-invoice-items/design.md §1.1 + §5.2

SET search_path TO kvota, public;

CREATE TABLE IF NOT EXISTS kvota.invoice_item_coverage (
    invoice_item_id UUID NOT NULL REFERENCES kvota.invoice_items(id) ON DELETE CASCADE,
    quote_item_id   UUID NOT NULL REFERENCES kvota.quote_items(id)   ON DELETE CASCADE,
    ratio           NUMERIC NOT NULL DEFAULT 1 CHECK (ratio > 0),
    PRIMARY KEY (invoice_item_id, quote_item_id)
);

-- Indexes — PK gives us (invoice_item_id, quote_item_id) for invoice_item
-- lookups but we also need efficient quote_item-side lookups (find all
-- invoice_items covering this quote_item).
CREATE INDEX IF NOT EXISTS idx_coverage_invoice_item
    ON kvota.invoice_item_coverage(invoice_item_id);

CREATE INDEX IF NOT EXISTS idx_coverage_quote_item
    ON kvota.invoice_item_coverage(quote_item_id);

-- Documentation
COMMENT ON TABLE kvota.invoice_item_coverage IS
    'Phase 5c: M:N junction between invoice_items and quote_items with a ratio coefficient. ratio = invoice_item_units per quote_item_unit. Supports 1:1, split (1 qi → N ii), and merge (N qi → 1 ii) compositions.';

COMMENT ON COLUMN kvota.invoice_item_coverage.ratio IS
    'Ratio = invoice_item_units per quote_item_unit. Example: qi "болт ×100" split into ii "болт ×100" (ratio=1) + ii "шайба ×200" (ratio=2); validation 100 = 100 × 1, 200 = 100 × 2.';

-- Enable Row Level Security
ALTER TABLE kvota.invoice_item_coverage ENABLE ROW LEVEL SECURITY;

-- Drop existing policies (safe no-op on first run)
DROP POLICY IF EXISTS invoice_item_coverage_select ON kvota.invoice_item_coverage;
DROP POLICY IF EXISTS invoice_item_coverage_insert ON kvota.invoice_item_coverage;
DROP POLICY IF EXISTS invoice_item_coverage_update ON kvota.invoice_item_coverage;
DROP POLICY IF EXISTS invoice_item_coverage_delete ON kvota.invoice_item_coverage;

-- SELECT: 10 roles (same breadth as invoice_items_select). Org containment
-- via invoice_item_id subquery — invoice_items already RLS-filters by org,
-- so membership in that set proves the invoice_item is in the user's org.
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
                      'admin', 'top_manager',
                      'procurement', 'procurement_senior', 'head_of_procurement',
                      'sales', 'head_of_sales',
                      'finance',
                      'quote_controller', 'spec_controller'
                  )
            )
        )
    );

-- INSERT: procurement-only (matches invoice_items_insert)
CREATE POLICY invoice_item_coverage_insert ON kvota.invoice_item_coverage
    FOR INSERT
    WITH CHECK (
        invoice_item_id IN (
            SELECT ii.id
            FROM kvota.invoice_items ii
            WHERE ii.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON r.id = ur.role_id
                WHERE ur.user_id = auth.uid()
                  AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
            )
        )
    );

-- UPDATE: procurement-only (same role set as INSERT)
CREATE POLICY invoice_item_coverage_update ON kvota.invoice_item_coverage
    FOR UPDATE
    USING (
        invoice_item_id IN (
            SELECT ii.id
            FROM kvota.invoice_items ii
            WHERE ii.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON r.id = ur.role_id
                WHERE ur.user_id = auth.uid()
                  AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
            )
        )
    );

-- DELETE: admin + head_of_procurement only (matches invoice_items_delete)
CREATE POLICY invoice_item_coverage_delete ON kvota.invoice_item_coverage
    FOR DELETE
    USING (
        invoice_item_id IN (
            SELECT ii.id
            FROM kvota.invoice_items ii
            WHERE ii.organization_id IN (
                SELECT ur.organization_id
                FROM kvota.user_roles ur
                JOIN kvota.roles r ON r.id = ur.role_id
                WHERE ur.user_id = auth.uid()
                  AND r.slug IN ('admin', 'head_of_procurement')
            )
        )
    );
