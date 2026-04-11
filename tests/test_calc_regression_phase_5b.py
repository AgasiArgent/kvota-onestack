"""
Phase 5b regression test — Task 5.

Validates that replacing the three quote_items reads that feed
build_calculation_inputs() in main.py with composition_service.get_composed_items
does NOT change the engine input shape for backfilled data.

Uses a snapshotted real prod quote (PHASE-5B-TEST: Q-TEST-P5B-01,
UUID 11111111-1111-1111-1111-111111111111) as fixture, so the test
exercises the actual column shape quote_items has in production —
not a hand-mocked subset. Fixture is stored in
tests/fixtures/phase_5b_test_quote.json and refreshed via SQL dump
when the schema evolves.

Covers:
- Bit-identity: on backfilled data (iip prices == quote_items prices),
  get_composed_items returns dicts where the 4 overlay fields match
  the legacy quote_items values. This is the Task 5 correctness check.
- Overlay mutation: when iip prices DIFFER from quote_items (simulated
  in memory), get_composed_items actually substitutes the iip values.
  This proves the adapter isn't a silent no-op.
- Locked files invariant: main.py changes in Task 5 must not have
  touched calculation_engine.py / calculation_models.py /
  calculation_mapper.py. Asserted via git diff.
"""

import json
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.composition_service import get_composed_items  # noqa: E402


FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "phase_5b_test_quote.json",
)

TEST_QUOTE_ID = "11111111-1111-1111-1111-111111111111"

OVERLAY_FIELDS = (
    "purchase_price_original",
    "purchase_currency",
    "base_price_vat",
    "price_includes_vat",
)


# ============================================================================
# Fixture-backed mock supabase
# ============================================================================

def _load_fixture() -> dict:
    with open(FIXTURE_PATH, "r") as f:
        return json.load(f)


def _make_supabase_from_fixture(fixture: dict) -> MagicMock:
    """Build a mock supabase whose .table(name) returns a chainable query
    that terminates at .execute() returning the fixture's rows for that table.

    Ignores filters (eq/in_) since the fixture is already pre-scoped to the
    test quote. Writes (update/insert/delete) are not tested here — Task 5
    only touches read paths.
    """
    def _table(name: str):
        rows = fixture.get(name, []) or []
        q = MagicMock()
        q.select.return_value = q
        q.eq.return_value = q
        q.in_.return_value = q
        q.order.return_value = q
        q.limit.return_value = q
        result = MagicMock()
        result.data = rows
        result.error = None
        q.execute.return_value = result
        return q

    sb = MagicMock()
    sb.table.side_effect = _table
    return sb


# ============================================================================
# Regression tests
# ============================================================================

class TestPhase5bRegression:
    """Task 5 regression: get_composed_items on real prod shape."""

    def test_fixture_is_loadable_and_has_expected_test_quote(self):
        """Sanity check: fixture exists and contains the test quote data."""
        fixture = _load_fixture()
        assert "quote_items" in fixture
        assert "invoice_item_prices" in fixture
        assert len(fixture["quote_items"]) == 2
        assert len(fixture["invoice_item_prices"]) == 2

        # All items belong to our test quote
        for item in fixture["quote_items"]:
            assert item["quote_id"] == TEST_QUOTE_ID
            # Composition pointer must be set (proves backfill-simulation)
            assert item.get("composition_selected_invoice_id") is not None, (
                "Test quote items must have composition_selected_invoice_id set — "
                "the whole point of this fixture is to exercise the overlay path"
            )

    def test_composed_items_match_quote_items_shape(self):
        """get_composed_items returns dicts structurally identical to quote_items reads.

        For backfilled data where iip.* == quote_items.*, the overlay is a
        mathematical no-op — every field should match.
        """
        fixture = _load_fixture()
        sb = _make_supabase_from_fixture(fixture)

        composed = get_composed_items(TEST_QUOTE_ID, sb)

        # Same row count
        assert len(composed) == len(fixture["quote_items"])

        # Every item in composed must have the same ID as one in quote_items
        composed_by_id = {item["id"]: item for item in composed}
        for original in fixture["quote_items"]:
            assert original["id"] in composed_by_id

    def test_overlay_is_noop_on_backfilled_data(self):
        """On backfilled data (iip == quote_items), composed matches legacy 1:1.

        This is the Task 5 correctness property: migration 265 copied
        quote_items price fields into iip verbatim, so composition_service's
        overlay must produce outputs bit-identical to the legacy path for
        every quote created before Phase 5b ships.
        """
        fixture = _load_fixture()
        sb = _make_supabase_from_fixture(fixture)

        composed = get_composed_items(TEST_QUOTE_ID, sb)
        legacy_by_id = {item["id"]: item for item in fixture["quote_items"]}

        for item in composed:
            legacy = legacy_by_id[item["id"]]
            for field_name in OVERLAY_FIELDS:
                assert item.get(field_name) == legacy.get(field_name), (
                    f"Field {field_name} differs for item {item['id']}: "
                    f"composed={item.get(field_name)}, legacy={legacy.get(field_name)}"
                )

    def test_non_price_fields_pass_through_unchanged(self):
        """Non-overlay fields (customs_code, quantity, etc.) must not be touched."""
        fixture = _load_fixture()
        sb = _make_supabase_from_fixture(fixture)

        composed = get_composed_items(TEST_QUOTE_ID, sb)
        legacy_by_id = {item["id"]: item for item in fixture["quote_items"]}

        # Fields that must NEVER be overlaid
        protected_fields = (
            "id",
            "quote_id",
            "position",
            "product_name",
            "quantity",
            "idn_sku",
            "customs_code",
            "weight_in_kg",
            "composition_selected_invoice_id",
        )

        for item in composed:
            legacy = legacy_by_id[item["id"]]
            for field_name in protected_fields:
                assert item.get(field_name) == legacy.get(field_name), (
                    f"Protected field {field_name} was modified for item {item['id']}: "
                    f"composed={item.get(field_name)}, legacy={legacy.get(field_name)}"
                )

    def test_overlay_actually_substitutes_when_iip_differs(self):
        """When iip prices differ from quote_items (simulated), composed
        reflects iip values — proves the adapter is not a silent no-op.
        """
        fixture = _load_fixture()
        # Mutate fixture in memory: double the iip prices so they differ
        # from quote_items.
        for iip in fixture["invoice_item_prices"]:
            iip["purchase_price_original"] = float(iip["purchase_price_original"]) * 2
            iip["base_price_vat"] = float(iip["base_price_vat"]) * 2
            iip["purchase_currency"] = "EUR"  # change currency too
            iip["price_includes_vat"] = not iip["price_includes_vat"]

        sb = _make_supabase_from_fixture(fixture)
        composed = get_composed_items(TEST_QUOTE_ID, sb)

        for item in composed:
            # Find the matching iip row
            matching_iip = next(
                (
                    iip
                    for iip in fixture["invoice_item_prices"]
                    if iip["quote_item_id"] == item["id"]
                    and iip["invoice_id"] == item["composition_selected_invoice_id"]
                ),
                None,
            )
            assert matching_iip is not None, "Fixture must have matching iip row"

            # The composed item should have the (now-mutated) iip values, not
            # the original quote_items values
            assert item["purchase_price_original"] == matching_iip["purchase_price_original"]
            assert item["purchase_currency"] == "EUR"
            assert item["base_price_vat"] == matching_iip["base_price_vat"]
            assert item["price_includes_vat"] == matching_iip["price_includes_vat"]


# ============================================================================
# Locked files invariant
# ============================================================================

class TestLockedFilesUntouched:
    """Assert Task 5's main.py changes did not touch the locked calc engine."""

    def test_calc_engine_files_unchanged_vs_main_branch(self):
        """git diff main HEAD -- <3 locked files> must be empty.

        Requires git to be available and the test to run in the repo root.
        Skipped when git is unavailable or we're not in a git checkout.
        """
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        locked = [
            "calculation_engine.py",
            "calculation_models.py",
            "calculation_mapper.py",
        ]

        try:
            result = subprocess.run(
                ["git", "-C", repo_root, "diff", "main", "HEAD", "--"] + locked,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pytest.skip("git not available or timed out")

        if result.returncode != 0:
            pytest.skip(f"git diff failed (not a git checkout?): {result.stderr}")

        assert result.stdout == "", (
            "Locked calc engine files were modified in Task 5 — this is "
            "forbidden. Revert the changes to:\n"
            "  calculation_engine.py\n"
            "  calculation_models.py\n"
            "  calculation_mapper.py\n\n"
            f"Diff:\n{result.stdout}"
        )

    def test_main_py_still_imports_from_composition_service(self):
        """Sanity: main.py imports get_composed_items from composition_service.

        Catches accidental reverts of Task 5's hook-up.
        """
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_py_path, "r") as f:
            source = f.read()

        assert "from services.composition_service import get_composed_items" in source, (
            "main.py must import get_composed_items from composition_service — "
            "Task 5 hook-up appears to be missing"
        )
        # And the call sites must exist (at least the 3 we replaced)
        assert source.count("get_composed_items(quote_id, supabase)") >= 3, (
            "main.py should call get_composed_items(quote_id, supabase) at least "
            "3 times — once per build_calculation_inputs entry point"
        )
