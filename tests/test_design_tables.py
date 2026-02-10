"""
Tests for table-enhanced design consistency across dashboard, tasks, sales, and calendar pages.

Design issue group:
  M5  - Dashboard overview: "Последние КП" table lacks table-enhanced styling
  M9  - Payments calendar: table uses unified-table instead of table-enhanced
  M11 - Dashboard sales tab: "Активные спецификации" and "Активные КП" tables lack table-enhanced
  M12 - Tasks page: spec_controller section lacks a table-enhanced table

All tables in the application should use the `table-enhanced` class and be wrapped
in a `table-enhanced-container` div for consistent styling (gradient header, hover
effects, proper spacing).

These tests are written BEFORE the fix (TDD).
All tests MUST FAIL until the design issues are resolved.
"""

import pytest
import re
import os


# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code (no import needed, avoids dependency issues)."""
    with open(MAIN_PY) as f:
        return f.read()


def _extract_function_source(func_name: str) -> str:
    """Extract a top-level function's source from main.py by name.

    Uses a regex that matches from `def func_name(` up to the next
    top-level `def ` (or end of file).
    """
    content = _read_main_source()
    pattern = rf'^(def {re.escape(func_name)}\(.*?)(?=\ndef |\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if not match:
        pytest.fail(f"Could not find function '{func_name}' in main.py")
    return match.group(0)


# ============================================================================
# M5: Dashboard overview — "Последние КП" table
# ============================================================================

class TestM5DashboardOverviewTables:
    """M5: The 'Последние КП' table in _dashboard_overview_content must use
    the table-enhanced class and table-enhanced-container wrapper."""

    def test_recent_quotes_table_has_table_enhanced_class(self):
        """The 'Последние КП' table must include cls='table-enhanced'."""
        src = _extract_function_source("_dashboard_overview_content")

        # Find the "Последние КП" section — it starts after the H2 header
        last_kp_idx = src.find("Последние КП")
        assert last_kp_idx != -1, "Could not find 'Последние КП' section in _dashboard_overview_content"

        # Extract the section from that header to the end of the function
        section = src[last_kp_idx:]

        # The Table() call in that section must have cls="table-enhanced"
        assert 'cls="table-enhanced"' in section, (
            "The 'Последние КП' table in _dashboard_overview_content "
            "is missing cls='table-enhanced'. Currently renders a plain Table()."
        )

    def test_recent_quotes_table_has_enhanced_container_wrapper(self):
        """The 'Последние КП' table must be wrapped in a table-enhanced-container div."""
        src = _extract_function_source("_dashboard_overview_content")

        last_kp_idx = src.find("Последние КП")
        assert last_kp_idx != -1, "Could not find 'Последние КП' section"

        section = src[last_kp_idx:]

        assert 'cls="table-enhanced-container"' in section, (
            "The 'Последние КП' table in _dashboard_overview_content "
            "is not wrapped in a table-enhanced-container div."
        )


# ============================================================================
# M9: Payments calendar table
# ============================================================================

class TestM9PaymentsCalendarTable:
    """M9: The payments calendar table in finance_calendar_tab must use
    table-enhanced instead of unified-table."""

    def test_calendar_table_uses_table_enhanced_class(self):
        """The calendar table must use cls='table-enhanced', not 'unified-table'."""
        src = _extract_function_source("finance_calendar_tab")

        assert 'cls="table-enhanced"' in src, (
            "The payments calendar table in finance_calendar_tab uses "
            "cls='unified-table' instead of cls='table-enhanced'."
        )

    def test_calendar_table_does_not_use_unified_table_class(self):
        """The calendar table must NOT use the old unified-table class."""
        src = _extract_function_source("finance_calendar_tab")

        assert 'cls="unified-table"' not in src, (
            "The payments calendar table still uses the deprecated "
            "'unified-table' class. Should use 'table-enhanced' instead."
        )

    def test_calendar_table_has_enhanced_container_wrapper(self):
        """The calendar table must be wrapped in a table-enhanced-container div."""
        src = _extract_function_source("finance_calendar_tab")

        assert 'cls="table-enhanced-container"' in src, (
            "The payments calendar table is not wrapped in a "
            "table-enhanced-container div."
        )


# ============================================================================
# M11: Dashboard sales tab tables
# ============================================================================

class TestM11DashboardSalesTabTables:
    """M11: Both tables in _dashboard_sales_content (Активные спецификации
    and Активные КП) must use the table-enhanced class."""

    def test_active_specs_table_has_table_enhanced_class(self):
        """The 'Активные спецификации' table must include cls='table-enhanced'."""
        src = _extract_function_source("_dashboard_sales_content")

        # Find the section for active specs
        specs_idx = src.find("Активные спецификации")
        assert specs_idx != -1, "Could not find 'Активные спецификации' in _dashboard_sales_content"

        # Extract from that header up to the next major section
        quotes_idx = src.find("Активные КП", specs_idx)
        if quotes_idx != -1:
            specs_section = src[specs_idx:quotes_idx]
        else:
            specs_section = src[specs_idx:]

        assert 'cls="table-enhanced"' in specs_section, (
            "The 'Активные спецификации' table in _dashboard_sales_content "
            "is missing cls='table-enhanced'. Currently renders a plain Table()."
        )

    def test_active_quotes_table_has_table_enhanced_class(self):
        """The 'Активные КП' table must include cls='table-enhanced'."""
        src = _extract_function_source("_dashboard_sales_content")

        quotes_idx = src.find("Активные КП")
        assert quotes_idx != -1, "Could not find 'Активные КП' in _dashboard_sales_content"

        quotes_section = src[quotes_idx:]

        assert 'cls="table-enhanced"' in quotes_section, (
            "The 'Активные КП' table in _dashboard_sales_content "
            "is missing cls='table-enhanced'. Currently renders a plain Table()."
        )

    def test_active_specs_table_has_enhanced_container_wrapper(self):
        """The 'Активные спецификации' table must be wrapped in table-enhanced-container."""
        src = _extract_function_source("_dashboard_sales_content")

        specs_idx = src.find("Активные спецификации")
        assert specs_idx != -1, "Could not find 'Активные спецификации'"

        quotes_idx = src.find("Активные КП", specs_idx)
        if quotes_idx != -1:
            specs_section = src[specs_idx:quotes_idx]
        else:
            specs_section = src[specs_idx:]

        assert 'cls="table-enhanced-container"' in specs_section, (
            "The 'Активные спецификации' table is not wrapped in a "
            "table-enhanced-container div."
        )

    def test_active_quotes_table_has_enhanced_container_wrapper(self):
        """The 'Активные КП' table must be wrapped in table-enhanced-container."""
        src = _extract_function_source("_dashboard_sales_content")

        quotes_idx = src.find("Активные КП")
        assert quotes_idx != -1, "Could not find 'Активные КП'"

        quotes_section = src[quotes_idx:]

        assert 'cls="table-enhanced-container"' in quotes_section, (
            "The 'Активные КП' table is not wrapped in a "
            "table-enhanced-container div."
        )


# ============================================================================
# M12: Tasks page — spec_controller section
# ============================================================================

class TestM12TasksPageTables:
    """M12: The spec_controller section inside _get_role_tasks_sections should
    render a table-enhanced table (currently uses only stat cards with no table)."""

    def test_spec_controller_section_has_table_enhanced(self):
        """The spec_controller section must render a table with cls='table-enhanced'.

        Currently the spec_controller section (lines ~4795-4835) only renders
        stat cards (grid of Divs) without a table-enhanced table for listing
        specifications that need attention.
        """
        src = _extract_function_source("_get_role_tasks_sections")

        # Find the spec_controller section
        spec_ctrl_idx = src.find("SPEC_CONTROLLER")
        assert spec_ctrl_idx != -1, "Could not find SPEC_CONTROLLER section"

        # Find the next section boundary (FINANCE section)
        finance_idx = src.find("FINANCE", spec_ctrl_idx + 20)
        if finance_idx != -1:
            spec_ctrl_section = src[spec_ctrl_idx:finance_idx]
        else:
            spec_ctrl_section = src[spec_ctrl_idx:]

        assert 'cls="table-enhanced"' in spec_ctrl_section, (
            "The SPEC_CONTROLLER section in _get_role_tasks_sections does not "
            "include a table-enhanced table. It only shows stat cards without "
            "a detailed list of specifications needing attention."
        )

    def test_spec_controller_section_has_table_rows(self):
        """The spec_controller section should list individual specs in a table,
        not just aggregate counts in stat cards."""
        src = _extract_function_source("_get_role_tasks_sections")

        spec_ctrl_idx = src.find("SPEC_CONTROLLER")
        assert spec_ctrl_idx != -1, "Could not find SPEC_CONTROLLER section"

        finance_idx = src.find("FINANCE", spec_ctrl_idx + 20)
        if finance_idx != -1:
            spec_ctrl_section = src[spec_ctrl_idx:finance_idx]
        else:
            spec_ctrl_section = src[spec_ctrl_idx:]

        # Should have Thead + Tbody for listing specs
        assert "Thead" in spec_ctrl_section and "Tbody" in spec_ctrl_section, (
            "The SPEC_CONTROLLER section does not render a proper table with "
            "Thead/Tbody. It should list individual specs needing attention, "
            "not just aggregate stat cards."
        )

    def test_spec_controller_section_has_enhanced_container(self):
        """The spec_controller section table must be wrapped in table-enhanced-container."""
        src = _extract_function_source("_get_role_tasks_sections")

        spec_ctrl_idx = src.find("SPEC_CONTROLLER")
        assert spec_ctrl_idx != -1, "Could not find SPEC_CONTROLLER section"

        finance_idx = src.find("FINANCE", spec_ctrl_idx + 20)
        if finance_idx != -1:
            spec_ctrl_section = src[spec_ctrl_idx:finance_idx]
        else:
            spec_ctrl_section = src[spec_ctrl_idx:]

        assert 'cls="table-enhanced-container"' in spec_ctrl_section, (
            "The SPEC_CONTROLLER section is missing a table-enhanced-container wrapper."
        )
