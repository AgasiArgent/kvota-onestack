-- Migration 308: Restrict UPDATEs to customer-facing fields on kvota.quotes
-- Created: 2026-05-07
--
-- Bug МОЗ-58 (Track A): procurement / logistics / customs / finance roles
-- could change `contact_person_id` and `delivery_address` on a quote via the
-- context-panel dropdowns (frontend wrote directly through PostgREST). Those
-- fields are sales-side decisions — only sales / head_of_sales / admin should
-- mutate them.
--
-- Architecture choice: BEFORE UPDATE trigger, NOT a per-row WITH CHECK policy.
-- Rationale:
--   1. Postgres RLS policies see NEW row in WITH CHECK and OLD row in USING,
--      but they cannot reference BOTH simultaneously to detect a per-column
--      change ("did this UPDATE change contact_person_id?"). The standard
--      `OLD.x IS DISTINCT FROM NEW.x` idiom is trigger-only.
--   2. A blanket UPDATE policy gated on role would lock out every other field
--      edit (workflow_status changes, totals, etc.), breaking the existing
--      "Users can update their own quotes" contract.
--   3. Triggers fire AFTER RLS USING/CHECK and BEFORE the row is written,
--      letting us inspect old vs. new values per field and raise a clean
--      exception with a Russian-readable message that the toast surfaces.
--
-- service_role bypasses RLS but NOT triggers (Postgres default). The trigger
-- below runs for every UPDATE regardless of the calling role, which means
-- the Python backend (service_role) is also gated. Today there is no
-- `/api/quotes/{id}` PATCH endpoint that mutates these fields — when one is
-- added per `.claude/rules/api-first.md`, it should validate role at the API
-- layer and then either set `auth.uid()` to the acting user via JWT
-- forwarding (preferred) or `SET LOCAL session_replication_role = replica`
-- around the write to bypass triggers. Until then, the trigger denying
-- NULL-uid writes is the desired behaviour.

BEGIN;

-- Helper: returns true iff the caller has at least one of the allowlisted
-- slugs in any organization. Mirrors the application-layer
-- `canEditQuoteCustomerFields([...])` helper in `frontend/src/shared/lib/roles.ts`
-- and the slug list documented in `.kiro/steering/access-control.md`.
CREATE OR REPLACE FUNCTION kvota.user_can_edit_quote_customer_fields(p_user_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = kvota, public
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM kvota.user_roles ur
          JOIN kvota.roles r ON r.id = ur.role_id
         WHERE ur.user_id = p_user_id
           AND r.slug IN ('admin', 'sales', 'head_of_sales')
    );
$$;

COMMENT ON FUNCTION kvota.user_can_edit_quote_customer_fields(uuid) IS
  'МОЗ-58: returns true iff the user has admin/sales/head_of_sales role. '
  'Used by the BEFORE UPDATE trigger on kvota.quotes to gate customer-facing '
  'field writes (contact_person_id, delivery_address). SECURITY DEFINER so '
  'authenticated callers can read user_roles without their own SELECT policy.';

-- Trigger function: rejects an UPDATE that changes contact_person_id or
-- delivery_address when the caller isn't sales-tier. service_role passing a
-- NULL auth.uid() also gets denied — backend code that needs to bypass this
-- must SET LOCAL session_replication_role = replica around the write.
CREATE OR REPLACE FUNCTION kvota.guard_quote_customer_fields()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = kvota, public
AS $$
DECLARE
    v_uid uuid := auth.uid();
    v_changed boolean;
BEGIN
    v_changed :=
        OLD.contact_person_id IS DISTINCT FROM NEW.contact_person_id
        OR OLD.delivery_address IS DISTINCT FROM NEW.delivery_address;

    IF NOT v_changed THEN
        RETURN NEW;
    END IF;

    IF v_uid IS NULL THEN
        -- service_role / SECURITY DEFINER context with no auth.uid() — refuse.
        -- Backend writes that legitimately need this field must go through a
        -- role-validated /api/* endpoint (api-first.md), not direct PostgREST.
        RAISE EXCEPTION
            'Изменение контакта или адреса доставки требует авторизации'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NOT kvota.user_can_edit_quote_customer_fields(v_uid) THEN
        RAISE EXCEPTION
            'Только роли «продажи» могут менять контакт и адрес доставки квоты'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION kvota.guard_quote_customer_fields() IS
  'МОЗ-58: BEFORE UPDATE trigger function on kvota.quotes. Blocks writes to '
  'contact_person_id / delivery_address from non-sales-tier callers.';

DROP TRIGGER IF EXISTS quotes_guard_customer_fields ON kvota.quotes;
CREATE TRIGGER quotes_guard_customer_fields
    BEFORE UPDATE OF contact_person_id, delivery_address
    ON kvota.quotes
    FOR EACH ROW
    EXECUTE FUNCTION kvota.guard_quote_customer_fields();

COMMENT ON TRIGGER quotes_guard_customer_fields ON kvota.quotes IS
  'МОЗ-58: per-column gate on contact_person_id + delivery_address writes. '
  'Pure RLS cannot express "field-level change detection" — see migration '
  'header for the why-trigger-not-policy rationale.';

COMMIT;
