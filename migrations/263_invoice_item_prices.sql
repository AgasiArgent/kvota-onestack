-- migrations/263_invoice_item_prices.sql
-- Phase 5b Task 1: Junction table for multi-supplier quote composition
--
-- Holds per-item prices from each competing supplier invoice.
-- Multiple invoices can hold prices for the same quote_item;
-- quote_items.composition_selected_invoice_id (added in migration 264)
-- picks which one is active for calculation.
--
-- Versioning:
--   version + frozen_at support KP-send-time freezing. Frozen rows are
--   immutable (enforced at service layer in composition_service.py);
--   edits create a new version row.
--
-- RLS:
--   Organization + role pattern, matching item_price_offers (migration
--   145, outside main tracking), purchasing_companies, customer_contracts,
--   and most other org-scoped kvota tables. Pre-check of 2026-04-10
--   revealed that kvota.invoices has RLS DISABLED entirely — the original
--   reference-predicate approach (USING invoice_id IN SELECT id FROM
--   kvota.invoices) would have been a no-op. See
--   .kiro/specs/phase-5b-quote-composition/research.md § "Pre-check findings".
--
--   Python API uses service_role and bypasses RLS entirely — these
--   policies primarily protect Next.js JS client direct reads via the
--   useQuoteComposition hook. Defense-in-depth layer.

SET search_path TO kvota, public;

CREATE TABLE IF NOT EXISTS kvota.invoice_item_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Junction keys
    invoice_id    UUID NOT NULL REFERENCES kvota.invoices(id)    ON DELETE CASCADE,
    quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,

    -- Organization boundary (for RLS)
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id),

    -- Price fields — mirror quote_items shape so composition_service can overlay
    purchase_price_original NUMERIC(18,4) NOT NULL,
    purchase_currency       TEXT          NOT NULL,
    base_price_vat          NUMERIC(18,4),
    price_includes_vat      BOOLEAN       NOT NULL DEFAULT false,

    -- Optional supplier-offer metadata
    production_time_days   INTEGER,
    minimum_order_quantity INTEGER,
    supplier_notes         TEXT,

    -- Versioning
    version    INTEGER     NOT NULL DEFAULT 1 CHECK (version >= 1),
    frozen_at  TIMESTAMPTZ,
    frozen_by  UUID        REFERENCES auth.users(id),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID        REFERENCES auth.users(id),

    CONSTRAINT uq_iip_invoice_item_version
        UNIQUE (invoice_id, quote_item_id, version)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_iip_invoice
    ON kvota.invoice_item_prices(invoice_id);

CREATE INDEX IF NOT EXISTS idx_iip_quote_item
    ON kvota.invoice_item_prices(quote_item_id);

CREATE INDEX IF NOT EXISTS idx_iip_organization
    ON kvota.invoice_item_prices(organization_id);

-- Partial index for "current editable row" lookups — the 99% path
CREATE INDEX IF NOT EXISTS idx_iip_active
    ON kvota.invoice_item_prices(quote_item_id, invoice_id)
    WHERE frozen_at IS NULL;

-- Documentation
COMMENT ON TABLE kvota.invoice_item_prices IS
    'Phase 5b: Per-item prices from supplier invoices. Junction between invoices and quote_items. Multiple invoices can hold prices for the same quote_item; quote_items.composition_selected_invoice_id (added in migration 264) picks the active one.';

COMMENT ON COLUMN kvota.invoice_item_prices.frozen_at IS
    'NULL = editable; NOT NULL = frozen snapshot (set when KP is sent or manually frozen). Frozen rows are immutable at the service layer — edits create a new version row.';

COMMENT ON COLUMN kvota.invoice_item_prices.version IS
    'Monotonic per (invoice_id, quote_item_id). Incremented when a new snapshot is created after an earlier version was frozen.';

COMMENT ON COLUMN kvota.invoice_item_prices.organization_id IS
    'Organization boundary — used by RLS policies. Populated at INSERT from quotes.organization_id (via JOIN in migration 265 backfill, or from request user context in application code).';

-- Enable Row Level Security
ALTER TABLE kvota.invoice_item_prices ENABLE ROW LEVEL SECURITY;

-- Drop existing policies (safe no-op on first run; enables idempotent re-run)
DROP POLICY IF EXISTS invoice_item_prices_select ON kvota.invoice_item_prices;
DROP POLICY IF EXISTS invoice_item_prices_insert ON kvota.invoice_item_prices;
DROP POLICY IF EXISTS invoice_item_prices_update ON kvota.invoice_item_prices;
DROP POLICY IF EXISTS invoice_item_prices_delete ON kvota.invoice_item_prices;

-- SELECT: broad audience — anyone who can see a quote needs to see its composition.
-- Excludes logistics and customs (ASSIGNED_ITEMS tier, composition not in their flow).
CREATE POLICY invoice_item_prices_select ON kvota.invoice_item_prices
    FOR SELECT
    USING (
        organization_id IN (
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
    );

-- INSERT: procurement only — rows are created during invoice creation
CREATE POLICY invoice_item_prices_insert ON kvota.invoice_item_prices
    FOR INSERT
    WITH CHECK (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

-- UPDATE: procurement only — direct updates only via the verified-edit-approval
-- flow (which runs under procurement user context)
CREATE POLICY invoice_item_prices_update ON kvota.invoice_item_prices
    FOR UPDATE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'procurement', 'procurement_senior', 'head_of_procurement')
        )
    );

-- DELETE: restricted to admin + head_of_procurement only (destructive repair action)
CREATE POLICY invoice_item_prices_delete ON kvota.invoice_item_prices
    FOR DELETE
    USING (
        organization_id IN (
            SELECT ur.organization_id
            FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid()
              AND r.slug IN ('admin', 'head_of_procurement')
        )
    );
