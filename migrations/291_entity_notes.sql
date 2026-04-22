-- Migration 291: polymorphic entity_notes table.
-- Wave 1 Task 5.1 of logistics-customs-redesign spec (R11).
--
-- Single notes primitive for:
--   - quote-level comments (МОЗ → логисту, МОП → логисту)
--   - customer-level persistent notes (логистическая заметка о клиенте,
--     видна на всех будущих сделках с этим клиентом)
--   - invoice-level comments (логист → КП поставщика для закупок)
--
-- visible_to[] drives RBAC — a role must be listed (or '*') to read a note.
--
-- Design references:
--   - .kiro/specs/logistics-customs-redesign/design.md §3.7, §9.1
--   - .kiro/specs/logistics-customs-redesign/requirements.md R11

CREATE TABLE IF NOT EXISTS kvota.entity_notes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL
        CHECK (entity_type IN ('quote', 'customer', 'invoice', 'supplier')),
    entity_id   UUID NOT NULL,
    author_id   UUID NOT NULL REFERENCES auth.users(id),
    author_role VARCHAR(30) NOT NULL,
    visible_to  TEXT[] NOT NULL DEFAULT ARRAY['*'],
    body        TEXT NOT NULL CHECK (length(trim(body)) > 0),
    pinned      BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE kvota.entity_notes IS
    'Polymorphic notes with per-role visibility. entity_type+entity_id is a soft FK — consumer code validates.';
COMMENT ON COLUMN kvota.entity_notes.visible_to IS
    'Array of role slugs that can read this note. ''*'' = everyone in org.';
COMMENT ON COLUMN kvota.entity_notes.author_role IS
    'Role slug of author at write time (frozen — surviving role changes later).';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entity_notes_entity
    ON kvota.entity_notes(entity_type, entity_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_entity_notes_visible_to
    ON kvota.entity_notes USING GIN (visible_to);

CREATE INDEX IF NOT EXISTS idx_entity_notes_pinned
    ON kvota.entity_notes(entity_type, entity_id)
    WHERE pinned = true;

-- updated_at trigger
DROP TRIGGER IF EXISTS trg_entity_notes_updated_at ON kvota.entity_notes;
CREATE TRIGGER trg_entity_notes_updated_at
    BEFORE UPDATE ON kvota.entity_notes
    FOR EACH ROW EXECUTE FUNCTION kvota.set_updated_at();

-- =============================================================================
-- RLS — visible_to drives read access; only author / admin can edit/delete
-- =============================================================================

ALTER TABLE kvota.entity_notes ENABLE ROW LEVEL SECURITY;

-- Helper: check if current user has any of the listed role slugs in their org
CREATE OR REPLACE FUNCTION kvota.entity_notes_user_has_any_role(role_slugs TEXT[])
RETURNS BOOLEAN
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
AS $$
BEGIN
    IF '*' = ANY(role_slugs) THEN
        RETURN true;
    END IF;
    RETURN EXISTS (
        SELECT 1 FROM kvota.user_roles ur
        JOIN kvota.roles r ON r.id = ur.role_id
        WHERE ur.user_id = auth.uid()
          AND r.slug = ANY(role_slugs)
    );
END;
$$;

CREATE POLICY "entity_notes_select_by_visibility" ON kvota.entity_notes
    FOR SELECT TO authenticated
    USING (
        kvota.entity_notes_user_has_any_role(visible_to)
        OR author_id = auth.uid()
    );

CREATE POLICY "entity_notes_insert_self" ON kvota.entity_notes
    FOR INSERT TO authenticated
    WITH CHECK (author_id = auth.uid());

CREATE POLICY "entity_notes_update_author_or_admin" ON kvota.entity_notes
    FOR UPDATE TO authenticated
    USING (
        author_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

CREATE POLICY "entity_notes_delete_author_or_admin" ON kvota.entity_notes
    FOR DELETE TO authenticated
    USING (
        author_id = auth.uid()
        OR EXISTS (
            SELECT 1 FROM kvota.user_roles ur
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE ur.user_id = auth.uid() AND r.slug = 'admin'
        )
    );

INSERT INTO kvota.migrations (id, filename, applied_at)
VALUES (291, '291_entity_notes', now())
ON CONFLICT (id) DO NOTHING;
