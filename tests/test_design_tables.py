"""
Tests for table-enhanced design consistency across finance calendar pages.

Design issue group:
  M9  - Payments calendar: table uses unified-table instead of table-enhanced

All tables in the application should use the `table-enhanced` class and be wrapped
in a `table-enhanced-container` div for consistent styling (gradient header, hover
effects, proper spacing).

These tests are written BEFORE the fix (TDD).
All tests MUST FAIL until the design issues are resolved.

Note: Former M5 (dashboard overview "Последние КП"), M11 (dashboard sales
"Активные спецификации"/"Активные КП"), and M12 (tasks page spec_controller)
tests were removed during Phase 6C-2B-7 archive of /dashboard + /tasks
(2026-04-20). Their target helpers (_dashboard_overview_content,
_dashboard_sales_content, _get_role_tasks_sections) now live in
legacy-fasthtml/dashboard_tasks.py and are not imported.
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
