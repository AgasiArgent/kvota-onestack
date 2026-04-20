"""
TDD Tests for Spec Creation Bug Fix: contract_id, delivery_days, auto-number lost on save.

Root cause: migration 036 created contract_id in wrong schema (public instead of kvota).
Fix: migration 160 ensures columns exist in kvota.specifications (idempotent).

POST handler: main.py ~line 21797 (POST /spec-control/create/{quote_id})
  - spec_data dict building: ~lines 21894-21921
  - Auto-numbering logic: ~lines 21856-21877
  - delivery_days fallback: ~line 21880-21891
  - INSERT: ~line 21924

These tests are written BEFORE implementation (TDD).
Tests that check migration 160 should FAIL until the migration is created.
Tests that verify spec_data dict building should PASS (code already exists).
"""

import pytest  # noqa: F401 — used by pytest.main and migration test skips
import os
import glob as glob_module

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")


# TestSpecDataDictBuilding + TestAutoNumbering + TestDeliveryDaysFallback +
# TestSourceCodeVerification removed in Phase 6C-2B Mega-B — all four classes
# depended on the `post_handler_source` fixture reading the POST
# /spec-control/create/{quote_id} handler from main.py, which was archived
# to legacy-fasthtml/control_flow.py. The migration-targeted tests below
# (TestMigration160 + TestMigration036Bug) are retained — they inspect
# migration files and remain valid regardless of archive.


# ==============================================================================
# 5. Migration 160 tests: ensures columns exist in kvota schema
# ==============================================================================

class TestMigration160:
    """
    Migration 160 fixes the schema issue from migration 036.
    036 checked information_schema.columns without table_schema='kvota',
    so contract_id may have been created in public.specifications instead of
    kvota.specifications.

    Migration 160 must:
    - Exist as a migration file
    - Target kvota schema specifically
    - Use IF NOT EXISTS or equivalent for idempotency
    - Ensure contract_id column exists in kvota.specifications
    """

    def test_migration_160_file_exists(self):
        """
        Migration 160 file must exist in the migrations directory.
        This is the fix migration that ensures columns are in kvota schema.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file must exist in migrations/ directory. "
            "This migration fixes the schema issue from migration 036 "
            "where contract_id was created in public instead of kvota."
        )

    def test_migration_160_targets_kvota_schema(self):
        """
        Migration 160 must explicitly reference kvota schema (not public).
        The original bug was that 036 didn't specify kvota schema.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check schema targeting."
        )

        migration_content = open(migration_files[0]).read()
        has_kvota_schema = (
            "kvota.specifications" in migration_content
            or "table_schema = 'kvota'" in migration_content
            or "table_schema='kvota'" in migration_content
        )
        assert has_kvota_schema, (
            "Migration 160 must explicitly target kvota schema. "
            "Expected: 'kvota.specifications' or table_schema = 'kvota'. "
            "The original bug in 036 was missing this schema qualifier."
        )

    def test_migration_160_is_idempotent(self):
        """
        Migration 160 must use IF NOT EXISTS or equivalent for idempotency.
        Running it multiple times should not fail.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check idempotency."
        )

        migration_content = open(migration_files[0]).read().lower()
        has_idempotent = (
            "if not exists" in migration_content
            or "do $$" in migration_content  # PL/pgSQL conditional block
        )
        assert has_idempotent, (
            "Migration 160 must be idempotent (safe to run multiple times). "
            "Expected: IF NOT EXISTS or DO $$ conditional block."
        )

    def test_migration_160_ensures_contract_id_column(self):
        """
        Migration 160 must ensure contract_id column exists in kvota.specifications.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check contract_id column."
        )

        migration_content = open(migration_files[0]).read()
        has_contract_id = "contract_id" in migration_content
        assert has_contract_id, (
            "Migration 160 must ensure contract_id column exists in kvota.specifications. "
            "This is the primary column that was lost due to the schema bug."
        )

    def test_migration_160_does_not_use_public_schema(self):
        """
        Migration 160 must NOT reference public schema for specifications table.
        The whole point of this fix is to avoid the public schema mistake.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "160*"))
        assert len(migration_files) > 0, (
            "Migration 160 file not found -- cannot check for public schema references."
        )

        migration_content = open(migration_files[0]).read()
        has_public_specs = "public.specifications" in migration_content
        assert not has_public_specs, (
            "Migration 160 must NOT reference public.specifications. "
            "The fix specifically targets kvota schema."
        )


# ==============================================================================
# 6. Migration 036 bug verification: confirms the root cause
# ==============================================================================

class TestMigration036Bug:
    """
    Verify that migration 036 has the bug (no kvota schema qualifier).
    This confirms the root cause and justifies migration 160.
    """

    def test_migration_036_exists(self):
        """Migration 036 should exist."""
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, (
            "Migration 036 file should exist in migrations/ directory."
        )

    def test_migration_036_missing_kvota_schema_in_information_schema_check(self):
        """
        Migration 036 checks information_schema.columns for column existence,
        but does NOT filter by table_schema = 'kvota'. This means it checks
        the public schema by default, creating columns there instead of in kvota.
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, "Migration 036 not found"

        migration_content = open(migration_files[0]).read()

        # Confirm it uses information_schema.columns
        uses_info_schema = "information_schema.columns" in migration_content
        assert uses_info_schema, (
            "Migration 036 should use information_schema.columns check"
        )

        # Confirm it does NOT have table_schema = 'kvota'
        has_kvota_filter = (
            "table_schema = 'kvota'" in migration_content
            or "table_schema='kvota'" in migration_content
        )
        assert not has_kvota_filter, (
            "Migration 036 is missing table_schema = 'kvota' filter in "
            "information_schema.columns check. This is the root cause: "
            "columns were created in public schema instead of kvota."
        )

    def test_migration_036_uses_plain_table_name(self):
        """
        Migration 036 uses 'ALTER TABLE specifications' without kvota prefix.
        This means the ALTER TABLE targets the search_path default (likely public).
        """
        migration_files = glob_module.glob(os.path.join(MIGRATIONS_DIR, "036*"))
        assert len(migration_files) > 0, "Migration 036 not found"

        migration_content = open(migration_files[0]).read()

        # Check for ALTER TABLE without kvota prefix
        has_plain_alter = "ALTER TABLE specifications" in migration_content
        has_kvota_alter = "ALTER TABLE kvota.specifications" in migration_content

        assert has_plain_alter and not has_kvota_alter, (
            "Migration 036 uses 'ALTER TABLE specifications' without kvota prefix. "
            "This confirms the table targeted is in the default schema (public), "
            "not kvota. Migration 160 must fix this."
        )


# TestSpecDataColumnAlignment removed in Phase 6C-2B Mega-B — the class
# reads the spec_data dict from the archived POST /spec-control/create/{quote_id}
# handler, which moved to legacy-fasthtml/control_flow.py.


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
