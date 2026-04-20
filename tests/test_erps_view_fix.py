"""
Tests for ERPS Registry View Fix: migrations + calculation save logic.

BUG (fixed): The erps_registry view used qcs.calc_ak16_final_price_total,
which is often NULL/missing. Migration 161 recreates the view using
q.total_amount_usd from the quotes table instead.

Note: Python-side ERPS_VIEWS + ERPS_COLUMN_GROUPS constants tests
(TestERPSViewsFinanceIncludesAuto, TestERPSColumnGroupsAutoExists,
TestFinanceViewGroupOrdering) plus helpers (_extract_erps_views_source,
_extract_erps_column_groups_source) were removed during Phase 6C-2B-10c1
archive of the /finance cluster (2026-04-20). Those constants now live in
legacy-fasthtml/finance_lifecycle.py and are not imported. Remaining tests
target SQL migrations (161, 129, 139) and the alive calculation save logic
in main.py — both still valid.
"""

import pytest
import os
import glob as glob_module

# ============================================================================
# Paths
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _find_migration_161():
    """Find migration 161 file. Returns path or None."""
    pattern = os.path.join(MIGRATIONS_DIR, "161*")
    matches = glob_module.glob(pattern)
    return matches[0] if matches else None


def _read_migration_161():
    """Read migration 161 content. Fails if file does not exist."""
    path = _find_migration_161()
    if path is None:
        pytest.fail(
            "Migration 161 file does not exist yet. "
            "Expected a file matching migrations/161*.sql"
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()




# ============================================================================
# 1. Migration 161 File Existence
# ============================================================================


class TestMigration161Exists:
    """Migration 161 must exist to fix the erps_registry view."""

    def test_migration_161_file_exists(self):
        """Migration file 161*.sql must exist in migrations/ directory."""
        path = _find_migration_161()
        assert path is not None, (
            "Migration 161 file does not exist. "
            "Expected migrations/161*.sql to fix erps_registry view."
        )

    def test_migration_161_is_sql_file(self):
        """Migration 161 must be a .sql file."""
        path = _find_migration_161()
        assert path is not None, "Migration 161 does not exist"
        assert path.endswith(".sql"), (
            f"Migration 161 must be a .sql file, got: {path}"
        )


# ============================================================================
# 2. Migration 161 Uses q.total_amount_usd (Correct Data Source)
# ============================================================================


class TestMigration161UsesTotalAmountUsd:
    """
    Migration 161 must reference q.total_amount_usd from the quotes table
    instead of qcs.calc_ak16_final_price_total from quote_calculation_summaries.
    """

    def test_migration_references_q_total_amount_usd(self):
        """Migration 161 must use q.total_amount_usd as the data source."""
        content = _read_migration_161()
        assert "q.total_amount_usd" in content, (
            "Migration 161 must reference q.total_amount_usd "
            "(the correct, populated column from the quotes table)"
        )

    def test_migration_does_not_reference_calc_ak16(self):
        """
        Migration 161 must NOT use calc_ak16_final_price_total.
        This column from quote_calculation_summaries is often NULL,
        causing spec_sum_usd to show $0.00.
        """
        content = _read_migration_161()
        assert "calc_ak16_final_price_total" not in content, (
            "Migration 161 must NOT reference calc_ak16_final_price_total. "
            "This is the broken column that causes $0.00 values. "
            "Replace all 4 occurrences with q.total_amount_usd."
        )

    def test_migration_uses_total_amount_usd_for_spec_sum(self):
        """
        The spec_sum_usd field must be derived from q.total_amount_usd,
        not from qcs.calc_ak16_final_price_total.
        """
        content = _read_migration_161()
        # Should have a line like: COALESCE(q.total_amount_usd, 0) AS spec_sum_usd
        assert "spec_sum_usd" in content, (
            "Migration 161 must define spec_sum_usd column"
        )
        # Verify the total_amount_usd is used (not calc_ak16)
        assert "total_amount_usd" in content, (
            "Migration 161 must use total_amount_usd for spec_sum_usd calculation"
        )


# ============================================================================
# 3. Migration 161 Creates/Replaces erps_registry View
# ============================================================================


class TestMigration161CreatesView:
    """Migration 161 must create or replace the erps_registry view."""

    def test_migration_creates_erps_registry_view(self):
        """
        Migration must DROP and CREATE (or CREATE OR REPLACE)
        the erps_registry view.
        """
        content = _read_migration_161()
        has_create = (
            "CREATE VIEW" in content.upper()
            or "CREATE OR REPLACE VIEW" in content.upper()
        )
        assert has_create, (
            "Migration 161 must CREATE or CREATE OR REPLACE the erps_registry view"
        )

    def test_migration_references_erps_registry(self):
        """Migration must target the erps_registry view specifically."""
        content = _read_migration_161()
        assert "erps_registry" in content.lower(), (
            "Migration 161 must reference 'erps_registry' view"
        )

    def test_migration_targets_kvota_schema(self):
        """Migration must use kvota schema (not public)."""
        content = _read_migration_161()
        assert "kvota.erps_registry" in content or "kvota." in content, (
            "Migration 161 must target kvota schema "
            "(e.g., kvota.erps_registry, not public.erps_registry)"
        )


# ============================================================================
# 4. Migration 161 Handles All 4 Fields Correctly
# ============================================================================


class TestMigration161AllFieldsCovered:
    """
    The erps_registry view has 4 fields derived from the spec total:
    spec_sum_usd, planned_advance_usd, remaining_payment_usd,
    remaining_payment_percent. All must use q.total_amount_usd.
    """

    def test_spec_sum_usd_field_defined(self):
        """spec_sum_usd (total spec amount in USD) must be in the view."""
        content = _read_migration_161()
        assert "spec_sum_usd" in content, (
            "Migration 161 must define spec_sum_usd field"
        )

    def test_planned_advance_usd_field_defined(self):
        """planned_advance_usd (advance amount) must be in the view."""
        content = _read_migration_161()
        assert "planned_advance_usd" in content, (
            "Migration 161 must define planned_advance_usd field"
        )

    def test_remaining_payment_usd_field_defined(self):
        """remaining_payment_usd (outstanding payment) must be in the view."""
        content = _read_migration_161()
        assert "remaining_payment_usd" in content, (
            "Migration 161 must define remaining_payment_usd field"
        )

    def test_remaining_payment_percent_field_defined(self):
        """remaining_payment_percent (% outstanding) must be in the view."""
        content = _read_migration_161()
        assert "remaining_payment_percent" in content, (
            "Migration 161 must define remaining_payment_percent field"
        )

    def test_no_qcs_join_for_price_total(self):
        """
        The view should no longer need qcs (quote_calculation_summaries)
        for the price total. It may still join qcs for other fields,
        but calc_ak16_final_price_total must not appear.
        """
        content = _read_migration_161()
        assert "calc_ak16_final_price_total" not in content, (
            "Migration 161 must not reference calc_ak16_final_price_total at all. "
            "All 4 usages must be replaced with q.total_amount_usd."
        )


class TestTotalAmountUsdSavedInCalculation:
    """
    The calculation engine save logic in main.py must save total_amount_usd
    to the quotes table. This is the data source that the fixed view will use.
    """

    def test_total_amount_usd_saved_to_quotes_table(self):
        """
        main.py must include code that saves total_amount_usd to the quotes table
        via a Supabase update call.
        """
        source = _read_main_source()
        # The save logic should update quotes with total_amount_usd
        has_save = (
            '"total_amount_usd"' in source
            and ".update(" in source
        )
        assert has_save, (
            "main.py must save total_amount_usd to the quotes table "
            "in the calculation save logic"
        )

    def test_total_amount_usd_column_in_migration_139(self):
        """
        Migration 139 must define total_amount_usd column on kvota.quotes table.
        This is the column that the erps_registry view will reference.
        """
        migration_path = os.path.join(
            MIGRATIONS_DIR, "139_add_usd_columns_for_analytics.sql"
        )
        assert os.path.exists(migration_path), (
            "Migration 139 (add_usd_columns_for_analytics.sql) must exist"
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "total_amount_usd" in content, (
            "Migration 139 must define total_amount_usd column on quotes table"
        )
        assert "kvota.quotes" in content, (
            "Migration 139 must target kvota.quotes table"
        )


# ============================================================================
# 8. Regression: Old View's Broken Data Source
# ============================================================================


class TestOldViewBrokenDataSource:
    """
    Verify that migration 129 (current view) uses the broken data source.
    This confirms the bug exists and that migration 161 is needed.
    """

    def test_migration_129_uses_calc_ak16(self):
        """
        Migration 129 (current view) uses calc_ak16_final_price_total,
        which is the column that causes $0.00 values.
        """
        migration_path = os.path.join(
            MIGRATIONS_DIR, "129_update_erps_registry_view.sql"
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "calc_ak16_final_price_total" in content, (
            "Migration 129 should use calc_ak16_final_price_total "
            "(this is the broken behavior we are fixing)"
        )

    def test_migration_129_has_4_occurrences_of_calc_ak16(self):
        """
        Migration 129 uses calc_ak16_final_price_total in 4 field calculations:
        spec_sum_usd, planned_advance_usd, remaining_payment_usd,
        remaining_payment_percent.
        """
        migration_path = os.path.join(
            MIGRATIONS_DIR, "129_update_erps_registry_view.sql"
        )
        with open(migration_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Count occurrences of the broken column reference
        count = content.count("calc_ak16_final_price_total")
        # There are 5 literal occurrences across 4 field calculations
        # (remaining_payment_percent uses it twice: in WHEN and in division)
        assert count >= 4, (
            f"Migration 129 should reference calc_ak16_final_price_total "
            f"at least 4 times (found {count}). These are the 4 fields to fix."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
