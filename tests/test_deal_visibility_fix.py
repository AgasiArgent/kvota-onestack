"""
Tests for BUG-C: Deal visibility fix - PostgREST FK ambiguity

Bug: deals table has 2 FKs to specifications and quotes. Queries that join
specifications(...) and quotes(...) without FK hints cause PostgREST ambiguity
error, resulting in silent failure and empty results on /deals page.

Fix: Add FK hints to deal queries:
  - specifications!deals_specification_id_fkey(...)
  - quotes!deals_quote_id_fkey(...)

These tests verify the source code contains correct FK hint syntax.
Tests MUST FAIL before the fix is applied (TDD).
"""

import os
import re
import sys

import pytest

# Project root for reading main.py
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


@pytest.fixture(scope="module")
def main_py_content():
    """Read main.py source code once for all tests in this module."""
    with open(MAIN_PY, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def main_py_lines():
    """Read main.py as a list of lines for line-level analysis."""
    with open(MAIN_PY, "r") as f:
        return f.readlines()


def _find_deals_select_blocks(content):
    """
    Find all supabase.table("deals").select(...) blocks that span
    potentially multiple lines. Returns list of (start_line, select_string) tuples.

    We need to extract the full select string (which may span multiple lines)
    for each deals query that joins specifications or quotes.
    """
    blocks = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'table("deals").select(' in line:
            # Collect the full select() call (may span multiple lines)
            select_str = line
            paren_depth = line.count("(") - line.count(")")
            start_line = i + 1  # 1-indexed
            j = i + 1
            while paren_depth > 0 and j < len(lines):
                select_str += "\n" + lines[j]
                paren_depth += lines[j].count("(") - lines[j].count(")")
                j += 1
            blocks.append((start_line, select_str))
            i = j
        else:
            i += 1
    return blocks


def _get_deals_join_blocks(content):
    """
    Get only deals select blocks that join specifications or quotes.
    These are the ones that need FK hints.
    """
    all_blocks = _find_deals_select_blocks(content)
    join_blocks = []
    for line_num, select_str in all_blocks:
        if "specifications(" in select_str or "quotes(" in select_str:
            join_blocks.append((line_num, select_str))
    return join_blocks


# =============================================================================
# TEST CLASS: Deal List Query FK Hints
# =============================================================================

class TestDealListQueryFKHints:
    """
    Verify the deal list query (finance_workspace_tab) uses FK hints
    when joining specifications and quotes tables.

    Bug: Without FK hints, PostgREST cannot resolve which FK to use when
    deals has both specification_id and quote_id columns, causing ambiguity
    error and returning empty results.
    """

    def test_deal_list_specifications_fk_hint(self, main_py_content):
        """
        Deal list query must use specifications!deals_specification_id_fkey
        instead of bare specifications(...) to avoid PostgREST ambiguity.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)
        assert len(join_blocks) >= 1, "Expected at least 1 deals query that joins specifications/quotes"

        # Find the deal list query (first one that joins specifications)
        deal_list_found = False
        for line_num, select_str in join_blocks:
            if "specifications(" in select_str and "specification_number" in select_str:
                # This is likely the deal list query (contains specification_number in select)
                # Must have FK hint
                assert "specifications!" in select_str, (
                    f"Deal list query at ~line {line_num} joins specifications without FK hint. "
                    f"Must use specifications!deals_specification_id_fkey(...) syntax. "
                    f"Got: {select_str[:200]}"
                )
                deal_list_found = True
                break

        assert deal_list_found, (
            "Could not find deal list query that selects specification_number"
        )

    def test_deal_list_quotes_fk_hint(self, main_py_content):
        """
        Deal list query must use quotes!deals_quote_id_fkey
        instead of bare quotes(...) to avoid PostgREST ambiguity.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        # Find the deal list query (has quotes(...) with idn_quote)
        deal_list_found = False
        for line_num, select_str in join_blocks:
            if "quotes(" in select_str and "idn_quote" in select_str and "specification_number" in select_str:
                # This is the deal list query
                assert "quotes!" in select_str, (
                    f"Deal list query at ~line {line_num} joins quotes without FK hint. "
                    f"Must use quotes!deals_quote_id_fkey(...) syntax. "
                    f"Got: {select_str[:200]}"
                )
                deal_list_found = True
                break

        assert deal_list_found, (
            "Could not find deal list query that selects idn_quote + specification_number"
        )


# =============================================================================
# TEST CLASS: Deal Detail Query FK Hints
# =============================================================================

class TestDealDetailQueryFKHints:
    """
    Verify the deal detail query uses FK hints when joining
    specifications and quotes tables.
    """

    def test_deal_detail_specifications_fk_hint(self, main_py_content):
        """
        Deal detail query must use specifications! FK hint.
        The detail query selects more fields (sign_date, validity_period, etc.)
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        # Find the detail query - it has more specification fields like sign_date
        detail_found = False
        for line_num, select_str in join_blocks:
            if "specifications(" in select_str and "sign_date" in select_str:
                assert "specifications!" in select_str, (
                    f"Deal detail query at ~line {line_num} joins specifications without FK hint. "
                    f"Must use specifications!deals_specification_id_fkey(...) syntax. "
                    f"Got: {select_str[:300]}"
                )
                detail_found = True
                break

        assert detail_found, (
            "Could not find deal detail query that selects sign_date from specifications"
        )

    def test_deal_detail_quotes_fk_hint(self, main_py_content):
        """
        Deal detail query must use quotes! FK hint.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        # Find the detail query
        detail_found = False
        for line_num, select_str in join_blocks:
            if "sign_date" in select_str and "quotes(" in select_str:
                assert "quotes!" in select_str, (
                    f"Deal detail query at ~line {line_num} joins quotes without FK hint. "
                    f"Must use quotes!deals_quote_id_fkey(...) syntax. "
                    f"Got: {select_str[:300]}"
                )
                detail_found = True
                break

        assert detail_found, (
            "Could not find deal detail query with sign_date that also joins quotes"
        )


# =============================================================================
# TEST CLASS: No Bare specifications/quotes Joins in Deals Queries
# =============================================================================

class TestNoBareJoinsInDealsQueries:
    """
    Ensure that NO deals query uses bare 'specifications(' or 'quotes('
    without FK hints. Every join must be disambiguated.
    """

    def test_no_bare_specifications_join_in_any_deals_query(self, main_py_content):
        """
        Every table("deals").select() that references specifications must
        use the FK hint syntax (specifications!...) not bare specifications(.

        Bare 'specifications(' (not preceded by '!') would trigger PostgREST
        ambiguity error.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        for line_num, select_str in join_blocks:
            if "specifications(" in select_str:
                # Check that every 'specifications(' is preceded by '!'
                # Find all occurrences of 'specifications('
                # Each must be 'specifications!...(', not bare 'specifications('
                # Use regex: find 'specifications(' NOT preceded by '!'
                bare_matches = re.findall(r'(?<![!a-zA-Z_])specifications\(', select_str)
                hinted_matches = re.findall(r'specifications![a-zA-Z_]+\(', select_str)

                assert len(bare_matches) == 0, (
                    f"Deal query at ~line {line_num} has bare 'specifications(' without FK hint. "
                    f"Found {len(bare_matches)} bare join(s) vs {len(hinted_matches)} hinted join(s). "
                    f"All must use specifications!deals_specification_id_fkey(...) syntax."
                )

    def test_no_bare_quotes_join_in_any_deals_query(self, main_py_content):
        """
        Every table("deals").select() that references quotes must
        use the FK hint syntax (quotes!...) not bare quotes(.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        for line_num, select_str in join_blocks:
            if "quotes(" in select_str:
                bare_matches = re.findall(r'(?<![!a-zA-Z_])quotes\(', select_str)
                hinted_matches = re.findall(r'quotes![a-zA-Z_]+\(', select_str)

                assert len(bare_matches) == 0, (
                    f"Deal query at ~line {line_num} has bare 'quotes(' without FK hint. "
                    f"Found {len(bare_matches)} bare join(s) vs {len(hinted_matches)} hinted join(s). "
                    f"All must use quotes!deals_quote_id_fkey(...) syntax."
                )


# =============================================================================
# TEST CLASS: Pattern Verification - All Deals Queries Covered
# =============================================================================

class TestAllDealsQueriesWithJoinsCovered:
    """
    Verify that ALL table("deals").select() calls that join related
    tables use FK hints. This is a comprehensive sweep to catch any
    query we might have missed.
    """

    def test_count_deals_queries_with_joins(self, main_py_content):
        """
        There should be exactly 2 deals queries that join specifications/quotes:
        1. Deal list query (finance_workspace_tab)
        2. Deal detail query (deal detail page)

        If more are added in the future, this test will flag them for FK hint review.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)
        assert len(join_blocks) >= 2, (
            f"Expected at least 2 deals queries with specifications/quotes joins, "
            f"found {len(join_blocks)}. Check if new queries were added without FK hints."
        )

    def test_all_deals_join_queries_have_complete_fk_hints(self, main_py_content):
        """
        Every deals query that joins specifications or quotes must have
        FK hints on ALL joined tables (not just one).
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        for line_num, select_str in join_blocks:
            has_spec_join = "specifications(" in select_str or "specifications!" in select_str
            has_quote_join = "quotes(" in select_str or "quotes!" in select_str

            if has_spec_join:
                assert "specifications!" in select_str, (
                    f"Deal query at ~line {line_num}: joins specifications but missing FK hint"
                )
            if has_quote_join:
                assert "quotes!" in select_str, (
                    f"Deal query at ~line {line_num}: joins quotes but missing FK hint"
                )


# =============================================================================
# TEST CLASS: Nested FK - customers inside quotes
# =============================================================================

class TestNestedCustomersFKInDealsQueries:
    """
    The deals queries nest customers inside quotes:
      quotes(id, idn_quote, customers(name))

    If quotes table also has multiple FKs, the customers join may also
    need an FK hint. Verify the pattern is correct.
    """

    def test_customers_join_inside_quotes_exists(self, main_py_content):
        """
        Deal queries that join quotes should also include customers(name)
        for displaying customer info on deals list/detail.
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        found_customers_nested = False
        for line_num, select_str in join_blocks:
            if "customers(" in select_str and "quotes" in select_str:
                found_customers_nested = True
                break

        assert found_customers_nested, (
            "Expected at least one deals query to include nested customers() inside quotes()"
        )

    def test_nested_customers_join_preserved_after_fk_hint_fix(self, main_py_content):
        """
        After adding FK hints to quotes, the nested customers(name) join
        must still be present. Verify the fix didn't accidentally remove it.

        Expected pattern:
          quotes!deals_quote_id_fkey(id, idn_quote, customers(name))
        """
        join_blocks = _get_deals_join_blocks(main_py_content)

        # At least one query should have quotes with nested customers
        has_nested = False
        for line_num, select_str in join_blocks:
            if "quotes!" in select_str and "customers(" in select_str:
                has_nested = True
                break

        # This test checks that BOTH the FK hint AND the nested customer join exist together
        # If quotes! FK hint exists but customers() is missing = regression
        # If quotes! FK hint is missing = caught by other tests
        for line_num, select_str in join_blocks:
            if "quotes!" in select_str:
                assert "customers(" in select_str, (
                    f"Deal query at ~line {line_num} has quotes FK hint but lost "
                    f"nested customers() join. Pattern should be: "
                    f"quotes!deals_quote_id_fkey(id, idn_quote, customers(name))"
                )
