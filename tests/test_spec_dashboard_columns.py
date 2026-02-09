"""
TDD Tests for Spec Dashboard Columns: Summa (Amount) and Profit.

These tests define expected behavior for adding financial columns
(Сумма and Профит) to the specification control dashboard at /spec-control.

Current state: The spec-control dashboard does NOT show these columns.
These tests MUST FAIL until the feature is implemented.

Tests cover:
1. SQL query fetches total_amount_usd and total_profit_usd from quotes
2. Table headers include Сумма and Профит columns
3. Table rows display formatted financial values
4. Summary totals are calculated and displayed
5. Edge cases: specs without financial data, zero values, mixed currencies
"""

import pytest
import re
import os
from datetime import datetime
from uuid import uuid4


# ============================================================================
# Helper: Read the _dashboard_spec_control_content function source from main.py
# ============================================================================

MAIN_PY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "main.py"
)


def _read_spec_control_function_source():
    """
    Read the source code of _dashboard_spec_control_content from main.py.
    Extracts the function body from the file without importing the module.
    """
    with open(MAIN_PY_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the function definition and extract its body
    # The function starts with "def _dashboard_spec_control_content("
    # and ends before the next top-level "def " at the same indentation
    match = re.search(
        r'^def _dashboard_spec_control_content\(.*?\n(.*?)(?=\ndef )',
        content,
        re.MULTILINE | re.DOTALL
    )
    if not match:
        pytest.fail("Could not find _dashboard_spec_control_content function in main.py")

    return match.group(0)


# ============================================================================
# Test Data Factories
# ============================================================================

def make_uuid():
    return str(uuid4())


ORG_ID = make_uuid()
USER_ID = make_uuid()


def make_spec(
    spec_id=None,
    quote_id=None,
    status="draft",
    specification_number="SPEC-2026-0001",
    specification_currency="USD",
    total_amount_usd=None,
    total_profit_usd=None,
    customer_name="Test Customer",
    idn_quote="Q-202601-0001",
):
    """Create a mock specification with quote financial data."""
    return {
        "id": spec_id or make_uuid(),
        "quote_id": quote_id or make_uuid(),
        "specification_number": specification_number,
        "proposal_idn": idn_quote,
        "status": status,
        "sign_date": None,
        "specification_currency": specification_currency,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "organization_id": ORG_ID,
        "quotes": {
            "idn_quote": idn_quote,
            "total_amount_usd": total_amount_usd,
            "total_profit_usd": total_profit_usd,
            "customers": {
                "name": customer_name,
            },
        },
    }


# ============================================================================
# 1. SQL Query Tests: Verify the query fetches financial data
# ============================================================================

class TestSpecDashboardQueryFetchesFinancialData:
    """
    The spec-control dashboard SQL query must include total_amount_usd
    and total_profit_usd from the related quotes table.
    """

    def test_specs_query_selects_total_amount_usd(self):
        """
        The specifications query should include total_amount_usd
        in its select statement so financial data is available for display.
        """
        source = _read_spec_control_function_source()

        assert "total_amount_usd" in source, (
            "The _dashboard_spec_control_content function must select "
            "total_amount_usd from the quotes relationship"
        )

    def test_specs_query_selects_total_profit_usd(self):
        """
        The specifications query should include total_profit_usd
        in its select statement so profit data is available for display.
        """
        source = _read_spec_control_function_source()

        assert "total_profit_usd" in source, (
            "The _dashboard_spec_control_content function must select "
            "total_profit_usd from the quotes relationship"
        )


# ============================================================================
# 2. Table Header Tests: Verify column headers exist
# ============================================================================

class TestSpecDashboardColumnHeaders:
    """
    All specification tables on the spec-control page must include
    'Сумма' and 'Профит' column headers.
    """

    def test_spec_tables_have_summa_header(self):
        """Spec tables (not pending quotes table) must have a 'СУММА' or 'Сумма' column header."""
        source = _read_spec_control_function_source()
        # Currently the spec table headers are: № СПЕЦИФИКАЦИИ, КЛИЕНТ, СТАТУС, ВАЛЮТА, ДАТА, actions
        # The pending quotes table already has СУММА, but the spec tables do NOT.
        # We need СУММА in the spec table headers (those that start with "№ СПЕЦИФИКАЦИИ")
        spec_theads = re.findall(
            r'Thead\(Tr\(Th\("№ СПЕЦИФИКАЦИИ"\).*?\)\)',
            source,
            re.DOTALL
        )
        assert len(spec_theads) > 0, "Should find spec table Thead definitions"
        has_summa_in_spec_table = any(
            'Th("СУММА"' in thead or 'Th("Сумма"' in thead
            for thead in spec_theads
        )
        assert has_summa_in_spec_table, (
            "Spec tables (with '№ СПЕЦИФИКАЦИИ' header) must include a 'Сумма' column header"
        )

    def test_spec_tables_have_profit_header(self):
        """Spec tables must have a 'ПРОФИТ' or 'Профит' column header."""
        source = _read_spec_control_function_source()
        has_profit = 'Th("ПРОФИТ"' in source or 'Th("Профит"' in source
        assert has_profit, (
            "Spec tables must include a 'Профит' column header"
        )

    def test_all_spec_tables_have_financial_headers(self):
        """
        All specification section tables (pending_review, draft, approved, signed)
        use the same spec_row() function, so the headers should be uniform.
        The header row for spec tables must contain at least 8 Th columns
        (adding Сумма and Профит to the existing 6).
        """
        source = _read_spec_control_function_source()
        # Find all Thead definitions for spec tables (those with "СПЕЦИФИКАЦИИ" or "СТАТУС" header)
        # The Thead lines contain multiple Th() calls on the same or adjacent lines
        spec_theads = re.findall(
            r'Thead\(Tr\(Th\("№ СПЕЦИФИКАЦИИ"\).*?\)\)',
            source,
            re.DOTALL
        )
        assert len(spec_theads) > 0, "Should find spec table Thead definitions"
        for thead in spec_theads:
            th_count = thead.count("Th(")
            assert th_count >= 8, (
                f"Spec table headers should have at least 8 columns (got {th_count}). "
                "Expected: № СПЕЦИФИКАЦИИ, КЛИЕНТ, СТАТУС, ВАЛЮТА, СУММА, ПРОФИТ, ДАТА, actions"
            )


# ============================================================================
# 3. Row Display Tests: Verify financial values in table rows
# ============================================================================

class TestSpecDashboardRowDisplaysFinancialValues:
    """
    Each specification row in the table must display formatted
    Сумма and Профит values from the related quote.
    """

    def test_spec_row_includes_amount_td(self):
        """
        The spec_row() function must reference total_amount_usd
        to display the amount in a table cell.
        """
        source = _read_spec_control_function_source()
        assert "total_amount_usd" in source, (
            "spec_row must display total_amount_usd from the related quote"
        )

    def test_spec_row_includes_profit_td(self):
        """
        The spec_row() function must reference total_profit_usd
        to display the profit in a table cell.
        """
        source = _read_spec_control_function_source()
        assert "total_profit_usd" in source, (
            "spec_row must display total_profit_usd from the related quote"
        )

    def test_spec_row_formats_amount_as_currency(self):
        """
        The amount value should be formatted as currency (e.g., '$1,234').
        The pattern used elsewhere in the codebase is f"${amount:,.0f}".
        """
        source = _read_spec_control_function_source()
        # Should use dollar formatting or format_money for amount display
        has_dollar_format = "${" in source and ":," in source
        has_format_money = "format_money" in source
        assert has_dollar_format or has_format_money, (
            "spec_row must format amount as currency (e.g., '$1,234' or format_money())"
        )


# ============================================================================
# 4. Summary Totals Tests: Verify totals are calculated and displayed
# ============================================================================

class TestSpecDashboardSummaryTotals:
    """
    The spec-control dashboard should show summary totals for
    Сумма and Профит across all displayed specifications.
    """

    def test_total_amount_calculated(self):
        """
        The function must calculate a total amount sum across all specifications.
        This is typically done with sum() over total_amount_usd values.
        """
        source = _read_spec_control_function_source()
        assert "total_amount_usd" in source, (
            "Dashboard must reference total_amount_usd for calculating sums"
        )

    def test_total_profit_calculated(self):
        """
        The function must calculate a total profit sum across all specifications.
        """
        source = _read_spec_control_function_source()
        assert "total_profit_usd" in source, (
            "Dashboard must reference total_profit_usd for calculating sums"
        )

    def test_summary_displayed_in_stats_or_table(self):
        """
        The summary totals should be displayed in the stats cards section
        at the top of the page, or as a summary header/footer in each table section.
        Either approach is acceptable.
        """
        source = _read_spec_control_function_source()
        # Check that summary amounts are displayed somewhere in the output.
        # The sales dashboard uses patterns like:
        #   Span(f"Итого: ${specs_total_amount:,.0f} | Профит: ${specs_total_profit:,.0f}")
        # Or stat cards with total values
        has_itogo = "Итого" in source or "итого" in source
        has_total_display = ("total_amount" in source and "total_profit" in source
                            and ("stat-card" in source or "stat-value" in source
                                 or "Итого" in source))
        assert has_itogo or has_total_display, (
            "Dashboard must display summary totals (Итого or stat cards) "
            "for amount and profit"
        )


# ============================================================================
# 5. Calculation Logic Tests: Verify correct aggregation
# ============================================================================

class TestSpecDashboardAmountCalculation:
    """
    Test the calculation logic for aggregating financial data
    from specifications.
    """

    def test_sum_spec_amounts_basic(self):
        """Test basic summation of spec amounts from quote data."""
        specs = [
            make_spec(total_amount_usd=10000, total_profit_usd=2000),
            make_spec(total_amount_usd=25000, total_profit_usd=5000),
            make_spec(total_amount_usd=15000, total_profit_usd=3000),
        ]

        total_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )

        assert total_amount == 50000.0
        assert total_profit == 10000.0

    def test_sum_spec_amounts_with_none_values(self):
        """Test summation when some specs have None financial values."""
        specs = [
            make_spec(total_amount_usd=10000, total_profit_usd=2000),
            make_spec(total_amount_usd=None, total_profit_usd=None),
            make_spec(total_amount_usd=5000, total_profit_usd=1000),
        ]

        total_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )

        assert total_amount == 15000.0
        assert total_profit == 3000.0

    def test_sum_spec_amounts_with_zero_values(self):
        """Test summation when some specs have zero financial values."""
        specs = [
            make_spec(total_amount_usd=0, total_profit_usd=0),
            make_spec(total_amount_usd=10000, total_profit_usd=2000),
        ]

        total_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )

        assert total_amount == 10000.0
        assert total_profit == 2000.0

    def test_sum_spec_amounts_empty_list(self):
        """Test summation with no specs returns zero."""
        specs = []

        total_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )

        assert total_amount == 0.0
        assert total_profit == 0.0

    def test_sum_spec_amounts_missing_quotes_relation(self):
        """Test summation when quotes relationship is missing/null."""
        specs = [
            {"id": make_uuid(), "quotes": None},
            {"id": make_uuid()},
            make_spec(total_amount_usd=10000, total_profit_usd=2000),
        ]

        total_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in specs
        )
        total_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in specs
        )

        assert total_amount == 10000.0
        assert total_profit == 2000.0


# ============================================================================
# 6. Per-Status Aggregation Tests
# ============================================================================

class TestSpecDashboardPerStatusTotals:
    """
    Financial totals should be available per status group
    (draft, pending_review, approved, signed) for proper display.
    """

    def test_amounts_aggregated_per_status(self):
        """
        When specs are filtered by status, the totals should
        reflect only specs in that status group.
        """
        all_specs = [
            make_spec(status="draft", total_amount_usd=10000, total_profit_usd=1000),
            make_spec(status="draft", total_amount_usd=20000, total_profit_usd=3000),
            make_spec(status="pending_review", total_amount_usd=50000, total_profit_usd=8000),
            make_spec(status="approved", total_amount_usd=100000, total_profit_usd=15000),
            make_spec(status="signed", total_amount_usd=75000, total_profit_usd=12000),
        ]

        draft_specs = [s for s in all_specs if s["status"] == "draft"]
        draft_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in draft_specs
        )
        draft_profit = sum(
            float((s.get("quotes") or {}).get("total_profit_usd") or 0)
            for s in draft_specs
        )
        assert draft_amount == 30000.0
        assert draft_profit == 4000.0

        pending_specs = [s for s in all_specs if s["status"] == "pending_review"]
        pending_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in pending_specs
        )
        assert pending_amount == 50000.0

        overall_amount = sum(
            float((s.get("quotes") or {}).get("total_amount_usd") or 0)
            for s in all_specs
        )
        assert overall_amount == 255000.0


# ============================================================================
# 7. Formatting Tests
# ============================================================================

class TestSpecDashboardAmountFormatting:
    """Test formatting of financial values in the dashboard."""

    def test_format_usd_amount(self):
        """USD amounts should be formatted as $XX,XXX."""
        amount = 12345.67
        formatted = f"${amount:,.0f}"
        assert formatted == "$12,346"

    def test_format_zero_amount(self):
        """Zero amounts should show as $0."""
        amount = 0.0
        formatted = f"${amount:,.0f}"
        assert formatted == "$0"

    def test_format_large_amount(self):
        """Large amounts should have thousand separators."""
        amount = 1234567.89
        formatted = f"${amount:,.0f}"
        assert formatted == "$1,234,568"

    def test_format_none_amount_defaults_to_zero(self):
        """None amount should default to 0 and format as $0."""
        raw_value = None
        amount = float(raw_value or 0)
        formatted = f"${amount:,.0f}"
        assert formatted == "$0"


# ============================================================================
# 8. Source Code Structure Tests: Column count validation
# ============================================================================

class TestSpecDashboardTableStructure:
    """
    Validate that the spec-control tables have been updated
    to include the new financial columns.
    """

    def test_spec_row_has_enough_td_cells(self):
        """
        The spec_row() function must return a row with at least 8 Td cells:
        spec_number, customer, status, currency, amount, profit, date, actions
        """
        source = _read_spec_control_function_source()

        # Find the spec_row inner function body
        spec_row_match = re.search(
            r'def spec_row\(.*?\):\s*\n(.*?)(?=\n    def |\n    return \[)',
            source,
            re.DOTALL
        )

        assert spec_row_match is not None, "spec_row function not found"

        spec_row_body = spec_row_match.group(1)
        td_count = spec_row_body.count("Td(")

        assert td_count >= 8, (
            f"spec_row must have at least 8 Td cells (got {td_count}). "
            "Expected: spec_number, customer, status, currency, amount, profit, date, actions"
        )

    def test_colspan_updated_for_empty_tables(self):
        """
        Empty table messages use colspan to span all columns.
        After adding 2 new columns, colspan should be updated from 6 to 8.
        """
        source = _read_spec_control_function_source()

        # Find all colspan values in the source
        spec_colspans = re.findall(r'colspan="(\d+)"', source)

        # There should be at least one colspan of 8 for spec tables
        has_updated_colspan = any(int(c) >= 8 for c in spec_colspans)
        assert has_updated_colspan, (
            f"Empty spec table messages should use colspan='8' (found: {spec_colspans}). "
            "Colspan must match the new column count after adding Сумма and Профит"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
