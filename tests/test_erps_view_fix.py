"""
TDD Tests for ERPS Registry View Fix: spec_sum_usd showing $0.00

BUG: The erps_registry view uses qcs.calc_ak16_final_price_total from
quote_calculation_summaries, but that column is often NULL/missing.
The correct data source is q.total_amount_usd from the quotes table,
which is populated by the calculation engine save logic.

FIX:
1. Migration 161: Recreate erps_registry view replacing all 4 occurrences
   of qcs.calc_ak16_final_price_total with q.total_amount_usd
2. main.py ERPS_VIEWS: Add 'auto' group to finance view so finance users
   can see payment columns (days_until_advance, remaining_payment_usd, etc.)

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the fix is implemented.
"""

import pytest
import os
import re
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


def _extract_erps_views_source():
    """Extract ERPS_VIEWS dict definition from main.py."""
    source = _read_main_source()
    match = re.search(
        r'ERPS_VIEWS\s*=\s*\{[^}]+\}',
        source,
        re.DOTALL,
    )
    if not match:
        pytest.fail("Could not find ERPS_VIEWS definition in main.py")
    return match.group(0)


def _extract_erps_column_groups_source():
    """Extract ERPS_COLUMN_GROUPS dict definition from main.py."""
    source = _read_main_source()
    match = re.search(
        r'ERPS_COLUMN_GROUPS\s*=\s*\{',
        source,
    )
    if not match:
        pytest.fail("Could not find ERPS_COLUMN_GROUPS definition in main.py")
    # Find the matching closing brace by counting braces
    start = match.start()
    brace_count = 0
    pos = match.end() - 1  # position of the opening brace
    for i in range(pos, len(source)):
        if source[i] == '{':
            brace_count += 1
        elif source[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return source[start:i + 1]
    pytest.fail("Could not parse ERPS_COLUMN_GROUPS - unmatched braces")


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


# ============================================================================
# 5. ERPS_VIEWS Finance Preset Includes 'auto' Group
# ============================================================================


class TestERPSViewsFinanceIncludesAuto:
    """
    The finance view must include the 'auto' column group so finance
    users can see payment-related columns (days_until_advance,
    remaining_payment_usd, etc.).
    """

    def test_finance_view_includes_auto_group(self):
        """
        ERPS_VIEWS['finance'] must include 'auto' in its group list.
        Current: ['spec', 'finance', 'management']
        Expected: ['spec', 'auto', 'finance', 'management']
        """
        source = _extract_erps_views_source()

        # Parse the finance view definition
        finance_match = re.search(
            r"'finance'\s*:\s*\[([^\]]+)\]",
            source,
        )
        assert finance_match is not None, (
            "Could not find 'finance' key in ERPS_VIEWS"
        )

        finance_groups = finance_match.group(1)
        assert "'auto'" in finance_groups, (
            f"ERPS_VIEWS['finance'] must include 'auto' group. "
            f"Current groups: [{finance_groups}]. "
            f"Expected: ['spec', 'auto', 'finance', 'management']"
        )


# ============================================================================
# 6. ERPS_COLUMN_GROUPS Has 'auto' Group Defined
# ============================================================================


class TestERPSColumnGroupsAutoExists:
    """
    The 'auto' column group must exist in ERPS_COLUMN_GROUPS and contain
    the payment-related columns that finance users need.
    """

    def test_auto_group_defined(self):
        """ERPS_COLUMN_GROUPS must have an 'auto' key."""
        source = _extract_erps_column_groups_source()
        assert "'auto'" in source, (
            "ERPS_COLUMN_GROUPS must have an 'auto' group defined"
        )

    def test_auto_group_contains_days_until_advance(self):
        """
        The 'auto' group must include days_until_advance column.
        This is the payment countdown that finance users need.
        """
        source = _extract_erps_column_groups_source()
        # Extract the auto group section
        auto_match = re.search(
            r"'auto'\s*:\s*\{[^}]*'columns'\s*:\s*\[(.*?)\]",
            source,
            re.DOTALL,
        )
        assert auto_match is not None, (
            "Could not find 'auto' group columns in ERPS_COLUMN_GROUPS"
        )
        auto_columns = auto_match.group(1)
        assert "days_until_advance" in auto_columns, (
            "'auto' column group must contain 'days_until_advance' column"
        )

    def test_auto_group_contains_remaining_payment_usd(self):
        """
        The 'auto' group must include remaining_payment_usd column.
        This shows how much the client still owes.
        """
        source = _extract_erps_column_groups_source()
        auto_match = re.search(
            r"'auto'\s*:\s*\{[^}]*'columns'\s*:\s*\[(.*?)\]",
            source,
            re.DOTALL,
        )
        assert auto_match is not None, (
            "Could not find 'auto' group columns in ERPS_COLUMN_GROUPS"
        )
        auto_columns = auto_match.group(1)
        assert "remaining_payment_usd" in auto_columns, (
            "'auto' column group must contain 'remaining_payment_usd' column"
        )

    def test_auto_group_contains_planned_advance_usd(self):
        """
        The 'auto' group must include planned_advance_usd column.
        """
        source = _extract_erps_column_groups_source()
        auto_match = re.search(
            r"'auto'\s*:\s*\{[^}]*'columns'\s*:\s*\[(.*?)\]",
            source,
            re.DOTALL,
        )
        assert auto_match is not None, (
            "Could not find 'auto' group columns in ERPS_COLUMN_GROUPS"
        )
        auto_columns = auto_match.group(1)
        assert "planned_advance_usd" in auto_columns, (
            "'auto' column group must contain 'planned_advance_usd' column"
        )

    def test_auto_group_contains_total_paid_usd(self):
        """
        The 'auto' group must include total_paid_usd column.
        """
        source = _extract_erps_column_groups_source()
        auto_match = re.search(
            r"'auto'\s*:\s*\{[^}]*'columns'\s*:\s*\[(.*?)\]",
            source,
            re.DOTALL,
        )
        assert auto_match is not None, (
            "Could not find 'auto' group columns in ERPS_COLUMN_GROUPS"
        )
        auto_columns = auto_match.group(1)
        assert "total_paid_usd" in auto_columns, (
            "'auto' column group must contain 'total_paid_usd' column"
        )


# ============================================================================
# 7. Data Source Verification: total_amount_usd Saved in Calculation Logic
# ============================================================================


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


# ============================================================================
# 9. Consistency: Finance View Groups Are Ordered Correctly
# ============================================================================


class TestFinanceViewGroupOrdering:
    """
    The finance view groups should be in a logical order:
    spec first (base data), then auto (calculated), then finance, then management.
    """

    def test_finance_view_has_spec_first(self):
        """Finance view must start with 'spec' group."""
        source = _extract_erps_views_source()
        finance_match = re.search(
            r"'finance'\s*:\s*\[([^\]]+)\]",
            source,
        )
        assert finance_match is not None
        groups_str = finance_match.group(1)
        # Extract group names in order
        groups = re.findall(r"'(\w+)'", groups_str)
        assert len(groups) > 0, "Finance view must have at least one group"
        assert groups[0] == "spec", (
            f"Finance view must start with 'spec' group, got: {groups}"
        )

    def test_finance_view_has_at_least_4_groups(self):
        """
        After fix, finance view should have 4 groups:
        spec, auto, finance, management.
        """
        source = _extract_erps_views_source()
        finance_match = re.search(
            r"'finance'\s*:\s*\[([^\]]+)\]",
            source,
        )
        assert finance_match is not None
        groups_str = finance_match.group(1)
        groups = re.findall(r"'(\w+)'", groups_str)
        assert len(groups) >= 4, (
            f"Finance view must have at least 4 groups "
            f"(spec, auto, finance, management), got {len(groups)}: {groups}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
