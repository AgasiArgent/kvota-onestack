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
    at main.py line 20610.

    This specific line has already been fixed. These tests verify the fix holds.
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

    def test_fixed_line_20610_exists_in_source(self):
        """Verify the fix is actually present in main.py at line ~20610."""
        source = _read_source(MAIN_PY)
        # The SAFE pattern must exist
        assert '(quote.get("customers") or {}).get("name"' in source, (
            "REGRESSION: The safe pattern for customers FK at line 20610 "
            "has been removed or reverted."
        )


# ============================================================================
# PART 3: Source-code scanning for REMAINING vulnerable patterns
# These tests FAIL until the developer fixes each pattern in main.py
# ============================================================================

class TestPickupLocationFKNullSafety:
    """main.py:17182-17191 -- pickup_location and supplier FK in invoice processing.

    Current (VULNERABLE):
        invoice.get("pickup_location", {}).get("city", "")
    Fixed:
        (invoice.get("pickup_location") or {}).get("city", "")
    """

    def test_pickup_location_city_uses_safe_pattern(self):
        """pickup_location FK access for 'city' must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        # The vulnerable pattern -- if this exists, the bug is NOT fixed
        vulnerable = 'invoice.get("pickup_location", {}).get("city"'
        safe = '(invoice.get("pickup_location") or {}).get("city"'

        has_vulnerable = vulnerable in source
        has_safe = safe in source

        assert not has_vulnerable, (
            f"VULNERABLE: invoice.get(\"pickup_location\", {{}}).get(\"city\") "
            f"found in main.py. Must use (invoice.get(\"pickup_location\") or {{}}).get(\"city\")."
        )

    def test_pickup_location_country_uses_safe_pattern(self):
        """pickup_location FK access for 'country' must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        vulnerable = 'invoice.get("pickup_location", {}).get("country"'

        assert vulnerable not in source, (
            f"VULNERABLE: invoice.get(\"pickup_location\", {{}}).get(\"country\") "
            f"found in main.py. Must use (invoice.get(\"pickup_location\") or {{}}).get(\"country\")."
        )

    def test_supplier_country_uses_safe_pattern(self):
        """supplier FK access for 'country' must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        vulnerable = 'invoice.get("supplier", {}).get("country"'

        assert vulnerable not in source, (
            f"VULNERABLE: invoice.get(\"supplier\", {{}}).get(\"country\") "
            f"found in main.py. Must use (invoice.get(\"supplier\") or {{}}).get(\"country\")."
        )


class TestPlanFactCategoriesFKNullSafety:
    """main.py:25924-25939 -- plan_fact_categories FK in plan-fact summaries.

    Current (VULNERABLE):
        item.get("plan_fact_categories", {}).get("is_income", False)
    Fixed:
        (item.get("plan_fact_categories") or {}).get("is_income", False)
    """

    def test_plan_fact_categories_uses_safe_pattern(self):
        """All plan_fact_categories FK accesses must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        vulnerable = 'item.get("plan_fact_categories", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'item.get("plan_fact_categories", {{}}).get(...) in main.py. '
            f"Must use (item.get(\"plan_fact_categories\") or {{}}).get(...)."
        )

    def test_plan_fact_is_income_null_scenario(self):
        """When plan_fact_categories FK is None, is_income filter must not crash."""
        item = {"planned_amount": 100, "plan_fact_categories": None}
        # Safe pattern
        is_income = (item.get("plan_fact_categories") or {}).get("is_income", False)
        assert is_income is False

    def test_plan_fact_is_income_with_false_default_preserved(self):
        """When plan_fact_categories is None, default for is_income must be False."""
        item = {"planned_amount": 100, "plan_fact_categories": None}
        result = (item.get("plan_fact_categories") or {}).get("is_income", False)
        assert result is False

    def test_plan_fact_is_income_with_true_default_preserved(self):
        """For expense filter, default is_income=True to exclude when negated."""
        item = {"planned_amount": 50, "plan_fact_categories": None}
        result = (item.get("plan_fact_categories") or {}).get("is_income", True)
        assert result is True


class TestPhaseResultsFKNullSafety:
    """main.py:20494-20498 -- phase_results JSON field in calc items.

    Current (VULNERABLE):
        item.get("phase_results", {}).get("T16", 0)
    Fixed:
        (item.get("phase_results") or {}).get("T16", 0)
    """

    def test_phase_results_uses_safe_pattern(self):
        """All phase_results accesses must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        vulnerable = 'item.get("phase_results", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'item.get("phase_results", {{}}).get(...) in main.py. '
            f"Must use (item.get(\"phase_results\") or {{}}).get(...)."
        )

    def test_phase_results_t16_null_scenario(self):
        """When phase_results is None, T16 extraction must not crash."""
        item = {"phase_results": None}
        result = float((item.get("phase_results") or {}).get("T16", 0) or 0)
        assert result == 0.0

    def test_phase_results_u16_null_scenario(self):
        """When phase_results is None, U16 extraction must not crash."""
        item = {"phase_results": None}
        result = float((item.get("phase_results") or {}).get("U16", 0) or 0)
        assert result == 0.0


class TestSettingValueFKNullSafety:
    """main.py:19564, 20961 -- setting_value JSON field.

    Current (VULNERABLE):
        result.data[0].get("setting_value", {}).get("columns", CALC_PRESET_BASIC)
    Fixed:
        (result.data[0].get("setting_value") or {}).get("columns", CALC_PRESET_BASIC)
    """

    def test_setting_value_uses_safe_pattern(self):
        """All setting_value accesses must use (x or {}) guard."""
        source = _read_source(MAIN_PY)
        vulnerable = '.get("setting_value", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'.get("setting_value", {{}}).get(...) in main.py. '
            f"Must use (.get(\"setting_value\") or {{}}).get(...)."
        )

    def test_setting_value_null_scenario(self):
        """When setting_value is None, columns extraction must not crash."""
        row = {"setting_value": None}
        default_columns = ["item", "qty", "price"]
        result = (row.get("setting_value") or {}).get("columns", default_columns)
        assert result == default_columns


class TestRolesFKNullSafety:
    """main.py:27758-27759 -- roles FK in list comprehension.

    Current code has if r.get("roles") guard, but still uses:
        r.get("roles", {}).get("slug", "")
    which is safe because of the if-guard. However, the , {} default
    is misleading and should be replaced with (or {}) for consistency.
    """

    def test_roles_fk_no_vulnerable_pattern(self):
        """roles FK should use safe (or {}) pattern for consistency."""
        source = _read_source(MAIN_PY)
        vulnerable = 'r.get("roles", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"INCONSISTENT: Found {count} occurrences of "
            f'r.get("roles", {{}}).get(...) in main.py. '
            f"Should use (r.get(\"roles\") or {{}}).get(...) for consistency, "
            f"even though the if-guard makes it technically safe."
        )


class TestCallbackQueryNullSafety:
    """main.py:22163, 22176 -- Telegram callback_query nested dict access.

    Current (VULNERABLE):
        json_data.get("callback_query", {}).get("message", {}).get("message_id")
    Fixed:
        (json_data.get("callback_query") or {}).get("message") or {}).get("message_id")
    """

    def test_callback_query_uses_safe_pattern(self):
        """All callback_query nested accesses must use (x or {}) guards."""
        source = _read_source(MAIN_PY)
        vulnerable = '.get("callback_query", {}).get("message", {}).get('

        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'chained .get("callback_query", {{}}).get("message", {{}}).get(...) in main.py. '
            f"Must guard with (x or {{}}) at each level."
        )

    def test_callback_query_null_scenario(self):
        """When callback_query is None, message_id extraction must not crash."""
        json_data = {"callback_query": None}
        result = ((json_data.get("callback_query") or {}).get("message") or {}).get(
            "message_id"
        )
        assert result is None

    def test_callback_query_message_null_scenario(self):
        """When callback_query.message is None, message_id extraction must not crash."""
        json_data = {"callback_query": {"message": None}}
        result = ((json_data.get("callback_query") or {}).get("message") or {}).get(
            "message_id"
        )
        assert result is None

    def test_callback_query_valid_scenario(self):
        """When callback_query.message has message_id, it should be extracted."""
        json_data = {"callback_query": {"message": {"message_id": 12345}}}
        result = ((json_data.get("callback_query") or {}).get("message") or {}).get(
            "message_id"
        )
        assert result == 12345


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

class TestNoVulnerablePatternsRemainInMainPy:
    """Scan main.py for any remaining .get("xxx", {}).get( patterns.
    Excludes known safe patterns (where the value is genuinely a dict, not a FK).
    """

    # FK field names known to come from PostgREST joins (can be null)
    FK_FIELDS = [
        "customers",
        "pickup_location",
        "supplier",
        "plan_fact_categories",
        "phase_results",
        "roles",
        "setting_value",
    ]

    @pytest.mark.parametrize("fk_field", FK_FIELDS)
    def test_no_vulnerable_fk_access_in_main_py(self, fk_field):
        """No FK field should use the unsafe .get("field", {}).get(...) pattern."""
        source = _read_source(MAIN_PY)
        vulnerable_pattern = f'.get("{fk_field}", {{}}).get('

        count = source.count(vulnerable_pattern)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'.get("{fk_field}", {{}}).get(...) in main.py. '
            f'Must use (.get("{fk_field}") or {{}}).get(...).'
        )

    def test_no_vulnerable_fk_access_in_quote_version_service(self):
        """No FK field should use the unsafe pattern in quote_version_service.py."""
        source = _read_source(QUOTE_VERSION_SERVICE_PY)
        # The only vulnerable pattern here is totals
        vulnerable = '.get("totals", {}).get('
        count = source.count(vulnerable)
        assert count == 0, (
            f"VULNERABLE: Found {count} occurrences of "
            f'.get("totals", {{}}).get(...) in quote_version_service.py.'
        )

    def test_count_all_vulnerable_patterns_in_main_py(self):
        """Count ALL remaining vulnerable .get("xxx", {}).get( patterns in main.py.
        This test gives a single summary count.
        """
        source = _read_source(MAIN_PY)
        # Match the general pattern: .get("some_field", {}).get(
        pattern = r'\.get\("[a-z_]+", \{\}\)\.get\('
        matches = re.findall(pattern, source)
        assert len(matches) == 0, (
            f"Found {len(matches)} total vulnerable .get(\"...\", {{}}).get(...) "
            f"patterns remaining in main.py. All must be converted to "
            f"(.get(\"...\") or {{}}).get(...).\n"
            f"Matches: {matches}"
        )


# ============================================================================
# PART 5: Edge cases for safe pattern with unusual values
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
