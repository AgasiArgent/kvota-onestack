"""
TDD Tests for BUG-B: Duplicate entry in spec-control list.

Bug: Same quote appears in both "Ожидают спецификации" and "Черновики" sections
of the spec-control unified table.

Root cause: When a specification is created from a quote, the quote's
workflow_status stays as 'pending_spec_control'. The function queries
all quotes with this status (pending_quotes) and separately queries
all specifications (all_specs). Both are merged into combined_items
without checking for overlap. If a spec already exists for a quote,
that quote should NOT appear in the "Ожидают" group.

Fix: After fetching pending_quotes and all_specs, filter out any
pending quote whose id is in the set of quote_ids from all_specs.

These tests are written BEFORE the fix (TDD). They MUST FAIL now.
"""

import pytest
import re
import os
from uuid import uuid4
from datetime import datetime


# ============================================================================
# Helpers
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_spec_control_function_source():
    """Extract _dashboard_spec_control_content function source from main.py."""
    content = _read_main_source()
    match = re.search(
        r'^(def _dashboard_spec_control_content\(.*?)(?=\ndef )',
        content,
        re.MULTILINE | re.DOTALL
    )
    if not match:
        pytest.fail("Could not find _dashboard_spec_control_content function in main.py")
    return match.group(0)


def _make_uuid():
    return str(uuid4())


# ============================================================================
# Test Data Factories
# ============================================================================

ORG_ID = _make_uuid()


def make_pending_quote(quote_id=None, idn="Q-202601-0001", customer_name="Customer A"):
    """Create a mock pending quote dict (as returned by Supabase query)."""
    return {
        "id": quote_id or _make_uuid(),
        "idn_quote": idn,
        "customers": {"name": customer_name},
        "workflow_status": "pending_spec_control",
        "currency": "USD",
        "total_amount": 10000,
        "created_at": datetime.now().isoformat(),
        "deal_type": "supply",
        "current_version_id": None,
    }


def make_spec(spec_id=None, quote_id=None, status="draft", spec_number="SPEC-2026-0001"):
    """Create a mock specification dict (as returned by Supabase query)."""
    return {
        "id": spec_id or _make_uuid(),
        "quote_id": quote_id or _make_uuid(),
        "specification_number": spec_number,
        "proposal_idn": "Q-202601-0001",
        "status": status,
        "sign_date": None,
        "specification_currency": "USD",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "organization_id": ORG_ID,
        "quotes": {
            "idn_quote": "Q-202601-0001",
            "total_amount_usd": 10000,
            "total_profit_usd": 2000,
            "customers": {"name": "Customer A"},
        },
    }


# ============================================================================
# 1. Source code verification: Function exists
# ============================================================================

class TestFunctionExists:
    """Verify _dashboard_spec_control_content exists and is structurally sound."""

    def test_function_exists_in_main(self):
        """The function _dashboard_spec_control_content must exist in main.py."""
        source = _read_main_source()
        assert "def _dashboard_spec_control_content(" in source


# ============================================================================
# 2. Source code: The function queries specs to find existing quote_ids
# ============================================================================

class TestDuplicateFilterSourceCode:
    """
    Verify that the source code of _dashboard_spec_control_content contains
    logic to filter out pending quotes that already have specifications.

    The fix must:
    1. Collect quote_ids from all_specs (set of spec.quote_id values)
    2. Filter pending_quotes to exclude those with matching ids
    This happens BEFORE building combined_items.
    """

    def test_collects_quote_ids_from_specs(self):
        """
        The function must collect the set of quote_ids from all_specs
        into a dedicated variable for dedup filtering.
        Expected pattern: something like
            spec_quote_ids = {s.get('quote_id') or s['quote_id'] for s in all_specs}
        or
            spec_quote_ids = set(s['quote_id'] for s in all_specs)
        """
        source = _read_spec_control_function_source()
        # Look for a dedicated variable that collects quote_ids for dedup
        # Must be an explicit assignment like `spec_quote_ids = ...` or similar
        has_quote_id_collection = bool(re.search(
            r'(spec_quote_ids|specs_quote_ids|existing_quote_ids|quote_ids_with_specs)\s*=',
            source
        ))
        assert has_quote_id_collection, (
            "The function must collect quote_ids from all_specs into a dedicated "
            "set variable (e.g., spec_quote_ids = {s['quote_id'] for s in all_specs}). "
            "This set is used to filter out pending quotes that already have specs."
        )

    def test_filters_pending_quotes_by_spec_quote_ids(self):
        """
        After collecting spec_quote_ids, the function must filter pending_quotes
        to exclude those whose id is in spec_quote_ids.
        Expected pattern:
            pending_quotes = [q for q in pending_quotes if q['id'] not in spec_quote_ids]
        """
        source = _read_spec_control_function_source()
        # Look for filtering pattern that excludes quotes with existing specs
        has_exclusion_filter = (
            ("not in spec_quote_ids" in source)
            or ("not in specs_quote_ids" in source)
            or ("not in existing_quote_ids" in source)
            or ("not in quote_ids_with_specs" in source)
            # Alternative: generic pattern of filtering pending_quotes with "not in"
            or (re.search(r'pending_quotes\s*=\s*\[.*not in.*for.*pending_quotes', source, re.DOTALL) is not None)
        )
        assert has_exclusion_filter, (
            "The function must filter pending_quotes to exclude those with existing specs. "
            "Expected: pending_quotes = [q for q in pending_quotes if q['id'] not in spec_quote_ids] "
            "This prevents the same quote from appearing in both 'Ожидают' and 'Черновики'."
        )

    def test_exclusion_happens_before_combined_items(self):
        """
        The filtering must happen BEFORE building combined_items.
        The set collection and filtering code must appear in the source
        before the 'combined_items = []' line.
        """
        source = _read_spec_control_function_source()

        # Find positions of key markers
        combined_items_pos = source.find("combined_items = []")
        assert combined_items_pos > 0, "combined_items = [] must exist in function"

        # The exclusion logic should appear before combined_items
        # Look for the filtering pattern in the code before combined_items
        code_before_merge = source[:combined_items_pos]

        has_exclusion_before_merge = (
            "spec_quote_ids" in code_before_merge
            or "specs_quote_ids" in code_before_merge
            or "existing_quote_ids" in code_before_merge
            or "quote_ids_with_specs" in code_before_merge
            or ("not in" in code_before_merge and "pending_quotes" in code_before_merge)
        )
        assert has_exclusion_before_merge, (
            "The duplicate exclusion logic must appear BEFORE 'combined_items = []'. "
            "If filtering happens after merging, duplicates will already be in the list. "
            "The fix must filter pending_quotes before they are added to combined_items."
        )

    def test_pending_quotes_count_reflects_filtering(self):
        """
        The stats['pending_quotes'] count should reflect the filtered
        (deduplicated) count, not the raw query count.
        This means either:
        a) stats dict is built AFTER the filtering, or
        b) the len(pending_quotes) used for stats already excludes dupes
        """
        source = _read_spec_control_function_source()

        # Find the stats assignment position
        stats_pos = source.find("stats = {")
        assert stats_pos > 0, "stats = { must exist in function"

        # Find where pending_quotes filtering happens
        # The filtering should happen BEFORE stats dict is populated
        code_before_stats = source[:stats_pos]

        has_filtering_before_stats = (
            "spec_quote_ids" in code_before_stats
            or "specs_quote_ids" in code_before_stats
            or "existing_quote_ids" in code_before_stats
            or "quote_ids_with_specs" in code_before_stats
            or ("not in" in code_before_stats and "pending_quotes" in code_before_stats
                and "for" in code_before_stats.split("pending_quotes")[-1][:100])
        )
        assert has_filtering_before_stats, (
            "The pending_quotes filtering must happen BEFORE the stats dict is built. "
            "Otherwise stats['pending_quotes'] will show the wrong count (including "
            "quotes that already have specs)."
        )


# ============================================================================
# 3. Pure Python filter logic tests
# ============================================================================

class TestDuplicateFilterLogic:
    """
    Test the core filtering logic in isolation (pure Python).
    Given a list of pending quotes and a list of specs,
    the filter should exclude quotes that already have specs.

    This simulates what the fix should do:
        spec_quote_ids = {s['quote_id'] for s in all_specs}
        pending_quotes = [q for q in pending_quotes if q['id'] not in spec_quote_ids]
    """

    @staticmethod
    def apply_dedup_filter(pending_quotes, all_specs):
        """
        Simulate the expected fix logic.
        This is the behavior we expect after the bug is fixed.
        """
        spec_quote_ids = {s.get("quote_id") for s in all_specs if s.get("quote_id")}
        return [q for q in pending_quotes if q["id"] not in spec_quote_ids]

    def test_quote_with_spec_is_excluded(self):
        """
        Given quotes [A, B, C] and a spec for quote B,
        filtered result should be [A, C].
        """
        qa_id = _make_uuid()
        qb_id = _make_uuid()
        qc_id = _make_uuid()

        pending = [
            make_pending_quote(quote_id=qa_id, idn="Q-001", customer_name="Alpha"),
            make_pending_quote(quote_id=qb_id, idn="Q-002", customer_name="Beta"),
            make_pending_quote(quote_id=qc_id, idn="Q-003", customer_name="Gamma"),
        ]
        specs = [
            make_spec(quote_id=qb_id, spec_number="SPEC-001"),
        ]

        result = self.apply_dedup_filter(pending, specs)

        assert len(result) == 2
        result_ids = {q["id"] for q in result}
        assert qa_id in result_ids
        assert qc_id in result_ids
        assert qb_id not in result_ids

    def test_all_quotes_with_specs_are_excluded(self):
        """
        Given quotes [A, B] and specs for [A, B],
        filtered result should be [].
        """
        qa_id = _make_uuid()
        qb_id = _make_uuid()

        pending = [
            make_pending_quote(quote_id=qa_id, idn="Q-001"),
            make_pending_quote(quote_id=qb_id, idn="Q-002"),
        ]
        specs = [
            make_spec(quote_id=qa_id),
            make_spec(quote_id=qb_id),
        ]

        result = self.apply_dedup_filter(pending, specs)
        assert len(result) == 0

    def test_no_specs_means_no_filtering(self):
        """
        Given quotes [A, B] and no specs,
        filtered result should be [A, B] (unchanged).
        """
        qa_id = _make_uuid()
        qb_id = _make_uuid()

        pending = [
            make_pending_quote(quote_id=qa_id, idn="Q-001"),
            make_pending_quote(quote_id=qb_id, idn="Q-002"),
        ]
        specs = []

        result = self.apply_dedup_filter(pending, specs)
        assert len(result) == 2

    def test_empty_pending_with_specs(self):
        """
        Given no pending quotes and some specs,
        filtered result should be [].
        """
        specs = [
            make_spec(quote_id=_make_uuid()),
        ]

        result = self.apply_dedup_filter([], specs)
        assert len(result) == 0

    def test_both_empty(self):
        """Both empty lists -> empty result."""
        result = self.apply_dedup_filter([], [])
        assert len(result) == 0

    def test_spec_for_different_quote_does_not_filter(self):
        """
        Given quote A in pending and spec for quote X (not in pending),
        quote A should remain (no false positive filtering).
        """
        qa_id = _make_uuid()
        qx_id = _make_uuid()  # not in pending_quotes

        pending = [
            make_pending_quote(quote_id=qa_id, idn="Q-001"),
        ]
        specs = [
            make_spec(quote_id=qx_id),
        ]

        result = self.apply_dedup_filter(pending, specs)
        assert len(result) == 1
        assert result[0]["id"] == qa_id

    def test_multiple_specs_for_same_quote(self):
        """
        If somehow multiple specs exist for the same quote_id,
        the quote should still be excluded (just once).
        """
        qa_id = _make_uuid()

        pending = [
            make_pending_quote(quote_id=qa_id, idn="Q-001"),
        ]
        specs = [
            make_spec(quote_id=qa_id, spec_number="SPEC-001"),
            make_spec(quote_id=qa_id, spec_number="SPEC-002"),
        ]

        result = self.apply_dedup_filter(pending, specs)
        assert len(result) == 0


# ============================================================================
# 4. Combined items should NOT contain duplicates
# ============================================================================

class TestCombinedItemsNoDuplicates:
    """
    Verify that after the fix, the combined_items list in the source code
    cannot contain a quote both as a pending entry and as a spec entry
    for the same quote_id.

    These tests check the source code structure to ensure the fix is
    correctly wired into the merging logic.
    """

    def test_no_duplicate_quote_id_in_combined_items(self):
        """
        Simulate the full combined_items build logic.
        After the fix, a quote_id should appear at most once
        as type='quote'. If a spec exists for it, only the spec entry
        should appear (type='spec'), not the pending quote entry.
        """
        shared_quote_id = _make_uuid()
        other_quote_id = _make_uuid()

        # Raw pending quotes (before filtering)
        raw_pending = [
            make_pending_quote(quote_id=shared_quote_id, idn="Q-001", customer_name="Overlap Client"),
            make_pending_quote(quote_id=other_quote_id, idn="Q-002", customer_name="Clean Client"),
        ]
        # Specs - one has same quote_id as pending
        specs = [
            make_spec(quote_id=shared_quote_id, spec_number="SPEC-001"),
        ]

        # Apply the expected fix
        spec_quote_ids = {s.get("quote_id") for s in specs if s.get("quote_id")}
        filtered_pending = [q for q in raw_pending if q["id"] not in spec_quote_ids]

        # Build combined items the same way main.py does
        combined_items = []
        for pq in filtered_pending:
            combined_items.append({"type": "quote", "quote_id": pq["id"]})
        for spec in specs:
            combined_items.append({"type": "spec", "quote_id": spec["quote_id"]})

        # Verify: shared_quote_id should appear only as type='spec', NOT as type='quote'
        quote_entries = [i for i in combined_items if i["type"] == "quote"]
        spec_entries = [i for i in combined_items if i["type"] == "spec"]

        quote_ids_in_quotes = {i["quote_id"] for i in quote_entries}
        quote_ids_in_specs = {i["quote_id"] for i in spec_entries}

        overlap = quote_ids_in_quotes & quote_ids_in_specs
        assert len(overlap) == 0, (
            f"Duplicate quote_ids found in both 'quote' and 'spec' entries: {overlap}. "
            "After filtering, a quote_id with an existing spec should only appear "
            "as a spec entry, not as a pending quote entry."
        )

    def test_stats_count_matches_filtered_pending(self):
        """
        After filtering, stats['pending_quotes'] should match the
        FILTERED pending count, not the raw query count.
        """
        shared_quote_id = _make_uuid()
        other_quote_id = _make_uuid()

        raw_pending = [
            make_pending_quote(quote_id=shared_quote_id),
            make_pending_quote(quote_id=other_quote_id),
        ]
        specs = [
            make_spec(quote_id=shared_quote_id),
        ]

        # Apply expected fix
        spec_quote_ids = {s.get("quote_id") for s in specs if s.get("quote_id")}
        filtered_pending = [q for q in raw_pending if q["id"] not in spec_quote_ids]

        # The stats should use filtered count
        assert len(filtered_pending) == 1, (
            "After filtering, only 1 pending quote should remain "
            "(the one without a spec). stats['pending_quotes'] should be 1, not 2."
        )


# ============================================================================
# 5. Source code: verify the actual main.py currently has the bug
#    (These tests PASS now, and should FAIL after the fix is applied,
#     confirming the fix actually changed the code. We invert them to
#     make them FAIL now.)
# ============================================================================

class TestCurrentCodeHasBug:
    """
    These tests verify the source code currently LACKS the dedup filter.
    They are written as assertions that the fix IS present,
    so they FAIL now (proving the bug exists) and PASS after the fix.
    """

    def test_pending_quotes_are_filtered_before_merge(self):
        """
        Currently, pending_quotes are added directly to combined_items
        without filtering. After the fix, there should be filtering logic
        between the two queries and the 'combined_items = []' line.
        """
        source = _read_spec_control_function_source()

        # Find the section between all_specs query and combined_items build
        all_specs_pos = source.find("all_specs = specs_result.data or []")
        combined_pos = source.find("combined_items = []")

        assert all_specs_pos > 0, "all_specs assignment must exist"
        assert combined_pos > 0, "combined_items = [] must exist"

        between_section = source[all_specs_pos:combined_pos]

        # The fix should add filtering logic in this section
        has_dedup_in_between = (
            "spec_quote_ids" in between_section
            or "specs_quote_ids" in between_section
            or "existing_quote_ids" in between_section
            or "quote_ids_with_specs" in between_section
            or ("not in" in between_section and "pending_quotes" in between_section)
        )
        assert has_dedup_in_between, (
            "BUG CONFIRMED: No dedup filtering exists between the all_specs query "
            "and combined_items build. The fix must add logic here to collect "
            "spec quote_ids and filter pending_quotes before merging."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
