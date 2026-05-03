-- Migration 303: extend uq_tnved_rates_v3 with `description` so льготные
-- variants WITHIN a single category coexist.
--
-- Discovered after migration 302 fixed the NULL country bug: a fresh Alta
-- probe of HS=7326909807 × Китай crashed with
--   "ON CONFLICT DO UPDATE command cannot affect row a second time"
-- because Alta returned multiple <VAT> within nds_inv that share
-- (category_code, value) but differ in <Condition> — e.g.
--   - 29. Специальные средства для самообслуживания
--   - 31. Приспособления для захвата и передвижения предметов
-- Both are valid льготные классификации; the customs-specialist must see
-- both options to pick the applicable one. So they must coexist as
-- separate rows.
--
-- Without `description` in the unique key, the parser emits 2 Rate rows
-- mapping to one constraint key — Postgres refuses to update the same
-- target twice in one INSERT statement.
--
-- Idempotency: TRUNCATE + DROP IF EXISTS.
-- The previous v2 constraint (without description) is replaced; v3 also
-- adds `description` to the natural key. NULL → '' coercion mirrors the
-- migration-302 sentinel pattern.

-- =============================================================================
-- Part 1: clear cache (will repopulate on next resolve)
-- =============================================================================

TRUNCATE TABLE kvota.tnved_rates CASCADE;

-- =============================================================================
-- Part 2: description must be NOT NULL with sentinel '' so the index
--         actually enforces uniqueness when a rate has no <Prim>/<Condition>
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    ALTER COLUMN description SET DEFAULT '';

-- After TRUNCATE there are no rows to violate NOT NULL.
ALTER TABLE kvota.tnved_rates
    ALTER COLUMN description SET NOT NULL;

-- =============================================================================
-- Part 3: replace v2 constraint with v3 (adds description)
-- =============================================================================

ALTER TABLE kvota.tnved_rates
    DROP CONSTRAINT IF EXISTS uq_tnved_rates_v2;

ALTER TABLE kvota.tnved_rates
    DROP CONSTRAINT IF EXISTS uq_tnved_rates_v3;

ALTER TABLE kvota.tnved_rates
    ADD CONSTRAINT uq_tnved_rates_v3 UNIQUE (
        tnved_code,
        payment_type,
        country_or_areal,
        valid_from,
        certificate_required,
        sp_certificate_required,
        category_code,
        description
    );

COMMENT ON CONSTRAINT uq_tnved_rates_v3 ON kvota.tnved_rates IS
    'Replaces uq_tnved_rates_v2 (migration 301). Adds description so льготные '
    'variants within a single category (e.g., nds_inv "- 29..." vs '
    '"- 31...") coexist as separate rows. description is NOT NULL with '
    'empty-string sentinel — Postgres NULL semantics would break uniqueness '
    'just like they did for country_or_areal in migration 302.';

COMMENT ON COLUMN kvota.tnved_rates.description IS
    'Free-text variant identifier — for IMP: <Prim> ("- зажимное устройство"), '
    'for NDS/AKC: <Condition> ("- Прочие", "- Медизделия"). NOT NULL with '
    'empty-string sentinel since migration 303 (part of uq_tnved_rates_v3 key).';
