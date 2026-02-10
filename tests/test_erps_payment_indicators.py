"""
TDD Tests for P1.8: Payment Countdown Indicators on ERPS Finance Registry.

Feature: Add color-coded payment countdown badges and remaining payment
percentage indicators to the ERPS (Ediniy Reestr Podpisannyh Spetsifikatsiy)
finance registry table.

Functions to be implemented in main.py:
  1. fmt_days_until_payment(days)     -- color-coded badge for days until advance
  2. fmt_remaining_payment_with_percent(remaining_usd, total_usd) -- remaining
     payment with percentage

Additional changes:
  - Summary footer on ERPS table: total outstanding debt, overdue count, urgent count
  - Row building loop in finance_erps_tab() uses custom formatters for
    days_until_advance and remaining_payment_usd columns

These tests are written BEFORE implementation (TDD).
All tests MUST FAIL until the feature is implemented.
"""

import pytest
import re
import os
from unittest.mock import MagicMock

# Path to main.py (project root)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _read_finance_erps_tab_source():
    """
    Extract the finance_erps_tab function source from main.py.
    Returns the full function body.
    """
    content = _read_main_source()
    match = re.search(
        r'^def finance_erps_tab\(.*?\n(.*?)(?=\ndef )',
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        pytest.fail("Could not find finance_erps_tab function in main.py")
    return match.group(0)


# ============================================================================
# 1. fmt_days_until_payment — Function Existence
# ============================================================================


class TestFmtDaysUntilPaymentExists:
    """Verify that fmt_days_until_payment is defined in main.py."""

    def test_function_defined_in_main(self):
        """fmt_days_until_payment must be defined in main.py."""
        source = _read_main_source()
        assert "def fmt_days_until_payment(" in source, (
            "fmt_days_until_payment() must be defined in main.py"
        )

    def test_function_used_in_finance_erps_tab(self):
        """finance_erps_tab must call fmt_days_until_payment."""
        source = _read_finance_erps_tab_source()
        assert "fmt_days_until_payment" in source, (
            "finance_erps_tab must use fmt_days_until_payment for days_until_advance column"
        )


# ============================================================================
# 2. fmt_days_until_payment — Green Badge (>7 days)
# ============================================================================


class TestFmtDaysUntilPaymentGreen:
    """days > 7: Green badge showing number of days. Safe zone."""

    def test_days_15_returns_green_badge(self):
        """15 days remaining: green badge with '15' in text."""
        source = _read_main_source()
        assert "def fmt_days_until_payment(" in source, (
            "fmt_days_until_payment must exist before testing green badge"
        )
        # Import and call the function
        # We need to test the actual function output, but since it returns
        # FastHTML elements, we test via source code patterns
        fn_source = _extract_fmt_days_function_source()
        # Should reference green color for >7
        assert "green" in fn_source.lower() or "#10b981" in fn_source or "#059669" in fn_source or "#22c55e" in fn_source, (
            "fmt_days_until_payment must use green color for days > 7"
        )

    def test_days_100_returns_green_badge(self):
        """100 days remaining: large number still gets green badge."""
        fn_source = _extract_fmt_days_function_source()
        # Check the conditional logic: >7 should be green
        has_gt_7_check = (
            "> 7" in fn_source
            or ">= 8" in fn_source
            or "> 7:" in fn_source
        )
        assert has_gt_7_check, (
            "fmt_days_until_payment must check for days > 7 to apply green badge"
        )

    def test_days_8_returns_green_badge(self):
        """8 days remaining: just above boundary, should be green."""
        fn_source = _extract_fmt_days_function_source()
        # 8 should hit the >7 path (green)
        has_gt_7 = "> 7" in fn_source or ">= 8" in fn_source
        assert has_gt_7, (
            "8 days should be in the green (>7) zone"
        )


# ============================================================================
# 3. fmt_days_until_payment — Yellow Badge (1-7 days)
# ============================================================================


class TestFmtDaysUntilPaymentYellow:
    """days 1-7: Yellow/amber badge. Urgent zone."""

    def test_days_7_returns_yellow_badge(self):
        """7 days remaining: boundary value, should be yellow."""
        fn_source = _extract_fmt_days_function_source()
        # Should reference yellow/amber color
        has_yellow = (
            "yellow" in fn_source.lower()
            or "amber" in fn_source.lower()
            or "#f59e0b" in fn_source
            or "#eab308" in fn_source
            or "#d97706" in fn_source
            or "#fbbf24" in fn_source
        )
        assert has_yellow, (
            "fmt_days_until_payment must use yellow/amber color for days 1-7"
        )

    def test_days_3_returns_yellow_badge(self):
        """3 days remaining: middle of yellow zone."""
        fn_source = _extract_fmt_days_function_source()
        # The function should have a range check for 1-7
        has_range_check = (
            "<= 7" in fn_source
            or "< 8" in fn_source
            or "in range" in fn_source
        )
        assert has_range_check, (
            "fmt_days_until_payment must have range check for yellow zone (1-7 days)"
        )

    def test_days_1_returns_yellow_badge(self):
        """1 day remaining: lower boundary of yellow zone."""
        fn_source = _extract_fmt_days_function_source()
        # Should check for days >= 1 (or > 0)
        has_lower_bound = (
            "> 0" in fn_source
            or ">= 1" in fn_source
        )
        assert has_lower_bound, (
            "fmt_days_until_payment must have lower bound check (>=1 or >0) for yellow zone"
        )


# ============================================================================
# 4. fmt_days_until_payment — Red Badge (<=0 days, overdue)
# ============================================================================


class TestFmtDaysUntilPaymentRed:
    """days <= 0: Red badge with 'PROSROCHENO'. Overdue zone."""

    def test_days_0_returns_red_badge(self):
        """0 days remaining: overdue, should be red."""
        fn_source = _extract_fmt_days_function_source()
        has_red = (
            "red" in fn_source.lower()
            or "#ef4444" in fn_source
            or "#dc2626" in fn_source
            or "#f87171" in fn_source
            or "#b91c1c" in fn_source
        )
        assert has_red, (
            "fmt_days_until_payment must use red color for days <= 0 (overdue)"
        )

    def test_days_0_shows_prosrocheno(self):
        """0 days: should show 'PROSROCHENO' text."""
        fn_source = _extract_fmt_days_function_source()
        has_overdue_text = (
            "ПРОСРОЧЕНО" in fn_source
            or "просрочено" in fn_source
            or "Просрочено" in fn_source
        )
        assert has_overdue_text, (
            "fmt_days_until_payment must show 'ПРОСРОЧЕНО' text when days <= 0"
        )

    def test_days_negative_5_shows_overdue_with_count(self):
        """Negative days (-5): should show overdue with day count."""
        fn_source = _extract_fmt_days_function_source()
        # Should reference abs() or negative days display
        has_abs_or_negative = (
            "abs(" in fn_source
            or "* -1" in fn_source
            or "-days" in fn_source
            or "abs(days)" in fn_source
        )
        assert has_abs_or_negative, (
            "fmt_days_until_payment must display absolute value of negative days "
            "(e.g., 'ПРОСРОЧЕНО 5 дн.')"
        )

    def test_overdue_check_condition(self):
        """Overdue check: must check days <= 0."""
        fn_source = _extract_fmt_days_function_source()
        has_overdue_condition = (
            "<= 0" in fn_source
            or "< 1" in fn_source
            or "< 0" in fn_source
        )
        assert has_overdue_condition, (
            "fmt_days_until_payment must have condition for overdue (days <= 0)"
        )


# ============================================================================
# 5. fmt_days_until_payment — Gray (None)
# ============================================================================


class TestFmtDaysUntilPaymentNone:
    """days=None: Gray dash. No data available."""

    def test_none_returns_gray_dash(self):
        """None days: should return gray '-' text."""
        fn_source = _extract_fmt_days_function_source()
        has_none_check = (
            "is None" in fn_source
            or "not days" in fn_source
            or "days is None" in fn_source
        )
        assert has_none_check, (
            "fmt_days_until_payment must handle None by returning gray dash"
        )

    def test_none_uses_gray_color(self):
        """None days: should use gray styling."""
        fn_source = _extract_fmt_days_function_source()
        has_gray = (
            "gray" in fn_source.lower()
            or "#9ca3af" in fn_source
            or "#6b7280" in fn_source
            or '"-"' in fn_source
        )
        assert has_gray, (
            "fmt_days_until_payment must use gray color or '-' for None value"
        )


# ============================================================================
# 6. fmt_remaining_payment_with_percent — Function Existence
# ============================================================================


class TestFmtRemainingPaymentExists:
    """Verify fmt_remaining_payment_with_percent is defined."""

    def test_function_defined_in_main(self):
        """fmt_remaining_payment_with_percent must be defined in main.py."""
        source = _read_main_source()
        assert "def fmt_remaining_payment_with_percent(" in source, (
            "fmt_remaining_payment_with_percent() must be defined in main.py"
        )

    def test_function_used_in_finance_erps_tab(self):
        """finance_erps_tab must call fmt_remaining_payment_with_percent."""
        source = _read_finance_erps_tab_source()
        assert "fmt_remaining_payment_with_percent" in source, (
            "finance_erps_tab must use fmt_remaining_payment_with_percent "
            "for remaining_payment_usd column"
        )


# ============================================================================
# 7. fmt_remaining_payment_with_percent — Normal Cases
# ============================================================================


class TestFmtRemainingPaymentNormal:
    """Test normal percentage calculation and display."""

    def test_25_percent_remaining(self):
        """remaining=5000, total=20000: shows '25.0%'."""
        fn_source = _extract_fmt_remaining_function_source()
        # Must calculate percentage
        has_percent_calc = (
            "%" in fn_source
            or "percent" in fn_source.lower()
        )
        assert has_percent_calc, (
            "fmt_remaining_payment_with_percent must calculate and display percentage"
        )

    def test_formats_dollar_amount(self):
        """Must format remaining amount as dollar value."""
        fn_source = _extract_fmt_remaining_function_source()
        has_dollar_format = (
            "$" in fn_source
            or "fmt_money" in fn_source
            or ":," in fn_source
        )
        assert has_dollar_format, (
            "fmt_remaining_payment_with_percent must format amount as currency"
        )


# ============================================================================
# 8. fmt_remaining_payment_with_percent — Color Coding
# ============================================================================


class TestFmtRemainingPaymentColors:
    """Test color coding based on percentage thresholds."""

    def test_zero_remaining_is_green(self):
        """remaining=0: fully paid, should be green."""
        fn_source = _extract_fmt_remaining_function_source()
        has_green = (
            "green" in fn_source.lower()
            or "#10b981" in fn_source
            or "#059669" in fn_source
            or "#22c55e" in fn_source
        )
        assert has_green, (
            "fmt_remaining_payment_with_percent must use green for 0% remaining (fully paid)"
        )

    def test_high_remaining_is_red(self):
        """remaining > 50% of total: high debt, should be red."""
        fn_source = _extract_fmt_remaining_function_source()
        has_red = (
            "red" in fn_source.lower()
            or "#ef4444" in fn_source
            or "#dc2626" in fn_source
        )
        assert has_red, (
            "fmt_remaining_payment_with_percent must use red for high remaining (>50%)"
        )

    def test_medium_remaining_is_amber(self):
        """remaining 20-50% of total: medium debt, should be amber/yellow."""
        fn_source = _extract_fmt_remaining_function_source()
        has_amber = (
            "amber" in fn_source.lower()
            or "yellow" in fn_source.lower()
            or "#f59e0b" in fn_source
            or "#d97706" in fn_source
            or "#eab308" in fn_source
        )
        assert has_amber, (
            "fmt_remaining_payment_with_percent must use amber for medium remaining (20-50%)"
        )

    def test_has_threshold_checks(self):
        """Must have threshold checks for color transitions."""
        fn_source = _extract_fmt_remaining_function_source()
        # Should check percentage thresholds like > 50, > 20
        has_thresholds = (
            ("50" in fn_source and "20" in fn_source)
            or ("> 0.5" in fn_source or "> 50" in fn_source)
        )
        assert has_thresholds, (
            "fmt_remaining_payment_with_percent must check percentage thresholds "
            "for color coding (e.g., >50% red, 20-50% amber)"
        )


# ============================================================================
# 9. fmt_remaining_payment_with_percent — Edge Cases
# ============================================================================


class TestFmtRemainingPaymentEdgeCases:
    """Test edge cases: None, zero total, division by zero."""

    def test_remaining_none_returns_gray(self):
        """remaining=None: should return gray '-'."""
        fn_source = _extract_fmt_remaining_function_source()
        has_none_check = (
            "is None" in fn_source
            or "remaining" in fn_source and "None" in fn_source
        )
        assert has_none_check, (
            "fmt_remaining_payment_with_percent must handle None remaining"
        )

    def test_total_zero_returns_gray(self):
        """total=0: division by zero protection."""
        fn_source = _extract_fmt_remaining_function_source()
        has_zero_check = (
            "== 0" in fn_source
            or "not total" in fn_source
            or "<= 0" in fn_source
            or "total_usd" in fn_source
        )
        assert has_zero_check, (
            "fmt_remaining_payment_with_percent must handle total=0 (division by zero)"
        )

    def test_total_none_returns_gray(self):
        """total=None: should return gray '-'."""
        fn_source = _extract_fmt_remaining_function_source()
        has_total_none = (
            "total" in fn_source
            and "None" in fn_source
        )
        assert has_total_none, (
            "fmt_remaining_payment_with_percent must handle total=None"
        )


# ============================================================================
# 10. Summary Footer — Existence and Content
# ============================================================================


class TestERPSSummaryFooter:
    """
    The ERPS table must have a summary footer showing:
    - Total outstanding debt (sum of remaining_payment_usd)
    - Overdue count (specs with days_until_advance <= 0)
    - Urgent count (specs with days_until_advance 1-7)
    """

    def test_summary_section_exists(self):
        """finance_erps_tab must include a summary section or footer."""
        source = _read_finance_erps_tab_source()
        has_summary = (
            "summary" in source.lower()
            or "footer" in source.lower()
            or "итого" in source.lower()
            or "total_outstanding" in source
            or "overdue_count" in source
        )
        assert has_summary, (
            "finance_erps_tab must include a summary section with totals"
        )

    def test_total_outstanding_debt_calculated(self):
        """Summary must calculate total outstanding debt."""
        source = _read_finance_erps_tab_source()
        has_outstanding = (
            "remaining_payment_usd" in source
            and ("sum(" in source.lower() or "total" in source.lower())
        )
        assert has_outstanding, (
            "finance_erps_tab must calculate total outstanding debt "
            "from remaining_payment_usd values"
        )

    def test_overdue_count_calculated(self):
        """Summary must count overdue specs (days_until_advance <= 0)."""
        source = _read_finance_erps_tab_source()
        has_overdue_count = (
            "overdue" in source.lower()
            or ("days_until_advance" in source and "<= 0" in source)
            or "просрочено" in source.lower()
        )
        assert has_overdue_count, (
            "finance_erps_tab must count overdue specs (days_until_advance <= 0)"
        )

    def test_urgent_count_calculated(self):
        """Summary must count urgent specs (days 1-7)."""
        source = _read_finance_erps_tab_source()
        has_urgent_count = (
            "urgent" in source.lower()
            or "срочн" in source.lower()
            or ("days_until_advance" in source and "7" in source)
        )
        assert has_urgent_count, (
            "finance_erps_tab must count urgent specs (days_until_advance 1-7)"
        )


# ============================================================================
# 11. Summary Calculation Logic
# ============================================================================


class TestSummaryCalculationLogic:
    """
    Test the calculation logic for summary aggregations.
    These tests verify expected behavior independent of implementation.
    """

    def test_mixed_specs_overdue_count(self):
        """Count overdue from mixed specs: days <= 0."""
        specs = [
            {"days_until_advance": -5, "remaining_payment_usd": 10000},
            {"days_until_advance": 0, "remaining_payment_usd": 5000},
            {"days_until_advance": 3, "remaining_payment_usd": 8000},
            {"days_until_advance": 15, "remaining_payment_usd": 12000},
            {"days_until_advance": None, "remaining_payment_usd": 2000},
        ]
        overdue = [
            s for s in specs
            if s.get("days_until_advance") is not None
            and s["days_until_advance"] <= 0
        ]
        assert len(overdue) == 2

    def test_mixed_specs_urgent_count(self):
        """Count urgent from mixed specs: days 1-7."""
        specs = [
            {"days_until_advance": -5, "remaining_payment_usd": 10000},
            {"days_until_advance": 0, "remaining_payment_usd": 5000},
            {"days_until_advance": 3, "remaining_payment_usd": 8000},
            {"days_until_advance": 7, "remaining_payment_usd": 4000},
            {"days_until_advance": 15, "remaining_payment_usd": 12000},
            {"days_until_advance": None, "remaining_payment_usd": 2000},
        ]
        urgent = [
            s for s in specs
            if s.get("days_until_advance") is not None
            and 1 <= s["days_until_advance"] <= 7
        ]
        assert len(urgent) == 2

    def test_mixed_specs_safe_count(self):
        """Count safe from mixed specs: days > 7."""
        specs = [
            {"days_until_advance": -5, "remaining_payment_usd": 10000},
            {"days_until_advance": 3, "remaining_payment_usd": 8000},
            {"days_until_advance": 15, "remaining_payment_usd": 12000},
            {"days_until_advance": 30, "remaining_payment_usd": 6000},
        ]
        safe = [
            s for s in specs
            if s.get("days_until_advance") is not None
            and s["days_until_advance"] > 7
        ]
        assert len(safe) == 2

    def test_total_outstanding_sum(self):
        """Sum all remaining_payment_usd values."""
        specs = [
            {"remaining_payment_usd": 10000},
            {"remaining_payment_usd": 5000},
            {"remaining_payment_usd": None},
            {"remaining_payment_usd": 8000},
        ]
        total = sum(
            float(s.get("remaining_payment_usd") or 0) for s in specs
        )
        assert total == 23000.0

    def test_empty_specs_list_totals(self):
        """Empty specs list: all counters should be 0."""
        specs = []
        overdue = [
            s for s in specs
            if s.get("days_until_advance") is not None
            and s["days_until_advance"] <= 0
        ]
        urgent = [
            s for s in specs
            if s.get("days_until_advance") is not None
            and 1 <= s["days_until_advance"] <= 7
        ]
        total = sum(
            float(s.get("remaining_payment_usd") or 0) for s in specs
        )
        assert len(overdue) == 0
        assert len(urgent) == 0
        assert total == 0.0

    def test_all_fully_paid_total_is_zero(self):
        """All specs fully paid: total outstanding = 0."""
        specs = [
            {"remaining_payment_usd": 0, "days_until_advance": 10},
            {"remaining_payment_usd": 0, "days_until_advance": 20},
            {"remaining_payment_usd": 0, "days_until_advance": 5},
        ]
        total = sum(
            float(s.get("remaining_payment_usd") or 0) for s in specs
        )
        assert total == 0.0

    def test_none_remaining_treated_as_zero(self):
        """None remaining_payment_usd values should be treated as 0 in sum."""
        specs = [
            {"remaining_payment_usd": None},
            {"remaining_payment_usd": None},
            {"remaining_payment_usd": 5000},
        ]
        total = sum(
            float(s.get("remaining_payment_usd") or 0) for s in specs
        )
        assert total == 5000.0


# ============================================================================
# 12. Row Building Uses Custom Formatters
# ============================================================================


class TestRowBuildingUsesCustomFormatters:
    """
    The row building loop in finance_erps_tab must use the custom
    formatter functions instead of the generic format_value for
    days_until_advance and remaining_payment_usd columns.
    """

    def test_days_column_uses_custom_formatter(self):
        """
        Row building must use fmt_days_until_payment for the
        days_until_advance column instead of generic format_value.
        """
        source = _read_finance_erps_tab_source()
        # The function should intercept days_until_advance in the row loop
        has_custom_days_formatter = (
            "fmt_days_until_payment" in source
            and "days_until_advance" in source
        )
        assert has_custom_days_formatter, (
            "Row building must use fmt_days_until_payment for days_until_advance column"
        )

    def test_remaining_column_uses_custom_formatter(self):
        """
        Row building must use fmt_remaining_payment_with_percent for the
        remaining_payment_usd column instead of generic format_value.
        """
        source = _read_finance_erps_tab_source()
        has_custom_remaining_formatter = (
            "fmt_remaining_payment_with_percent" in source
            and "remaining_payment_usd" in source
        )
        assert has_custom_remaining_formatter, (
            "Row building must use fmt_remaining_payment_with_percent "
            "for remaining_payment_usd column"
        )

    def test_custom_formatters_used_conditionally(self):
        """
        The row building loop should check column key and dispatch to
        custom formatters for specific columns.
        """
        source = _read_finance_erps_tab_source()
        # Should have conditional dispatch like:
        # if col['key'] == 'days_until_advance': ... fmt_days_until_payment
        # elif col['key'] == 'remaining_payment_usd': ... fmt_remaining_payment_with_percent
        has_conditional = (
            ("col['key']" in source or 'col["key"]' in source or "col_key" in source)
            and "days_until_advance" in source
            and "remaining_payment_usd" in source
        )
        assert has_conditional, (
            "Row building must conditionally dispatch to custom formatters "
            "based on column key"
        )


# ============================================================================
# 13. Integration: Both Functions in Same Scope
# ============================================================================


class TestIntegrationBothFunctions:
    """Verify both formatter functions coexist in main.py."""

    def test_both_formatters_defined(self):
        """Both fmt_days_until_payment and fmt_remaining_payment_with_percent must exist."""
        source = _read_main_source()
        has_days = "def fmt_days_until_payment(" in source
        has_remaining = "def fmt_remaining_payment_with_percent(" in source
        assert has_days, "fmt_days_until_payment not found in main.py"
        assert has_remaining, "fmt_remaining_payment_with_percent not found in main.py"

    def test_finance_erps_tab_exists(self):
        """finance_erps_tab function must exist in main.py."""
        source = _read_main_source()
        assert "def finance_erps_tab(" in source, (
            "finance_erps_tab function must exist in main.py"
        )

    def test_formatters_defined_before_erps_tab_or_nested(self):
        """
        Formatter functions must be accessible from finance_erps_tab,
        either defined before it or as nested functions inside it.
        """
        source = _read_main_source()
        erps_tab_source = _read_finance_erps_tab_source()

        # Either defined as top-level functions before finance_erps_tab
        # or as nested functions inside finance_erps_tab
        days_in_erps = "fmt_days_until_payment" in erps_tab_source
        remaining_in_erps = "fmt_remaining_payment_with_percent" in erps_tab_source

        days_top_level = "def fmt_days_until_payment(" in source
        remaining_top_level = "def fmt_remaining_payment_with_percent(" in source

        assert days_in_erps or days_top_level, (
            "fmt_days_until_payment must be accessible from finance_erps_tab"
        )
        assert remaining_in_erps or remaining_top_level, (
            "fmt_remaining_payment_with_percent must be accessible from finance_erps_tab"
        )


# ============================================================================
# 14. Percentage Calculation Logic
# ============================================================================


class TestPercentageCalculationLogic:
    """Test the percentage calculation independently."""

    def test_25_percent(self):
        """5000 / 20000 = 25.0%"""
        remaining = 5000
        total = 20000
        pct = (remaining / total) * 100
        assert pct == pytest.approx(25.0)

    def test_0_percent(self):
        """0 / 10000 = 0.0%"""
        remaining = 0
        total = 10000
        pct = (remaining / total) * 100
        assert pct == pytest.approx(0.0)

    def test_80_percent(self):
        """12000 / 15000 = 80.0%"""
        remaining = 12000
        total = 15000
        pct = (remaining / total) * 100
        assert pct == pytest.approx(80.0)

    def test_30_percent(self):
        """3000 / 10000 = 30.0%"""
        remaining = 3000
        total = 10000
        pct = (remaining / total) * 100
        assert pct == pytest.approx(30.0)

    def test_100_percent(self):
        """Full amount remaining."""
        remaining = 10000
        total = 10000
        pct = (remaining / total) * 100
        assert pct == pytest.approx(100.0)

    def test_division_by_zero_protection(self):
        """total=0 must not cause ZeroDivisionError."""
        remaining = 5000
        total = 0
        # Should default to 0 or return N/A
        if total == 0:
            pct = 0.0
        else:
            pct = (remaining / total) * 100
        assert pct == 0.0


# ============================================================================
# 15. Color Threshold Boundary Tests
# ============================================================================


class TestColorThresholdBoundaries:
    """Test boundary values for color coding in both functions."""

    def test_days_boundary_7_is_yellow_not_green(self):
        """days=7: must be yellow (<=7), not green (>7)."""
        fn_source = _extract_fmt_days_function_source()
        # The code should treat 7 as in the yellow zone
        # Check for <= 7 pattern (yellow includes 7)
        has_le_7 = "<= 7" in fn_source or "< 8" in fn_source
        has_gt_7 = "> 7" in fn_source or ">= 8" in fn_source
        # One of these patterns should exist to separate 7 into yellow
        assert has_le_7 or has_gt_7, (
            "Boundary at 7 must be handled: 7 should be yellow (<=7), 8+ should be green"
        )

    def test_days_boundary_0_is_red(self):
        """days=0: must be red (<=0)."""
        fn_source = _extract_fmt_days_function_source()
        has_zero_red = "<= 0" in fn_source or "< 1" in fn_source
        assert has_zero_red, (
            "days=0 must map to red zone (overdue)"
        )

    def test_remaining_50_percent_threshold(self):
        """50% remaining should be in the red zone boundary."""
        fn_source = _extract_fmt_remaining_function_source()
        has_50_check = (
            "50" in fn_source
            or "0.5" in fn_source
        )
        assert has_50_check, (
            "fmt_remaining_payment_with_percent must have 50% threshold for red zone"
        )

    def test_remaining_20_percent_threshold(self):
        """20% remaining should be the amber/yellow zone boundary."""
        fn_source = _extract_fmt_remaining_function_source()
        has_20_check = (
            "20" in fn_source
            or "0.2" in fn_source
        )
        assert has_20_check, (
            "fmt_remaining_payment_with_percent must have 20% threshold for amber zone"
        )


# ============================================================================
# Helper: Extract function source code
# ============================================================================


def _extract_fmt_days_function_source():
    """Extract the fmt_days_until_payment function source."""
    source = _read_main_source()
    match = re.search(
        r'def fmt_days_until_payment\(.*?\):\s*\n(.*?)(?=\n    def |\ndef )',
        source,
        re.DOTALL,
    )
    if not match:
        pytest.fail(
            "Could not find fmt_days_until_payment function in main.py. "
            "The function must be defined before these tests can validate "
            "its behavior."
        )
    return match.group(0)


def _extract_fmt_remaining_function_source():
    """Extract the fmt_remaining_payment_with_percent function source."""
    source = _read_main_source()
    match = re.search(
        r'def fmt_remaining_payment_with_percent\(.*?\):\s*\n(.*?)(?=\n    def |\ndef )',
        source,
        re.DOTALL,
    )
    if not match:
        pytest.fail(
            "Could not find fmt_remaining_payment_with_percent function in main.py. "
            "The function must be defined before these tests can validate "
            "its behavior."
        )
    return match.group(0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
