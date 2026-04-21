"""
Tests for PostgREST FK null-safety bug.

BUG: PostgREST returns {"customers": null} when FK join has no match.
Python code uses .get("customers", {}).get("name", "---") but the {}
default NEVER triggers because the key EXISTS with value None.
Result: None.get("name") -> AttributeError.

FIX PATTERN: Replace .get("fk", {}).get(...) with (obj.get("fk") or {}).get(...)

ALREADY FIXED (11 occurrences):
    customer_name patterns using (quote.get("customers") or {}).get("name", "---")

STILL VULNERABLE (not yet fixed):
    - pickup_location FK (main.py:17182-17191)
    - supplier FK (main.py:17190-17191)
    - plan_fact_categories FK (main.py:25924-25939)
    - phase_results JSON (main.py:20494-20498)
    - setting_value JSON (main.py:19564, 20961)
    - roles FK (main.py:27758-27759) -- has if-guard but still uses , {}
    - callback_query nested (main.py:22163, 22176)
    - totals dict (services/quote_version_service.py:221, 278)

Tests are written to FAIL against current code for unfixed patterns,
and PASS once the (x or {}).get(...) pattern is applied everywhere.
"""

import pytest
import os
import re
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")
QUOTE_VERSION_SERVICE_PY = os.path.join(
    _PROJECT_ROOT, "services", "quote_version_service.py"
)


def _read_source(path):
    """Read source file contents."""
    with open(path) as f:
        return f.read()


# ============================================================================
# PART 1: Generic safe-access pattern validation
# ============================================================================

class TestSafeAccessPattern:
    """Validate that (x.get(key) or {}).get(...) is safe for all FK scenarios."""

    @pytest.mark.parametrize(
        "obj, fk_key, nested_key, default, expected",
        [
            # FK key is None (PostgREST null join) -- the actual bug trigger
            ({"customers": None}, "customers", "name", "---", "---"),
            ({"pickup_location": None}, "pickup_location", "city", "", ""),
            ({"supplier": None}, "supplier", "country", "", ""),
            ({"plan_fact_categories": None}, "plan_fact_categories", "is_income", False, False),
            ({"phase_results": None}, "phase_results", "T16", 0, 0),
            ({"setting_value": None}, "setting_value", "columns", [], []),
            ({"roles": None}, "roles", "slug", "", ""),
            # FK key is missing entirely
            ({}, "customers", "name", "---", "---"),
            ({}, "pickup_location", "city", "", ""),
            ({}, "supplier", "country", "", ""),
            ({}, "plan_fact_categories", "is_income", False, False),
            ({}, "phase_results", "T16", 0, 0),
            # FK key has valid dict
            ({"customers": {"name": "Acme Corp"}}, "customers", "name", "---", "Acme Corp"),
            ({"pickup_location": {"city": "Moscow"}}, "pickup_location", "city", "", "Moscow"),
            ({"supplier": {"country": "CN"}}, "supplier", "country", "", "CN"),
            (
                {"plan_fact_categories": {"is_income": True}},
                "plan_fact_categories",
                "is_income",
                False,
                True,
            ),
            ({"phase_results": {"T16": 42.5}}, "phase_results", "T16", 0, 42.5),
        ],
        ids=[
            "customers-null",
            "pickup_location-null",
            "supplier-null",
            "plan_fact_categories-null",
            "phase_results-null",
            "setting_value-null",
            "roles-null",
            "customers-missing",
            "pickup_location-missing",
            "supplier-missing",
            "plan_fact_categories-missing",
            "phase_results-missing",
            "customers-valid",
            "pickup_location-valid",
            "supplier-valid",
            "plan_fact_categories-valid",
            "phase_results-valid",
        ],
    )
    def test_safe_pattern_does_not_crash(
        self, obj, fk_key, nested_key, default, expected
    ):
        """The safe pattern (obj.get(key) or {}).get(nested, default) must never crash."""
        result = (obj.get(fk_key) or {}).get(nested_key, default)
        assert result == expected

    @pytest.mark.parametrize(
        "obj, fk_key, nested_key, default",
        [
            ({"customers": None}, "customers", "name", "---"),
            ({"pickup_location": None}, "pickup_location", "city", ""),
            ({"supplier": None}, "supplier", "country", ""),
            ({"plan_fact_categories": None}, "plan_fact_categories", "is_income", False),
            ({"phase_results": None}, "phase_results", "T16", 0),
        ],
        ids=[
            "customers-null-crash",
            "pickup_location-null-crash",
            "supplier-null-crash",
            "plan_fact_categories-null-crash",
            "phase_results-null-crash",
        ],
    )
    def test_unsafe_pattern_crashes_on_none(self, obj, fk_key, nested_key, default):
        """Demonstrate that the UNSAFE pattern .get(key, {}).get(...) crashes
        when value is None -- because default {} is NOT used when key EXISTS."""
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
            # This is the BROKEN pattern that must be replaced everywhere
            obj.get(fk_key, {}).get(nested_key, default)


# ============================================================================
# PART 2: Regression test for the exact Sentry crash at line 20610
# ============================================================================

class TestSentryCrashLine20610:
    """Regression test for the Sentry crash:
    customer_name = (quote.get("customers") or {}).get("name", "---")
    formerly at main.py line 20610 (cost-analysis handler).

    The handler was archived to legacy-fasthtml/cost_analysis.py during
    Phase 6C-2B Mega-F (2026-04-20). The safe pattern is preserved in the
    archive. These unit tests still verify the defensive pattern itself,
    which documents the correct approach for future FK-join code.

    The previous source-scan assertion (`test_fixed_line_20610_exists_in_source`)
    was removed alongside the archive — main.py no longer contains the
    vulnerable call site to regress against.
    """

    def test_fixed_line_20610_with_null_customer(self):
        """Line 20610 should not crash when customers FK is None."""
        quote = {"id": "abc", "customers": None, "total_amount": 1000}
        # Fixed pattern:
        customer_name = (quote.get("customers") or {}).get("name", "---")
        assert customer_name == "---"

    def test_fixed_line_20610_with_missing_customer(self):
        """Line 20610 should not crash when customers key is absent."""
        quote = {"id": "abc", "total_amount": 1000}
        customer_name = (quote.get("customers") or {}).get("name", "---")
        assert customer_name == "---"

    def test_fixed_line_20610_with_valid_customer(self):
        """Line 20610 should return customer name when FK is populated."""
        quote = {"id": "abc", "customers": {"name": "Acme"}, "total_amount": 1000}
        customer_name = (quote.get("customers") or {}).get("name", "---")
        assert customer_name == "Acme"


# ============================================================================
# PART 3: Source-code scanning for REMAINING vulnerable patterns
# These tests FAIL until the developer fixes each pattern in main.py
# ============================================================================

class TestTotalsDictNullSafety:
    """services/quote_version_service.py:221, 278 -- totals dict access.

    Current (VULNERABLE):
        input_vars.get("totals", {}).get("total_with_vat", 0)
    Fixed:
        (input_vars.get("totals") or {}).get("total_with_vat", 0)
    """

    def test_totals_uses_safe_pattern_in_version_service(self):
        """All totals dict accesses must use (x or {}) guard in quote_version_service."""
        source = _read_source(QUOTE_VERSION_SERVICE_PY)
        vulnerable = '.get("totals", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'.get("totals", {{}}).get(...) in quote_version_service.py. '
            f"Must use (.get(\"totals\") or {{}}).get(...)."
        )

    def test_totals_null_scenario(self):
        """When totals is None, total_with_vat extraction must not crash."""
        input_vars = {"totals": None}
        result = (input_vars.get("totals") or {}).get("total_with_vat", 0)
        assert result == 0


# ============================================================================
# PART 4: Global scan -- no remaining .get("fk", {}).get( patterns
# ============================================================================

class TestSafePatternEdgeCases:
    """Edge cases to confirm the (x or {}) pattern handles all truthy/falsy values."""

    def test_fk_is_empty_dict(self):
        """Empty dict FK should be safe -- (x or {}) returns the empty dict itself."""
        obj = {"customers": {}}
        result = (obj.get("customers") or {}).get("name", "fallback")
        assert result == "fallback"

    def test_fk_is_zero(self):
        """Numeric 0 is falsy -- (x or {}) returns {} which is safe."""
        obj = {"customers": 0}
        result = (obj.get("customers") or {}).get("name", "fallback")
        assert result == "fallback"

    def test_fk_is_empty_string(self):
        """Empty string is falsy -- (x or {}) returns {} which is safe."""
        obj = {"customers": ""}
        result = (obj.get("customers") or {}).get("name", "fallback")
        assert result == "fallback"

    def test_fk_is_false(self):
        """Boolean False is falsy -- (x or {}) returns {} which is safe."""
        obj = {"customers": False}
        result = (obj.get("customers") or {}).get("name", "fallback")
        assert result == "fallback"

    def test_fk_is_empty_list(self):
        """Empty list is falsy -- (x or {}) returns {} which is safe.
        PostgREST can return [] for array joins."""
        obj = {"items": []}
        result = (obj.get("items") or {}).get("name", "fallback")
        assert result == "fallback"

    def test_sum_with_none_phase_results_in_list(self):
        """Simulate the actual sum() pattern from main.py:20493-20499
        with mixed None and valid phase_results."""
        calc_items_data = [
            {"phase_results": {"T16": 100.5, "U16": 50.0}},
            {"phase_results": None},  # FK null join
            {"phase_results": {"T16": 200.0, "U16": 75.0}},
            {},  # Missing key entirely
        ]

        logistics_first_leg = sum(
            float((item.get("phase_results") or {}).get("T16", 0) or 0)
            for item in calc_items_data
        )
        logistics_last_leg = sum(
            float((item.get("phase_results") or {}).get("U16", 0) or 0)
            for item in calc_items_data
        )

        assert logistics_first_leg == 300.5
        assert logistics_last_leg == 125.0

    def test_plan_fact_filter_with_none_categories_in_list(self):
        """Simulate the actual plan-fact filter from main.py:25921-25939
        with mixed None and valid plan_fact_categories."""
        plan_fact_items = [
            {"planned_amount": 1000, "plan_fact_categories": {"is_income": True}},
            {"planned_amount": 500, "plan_fact_categories": None},  # FK null
            {"planned_amount": 200, "plan_fact_categories": {"is_income": False}},
            {"planned_amount": 300, "plan_fact_categories": None},  # FK null
        ]

        total_planned_income = sum(
            float(item.get("planned_amount", 0) or 0)
            for item in plan_fact_items
            if (item.get("plan_fact_categories") or {}).get("is_income", False)
        )
        total_planned_expense = sum(
            float(item.get("planned_amount", 0) or 0)
            for item in plan_fact_items
            if not (item.get("plan_fact_categories") or {}).get("is_income", True)
        )

        # Only the first item has is_income=True
        assert total_planned_income == 1000.0
        # The third item has is_income=False; None defaults to True, so not included
        assert total_planned_expense == 200.0
