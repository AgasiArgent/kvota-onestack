-- migrations/281_create_invoice_items.sql
-- Phase 5c Task 1: Per-invoice positions for multi-supplier composition.
--
-- Replaces Phase 5b's invoice_item_prices. Each row is one line item inside
-- one supplier's КП, with its own identity (product_name/supplier_sku/brand)
-- and supplier-specific attributes (weight, customs code, dimensions, ...).
-- Split/merge/substitution are expressed through this table plus the
-- invoice_item_coverage M:N junction created in migration 282.
--
-- Design contract: .kiro/specs/phase-5c-invoice-items/design.md §1.1 + §5.1
--
-- RLS pattern mirrors invoice_item_prices (migration 263) — the Python API
-- runs as service_role and bypasses RLS; these policies protect JS clients
-- that hit PostgREST directly from Next.js.

SET search_path TO kvota, public;

CREATE TABLE IF NOT EXISTS kvota.invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Parent + org boundary (org is redundant via invoice, but duplicated
    -- here so RLS predicates don't need a JOIN — same tradeoff as iip).
    invoice_id      UUID NOT NULL REFERENCES kvota.invoices(id)      ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES kvota.organizations(id),
    -- TODO: ON DELETE NO ACTION — implicit per SQL default; project convention
    -- is explicit. Not altered retroactively (migration 281 already applied on
    -- VPS dev; the FK semantics match the intended "organizations should not
    -- be deletable while invoice_items reference them" policy either way).
    position        INT  NOT NULL,

    -- Identity (supplier's version of the product; may differ from quote_items)
    product_name TEXT NOT NULL,
    supplier_sku TEXT,
    brand        TEXT,

    -- Pricing
    quantity                NUMERIC        NOT NULL CHECK (quantity > 0),
    purchase_price_original NUMERIC(18,4),
    purchase_currency       TEXT           NOT NULL,
    base_price_vat          NUMERIC(18,4),
    price_includes_vat      BOOLEAN        NOT NULL DEFAULT false,
    vat_rate                NUMERIC(5,2),

    -- Supplier-specific attributes (may vary per supplier for the same
    -- underlying product — that's why they live on invoice_items, not qi)
    weight_in_kg           NUMERIC,
    customs_code           TEXT,
    supplier_country       TEXT,
    production_time_days   INTEGER,
    minimum_order_quantity INTEGER,
    dimension_height_mm    INT,
    dimension_width_mm     INT,
    dimension_length_mm    INT,
    license_ds_cost        NUMERIC,
    license_ss_cost        NUMERIC,
    license_sgr_cost       NUMERIC,
    supplier_notes         TEXT,

    -- Versioning — same KP-send-time freeze pattern as Phase 5b iip
    version   INT         NOT NULL DEFAULT 1 CHECK (version >= 1),
    frozen_at TIMESTAMPTZ,
    frozen_by UUID        REFERENCES auth.users(id),

    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID        REFERENCES auth.users(id),

    CONSTRAINT uq_invoice_items_invoice_position_version
        UNIQUE (invoice_id, position, version)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice
    ON kvota.invoice_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_invoice_items_organization
    ON kvota.invoice_items(organization_id);

-- Partial index for "current editable row" lookups — the 99% path
CREATE INDEX IF NOT EXISTS idx_invoice_items_active
    ON kvota.invoice_items(invoice_id, position)
    WHERE frozen_at IS NULL;

-- Documentation
COMMENT ON TABLE kvota.invoice_items IS
    'Phase 5c: Per-invoice positions. One row per line item inside a supplier КП. Combined with invoice_item_coverage (mig 282), expresses 1:1, split (1 qi → N ii), and merge (N qi → 1 ii) compositions. Replaces invoice_item_prices (mig 263), which is dropped in migration 284 after backfill.';

COMMENT ON COLUMN kvota.invoice_items.frozen_at IS
    'NULL = editable; NOT NULL = frozen snapshot (set when KP is sent or manually frozen). Frozen rows are immutable at the service layer; edits create a new version row.';

COMMENT ON COLUMN kvota.invoice_items.version IS
    'Monotonic per (invoice_id, position). Incremented when a new snapshot is created after an earlier version was frozen.';

COMMENT ON COLUMN kvota.invoice_items.organization_id IS
    'Organization boundary — used by RLS policies. Populated at INSERT from invoices.organization_id (via JOIN in migration 283 backfill, or from request user context in application code).';

-- Enable Row Level Security
ALTER TABLE kvota.invoice_items ENABLE ROW LEVEL SECURITY;

-- Drop existing policies (safe no-op on first run; enables idempotent re-run)
DROP POLICY IF EXISTS invoice_items_select ON kvota.invoice_items;
DROP POLICY IF EXISTS invoice_items_insert ON kvota.invoice_items;
DROP POLICY IF EXISTS invoice_items_update ON kvota.invoice_items;
DROP POLICY IF EXISTS invoice_items_delete ON kvota.invoice_items;

-- SELECT: broad audience — anyone who can see a quote needs to see its
-- composition. Excludes logistics and customs (ASSIGNED_ITEMS tier,
-- composition not in their flow). Same role set as invoice_item_prices.
CREATE POLICY invoice_items_select ON kvota.invoice_items
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

-- INSERT: procurement-only — rows are created when procurement builds a КП
CREATE POLICY invoice_items_insert ON kvota.invoice_items
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

-- UPDATE: procurement-only — direct edits only via the verified
-- procurement-unlock flow (which runs under procurement user context)
CREATE POLICY invoice_items_update ON kvota.invoice_items
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

-- DELETE: restricted to admin + head_of_procurement only (destructive
-- repair action — same restriction as iip)
CREATE POLICY invoice_items_delete ON kvota.invoice_items
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
