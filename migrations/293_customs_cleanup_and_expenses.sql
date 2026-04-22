-- Migration 293: Customs columns cleanup + expenses tables.
-- Wave 1 Tasks 2 + 3 of logistics-customs-redesign spec (R7, R9).
--
-- Cleanup (Task 2):
--   - DROP  customs_ds_sgr (duplicate of structured license_ds/ss/sgr columns
--                           added earlier)
--   - DROP  customs_marking (duplicate of customs_honest_mark)
--   - RENAME customs_psn_pts → customs_psm_pts (typo fix: ПСН → ПСМ)
--
-- Expenses (Task 3):
--   - customs_item_expenses   — per quote_item additional costs
--                               (testing, translations, stickers)
--   - customs_quote_expenses  — per-quote costs (broker, DT filing, etc)
--
-- Also updates user_table_views.visible_columns arrays to rename
-- customs_psn_pts → customs_psm_pts (R10.6 forward-compat).
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §5.2 ALTER quote_items
--   - .kiro/specs/logistics-customs-redesign/requirements.md R7, R9

-- =============================================================================
-- Part 1: Rename customs_psn_pts → customs_psm_pts (typo fix)
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota' AND table_name = 'quote_items'
          AND column_name = 'customs_psn_pts'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'kvota' AND table_name = 'quote_items'
          AND column_name = 'customs_psm_pts'
    ) THEN
        ALTER TABLE kvota.quote_items RENAME COLUMN customs_psn_pts TO customs_psm_pts;
    END IF;
END $$;

-- Update any existing user_table_views configs that reference the old name
UPDATE kvota.user_table_views
   SET visible_columns = array_replace(visible_columns, 'customs_psn_pts', 'customs_psm_pts')
 WHERE 'customs_psn_pts' = ANY(visible_columns);

-- =============================================================================
-- Part 2: DROP legacy duplicate columns
-- =============================================================================

ALTER TABLE kvota.quote_items
    DROP COLUMN IF EXISTS customs_ds_sgr,
    DROP COLUMN IF EXISTS customs_marking;

-- =============================================================================
-- Part 3: customs_item_expenses — per-item customs costs
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.customs_item_expenses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_item_id UUID NOT NULL REFERENCES kvota.quote_items(id) ON DELETE CASCADE,
    label         TEXT NOT NULL CHECK (length(trim(label)) > 0),
    amount_rub    DECIMAL(15, 2) NOT NULL DEFAULT 0 CHECK (amount_rub >= 0),
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by    UUID REFERENCES auth.users(id)
);

COMMENT ON TABLE kvota.customs_item_expenses IS
    'Per-item additional customs costs (testing, translations, stickers). RUB only.';

CREATE INDEX IF NOT EXISTS idx_customs_item_expenses_quote_item
    ON kvota.customs_item_expenses(quote_item_id);

ALTER TABLE kvota.customs_item_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "customs_item_expenses_org_select" ON kvota.customs_item_expenses
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quote_items qi
            JOIN kvota.quotes q ON q.id = qi.quote_id
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            WHERE qi.id = customs_item_expenses.quote_item_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "customs_item_expenses_customs_admin_mutate" ON kvota.customs_item_expenses
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quote_items qi
            JOIN kvota.quotes q ON q.id = qi.quote_id
            JOIN kvota.user_roles ur ON ur.organization_id = q.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE qi.id = customs_item_expenses.quote_item_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('customs', 'head_of_customs', 'admin')
        )
    );

-- =============================================================================
-- Part 4: customs_quote_expenses — per-quote customs overhead
-- =============================================================================

CREATE TABLE IF NOT EXISTS kvota.customs_quote_expenses (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id   UUID NOT NULL REFERENCES kvota.quotes(id) ON DELETE CASCADE,
    label      TEXT NOT NULL CHECK (length(trim(label)) > 0),
    amount_rub DECIMAL(15, 2) NOT NULL DEFAULT 0 CHECK (amount_rub >= 0),
    notes      TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID REFERENCES auth.users(id)
);

COMMENT ON TABLE kvota.customs_quote_expenses IS
    'Per-quote customs overhead (broker fee, ДТ filing, etc). RUB only.';

CREATE INDEX IF NOT EXISTS idx_customs_quote_expenses_quote
    ON kvota.customs_quote_expenses(quote_id);

ALTER TABLE kvota.customs_quote_expenses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "customs_quote_expenses_org_select" ON kvota.customs_quote_expenses
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.organization_members om ON om.organization_id = q.organization_id
            WHERE q.id = customs_quote_expenses.quote_id
              AND om.user_id = auth.uid()
              AND om.status = 'active'
        )
    );

CREATE POLICY "customs_quote_expenses_customs_admin_mutate" ON kvota.customs_quote_expenses
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM kvota.quotes q
            JOIN kvota.user_roles ur ON ur.organization_id = q.organization_id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE q.id = customs_quote_expenses.quote_id
              AND ur.user_id = auth.uid()
              AND r.slug IN ('customs', 'head_of_customs', 'admin')
        )
    );

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (293, '293_customs_cleanup_and_expenses', now())
ON CONFLICT (id) DO NOTHING;
