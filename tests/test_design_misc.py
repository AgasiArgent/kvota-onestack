"""
Tests for date format (L6/L7) and miscellaneous design polish issues.

L6+L7: ISO dates (YYYY-MM-DD) shown instead of Russian DD.MM.YYYY in HTML templates.
M2: Suppliers filter inputs lack max-width constraint, too spacious.
M4: Quote detail status badge uses inline styles, not status-badge-v2 class.
M6: Spec-control group separators use raw "--- text ---" instead of styled divs.
M8: Document chain page header lacks card-elevated wrapper.
M10: Settings page header uses inline style, not card-elevated class.
L1: Zero profit rendered in green with "0" instead of dash/gray.
L3: Deals page renders "Финансовый менеджер" as a section heading.

All tests are written BEFORE fixes (TDD) and MUST FAIL.
"""

import pytest
import os
import re

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_main_lines():
    """Read main.py as a list of lines (1-indexed via enumerate)."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.readlines()


def _extract_route_handler(route_pattern: str, source: str = None) -> str:
    """Extract a route handler block starting with @rt(route_pattern) def get/post.

    Returns everything from the @rt line until the next @rt or top-level def/class.
    """
    if source is None:
        source = _read_main_source()
    escaped = re.escape(route_pattern)
    pattern = re.compile(
        rf'(@rt\({escaped}\)\s*def \w+\(.*?)(?=\n@rt\(|\nclass |\Z)',
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Route handler for {route_pattern} not found in main.py"
    return match.group(1)


def _extract_function_source(func_name: str, source: str = None) -> str:
    """Extract a function's source from main.py."""
    if source is None:
        source = _read_main_source()
    pattern = re.compile(
        rf'^(def {re.escape(func_name)}\(.*?)(?=\ndef |\n@rt\(|\nclass |\Z)',
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match, f"Function '{func_name}' not found in main.py"
    return match.group(1)


# ==============================================================================
# L6+L7: Date format -- ISO dates should be DD.MM.YYYY in HTML rendering
# ==============================================================================

class TestDateFormatRussian:
    """Dates displayed in HTML should use DD.MM.YYYY, not ISO YYYY-MM-DD.

    Currently main.py uses `[:10]` slicing on ISO timestamps (e.g. "2026-02-10"),
    producing ISO format. A format_date_ru() helper should exist and all date
    display code should use it for consistent DD.MM.YYYY output.
    """

    def test_format_date_ru_helper_exists_in_main(self):
        """main.py should define or import a format_date_ru / format_date_russian helper
        for use in HTML rendering (not just in export modules)."""
        source = _read_main_source()
        # Check that a Russian date formatter is available in main.py scope
        has_def = "def format_date_ru" in source or "def format_date_russian" in source
        has_import = "from services" in source and "format_date_russian" in source
        assert has_def or has_import, (
            "main.py should define or import a format_date_russian() helper "
            "for rendering dates in DD.MM.YYYY format in HTML templates. "
            "Currently dates use raw [:10] slicing which produces ISO format."
        )

    def test_no_iso_date_slicing_in_table_cells(self):
        """Date values rendered in Td() cells should NOT use [:10] slicing
        (which produces ISO YYYY-MM-DD). They should use format_date_russian()."""
        source = _read_main_source()
        # Find all lines that render dates in Td() with [:10] slicing
        iso_date_pattern = re.compile(
            r'Td\(.*?(?:created_at|updated_at|signed_at|planned_date|actual_date|requested_at|joined_at).*?\[:10\]'
        )
        matches = iso_date_pattern.findall(source)
        assert len(matches) == 0, (
            f"Found {len(matches)} Td() cells using [:10] date slicing (ISO format). "
            "All date rendering in table cells should use format_date_russian() "
            "to produce DD.MM.YYYY format. Examples:\n"
            + "\n".join(matches[:5])
        )

    def test_admin_page_dates_use_russian_format(self):
        """Admin page joined_at dates should use DD.MM.YYYY, not ISO [:10]."""
        source = _read_main_source()
        # Find the admin handler area where joined_at is formatted
        admin_area = source[source.find('"joined_at"'):source.find('"joined_at"') + 200]
        assert '[:10]' not in admin_area, (
            "Admin page 'joined_at' date uses [:10] ISO slicing. "
            "Should use format_date_russian() for DD.MM.YYYY display."
        )


# ==============================================================================
# M2: Suppliers filter -- inputs should have max-width constraints
# ==============================================================================

class TestM2SuppliersFilterLayout:
    """Suppliers page filter inputs should have max-width to prevent
    them from becoming too spacious on wide screens."""

    def test_supplier_filter_inputs_have_max_width(self):
        """Filter inputs in the suppliers search form should have max-width
        set so they don't stretch across the entire page width."""
        source = _read_main_source()
        # Find the suppliers filter area (around line 29820-29835)
        # The Form has style="display: flex; gap: 8px; ..."
        # Individual inputs should have max-width constraints
        supplier_filter_area_start = source.find('Поиск по названию или коду')
        assert supplier_filter_area_start != -1, "Suppliers filter area not found"

        # Extract ~500 chars around the filter section
        filter_area = source[supplier_filter_area_start - 200:supplier_filter_area_start + 400]

        # Check that Select elements (country, status) have max-width
        # Currently they just use filter_input_style without any width constraint
        has_select_max_width = 'max-width' in filter_area and 'Select' in filter_area
        # Or check filter_input_style has max-width
        filter_style_start = source.find('filter_input_style = """')
        if filter_style_start != -1:
            filter_style = source[filter_style_start:filter_style_start + 300]
            has_style_max_width = 'max-width' in filter_style
        else:
            has_style_max_width = False

        assert has_select_max_width or has_style_max_width, (
            "Supplier filter inputs (search, country, status) lack max-width constraint. "
            "On wide screens they stretch too much. Add max-width: 200px or similar "
            "to filter_input_style or individual Select elements."
        )


# ==============================================================================
# M4: Quote detail status badge -- should use status-badge-v2
# ==============================================================================

class TestM4QuoteDetailStatusBadge:
    """The workflow_status_badge() function uses inline styles instead of
    the reusable status-badge-v2 CSS class defined in the design system."""

    def test_workflow_status_badge_uses_v2_class(self):
        """workflow_status_badge() should use the status-badge-v2 class
        instead of one-off inline styles for consistency."""
        func_source = _extract_function_source("workflow_status_badge")

        assert "status-badge-v2" in func_source, (
            "workflow_status_badge() uses inline styles instead of the "
            "status-badge-v2 CSS class. The design system defines "
            ".status-badge-v2 with proper styling. The badge should use "
            'cls="status-badge-v2 status-badge-v2--{variant}" like '
            "status_badge_v2() does, for visual consistency."
        )


# ==============================================================================
# M6: Spec control group separators -- no raw "---" text
# ==============================================================================

class TestM6SpecControlSeparators:
    """Group separators in the spec-control unified table should use styled
    elements, not raw '--- Label ---' text strings."""

    def test_no_raw_triple_dash_separators(self):
        """Separator rows should NOT contain '---' as raw text.
        They should use a styled Div or Span with proper visual treatment."""
        source = _read_main_source()
        # Find the line that creates separator rows with "--- {group_label} ---"
        raw_separator = re.findall(r'f"---\s*\{.*?\}\s*---"', source)
        assert len(raw_separator) == 0, (
            f"Found {len(raw_separator)} raw '--- label ---' separator(s) in source. "
            "Group separators should use styled elements (e.g., "
            "Div(group_label, cls='group-separator-label') with CSS styling) "
            "instead of raw triple-dash text."
        )


# ==============================================================================
# M8: Document chain page -- header needs card-elevated
# ==============================================================================

class TestM8DocumentChainHeader:
    """The document chain section is now merged into the Documents tab.
    Verify it exists as a helper function called from the documents route."""

    def test_document_chain_merged_into_documents(self):
        """Document chain should be a helper section within the documents route,
        not a standalone page (route was removed in tab consolidation)."""
        source = _read_main_source()
        # The standalone route should NOT exist
        assert '@rt("/quotes/{quote_id}/document-chain")' not in source, (
            "Standalone document-chain route should have been removed — "
            "document chain is now merged into the Documents tab."
        )
        # The helper function should exist
        assert '_render_document_chain_section' in source, (
            "Expected _render_document_chain_section helper for the merged "
            "document chain section within the Documents tab."
        )


# ==============================================================================
# M10: Settings page -- header should use card-elevated class
# ==============================================================================

class TestM10SettingsHeader:
    """Settings page header should use the card-elevated CSS class
    instead of duplicating gradient styles inline."""

    def test_settings_header_uses_card_elevated_class(self):
        """The settings page header card should use cls='card-elevated'
        instead of inline header_style with duplicated gradient CSS."""
        source = _read_main_source()
        # Find the /settings GET handler
        route_start = source.find('@rt("/settings")\ndef get(session)')
        assert route_start != -1, "/settings route not found"

        handler_end = source.find('\n@rt(', route_start + 10)
        if handler_end == -1:
            handler_end = len(source)
        handler_source = source[route_start:handler_end]

        # The header card should use class, not inline gradient
        # Currently: style=header_style (with inline gradient)
        # Should use: cls="card-elevated" or cls="card-elevated-static"
        uses_class = 'card-elevated' in handler_source
        assert uses_class, (
            "Settings page header uses inline header_style with duplicated "
            "gradient CSS instead of the card-elevated class from the design system. "
            "Replace style=header_style with cls='card-elevated' or 'card-elevated-static'."
        )


# ==============================================================================
# L1: Zero profit -- should show dash or gray, not green "0"
# ==============================================================================

class TestL1ZeroProfitRendering:
    """Zero profit values should display as a dash or gray text,
    not as a green-colored '0' that looks like a real value."""

    def test_profit_column_handles_zero_gracefully(self):
        """When total_profit_usd is 0 or None, the quotes list should show
        '---' or gray text, not a green-colored currency value."""
        source = _read_main_source()
        # Find the profit Td in the quotes list
        # Currently the pattern spans two lines:
        #   Td(format_money(q.get("total_profit_usd")), cls="col-money",
        #      style="color: #059669; font-weight: 500;")
        # This always uses green (#059669) even for 0

        # Look for unconditional green coloring of profit (multiline)
        profit_pattern = re.compile(
            r'Td\(format_money\(q\.get\("total_profit_usd"\)\).*?color:\s*#059669',
            re.DOTALL,
        )
        unconditional_green = profit_pattern.findall(source)

        assert len(unconditional_green) == 0, (
            f"Found {len(unconditional_green)} profit cell(s) with unconditional green color. "
            "Zero profit should not be styled green (#059669). Use conditional coloring: "
            "green for positive, gray/dash for zero, red for negative."
        )

    def test_format_money_zero_returns_dash(self):
        """format_money(0) should return a dash or neutral indicator,
        not a currency-formatted zero like '$0' or '0 rub'."""
        import sys
        sys.path.insert(0, _PROJECT_ROOT)

        # Import format_money from main.py indirectly by reading its definition
        source = _read_main_source()
        func_source = _extract_function_source("format_money", source)

        # Check that the function handles zero specially
        assert 'value == 0' in func_source or 'not value' in func_source or 'value is None or value == 0' in func_source, (
            "format_money() does not handle zero values specially. "
            "When value is 0, it should return '---' or similar neutral indicator "
            "instead of formatting it as a currency amount (e.g., '\\u20bd0')."
        )


# ==============================================================================
# L3: Deals page -- unnecessary "Финансовый менеджер" heading
# ==============================================================================

class TestL3DealsPageHeading:
    """The deals page should not render 'Финансовый менеджер' as a
    prominent section heading. It's a role label, not a page title."""

    def test_no_financial_manager_heading(self):
        """The deals page content should not include H2('Финансовый менеджер')
        as a section heading. Stats cards should stand on their own."""
        source = _read_main_source()
        # Find the specific H2 heading
        pattern = re.compile(r'H2\(\s*"Финансовый менеджер"')
        matches = pattern.findall(source)
        assert len(matches) == 0, (
            "Deals page renders H2('Финансовый менеджер') as a section heading. "
            "This role-based label is unnecessary and out of place. "
            "Remove it -- the stats cards and deals table are self-explanatory."
        )
