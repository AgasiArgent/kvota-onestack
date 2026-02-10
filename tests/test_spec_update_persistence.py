"""
TDD Tests for Spec Update Persistence Bug: contract_id missing from update_data dict.

Root cause: The POST handler for /spec-control/{spec_id} (action="save") builds an
update_data dict (main.py ~lines 22535-22558) that includes many fields but NOT
contract_id. It also lacks auto-numbering logic when a contract is newly selected.

The creation handler at main.py ~lines 21856-21877 already has the correct pattern:
  1. Extract contract_id from kwargs
  2. Auto-generate specification_number from contract if no manual number
  3. Increment next_specification_number in customer_contracts
  4. Include contract_id in spec_data dict

The update handler needs the same pattern, with an additional guard:
  - Only increment counter if contract_id actually CHANGED (compare with existing spec)

These tests are written BEFORE the fix (TDD). They MUST FAIL now.
"""

import pytest
import re
import os

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code (no import needed, avoids sentry_sdk dep)."""
    with open(MAIN_PY) as f:
        return f.read()


def _read_update_handler_source():
    """
    Extract the POST /spec-control/{spec_id} handler source from main.py.

    This is the UPDATE handler (not the create handler). It starts at the
    @rt("/spec-control/{spec_id}") def post(...) that handles action="save".
    """
    content = _read_main_source()
    # The update handler is: @rt("/spec-control/{spec_id}") def post(session, spec_id: str, action: str = "save", ...)
    # It is distinct from the create handler which is @rt("/spec-control/create/{quote_id}")
    # and from the GET handler @rt("/spec-control/{spec_id}") def get(...)
    match = re.search(
        r'(@rt\("/spec-control/\{spec_id\}"\)\s*def post\(.*?)(?=\n@rt\(|\n# ={10,})',
        content,
        re.DOTALL
    )
    if not match:
        pytest.fail("Could not find POST /spec-control/{spec_id} handler in main.py")
    return match.group(0)


def _read_create_handler_source():
    """
    Extract the POST /spec-control/create/{quote_id} handler source for comparison.
    """
    content = _read_main_source()
    match = re.search(
        r'(@rt\("/spec-control/create/\{quote_id\}"\)\s*def post\(.*?)(?=\n@rt\(|\n# ={10,})',
        content,
        re.DOTALL
    )
    if not match:
        pytest.fail("Could not find POST /spec-control/create/{quote_id} handler in main.py")
    return match.group(0)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def update_handler_source():
    """Read the update POST handler source once per test."""
    return _read_update_handler_source()


@pytest.fixture
def create_handler_source():
    """Read the create POST handler source for comparison."""
    return _read_create_handler_source()


# ==============================================================================
# 1. contract_id in update_data dict
# ==============================================================================

class TestContractIdInUpdateData:
    """
    The update_data dict at ~lines 22535-22558 MUST include 'contract_id'.
    Currently it does NOT -- this is the primary bug.
    """

    def test_update_data_includes_contract_id_key(self, update_handler_source):
        """
        update_data dict MUST include 'contract_id' key.
        Without it, changing the contract on an existing spec is silently lost.
        """
        # Look for contract_id in the update_data dict definition
        has_contract_id = re.search(
            r'update_data\s*=\s*\{[^}]*["\']contract_id["\']',
            update_handler_source,
            re.DOTALL
        )
        assert has_contract_id, (
            "update_data dict must include 'contract_id' key. "
            "Currently missing -- contract changes on existing specs are silently lost."
        )

    def test_contract_id_value_references_variable(self, update_handler_source):
        """
        update_data['contract_id'] must reference a processed contract_id variable,
        not an inline value. The variable is set earlier for auto-numbering.
        """
        has_variable_ref = re.search(
            r'"contract_id":\s*contract_id',
            update_handler_source
        )
        assert has_variable_ref, (
            "update_data['contract_id'] must reference the processed contract_id variable, "
            "not an inline value. The variable is needed for auto-numbering comparison."
        )

    def test_contract_id_normalized_from_parameter(self, update_handler_source):
        """
        contract_id must be normalized (or None) before the update_data dict,
        just like the create handler does.
        """
        has_normalization = re.search(
            r'contract_id\s*=\s*contract_id\s+or\s+None',
            update_handler_source
        )
        assert has_normalization, (
            "contract_id must be normalized before building update_data. "
            "Expected: contract_id = contract_id or None"
        )


# ==============================================================================
# 2. Auto-numbering logic in update handler
# ==============================================================================

class TestAutoNumberingInUpdateHandler:
    """
    When contract_id is selected on update and no manual specification_number
    is provided, the handler should auto-generate the spec number from the
    contract, just like the create handler does.

    Additional requirement: Only increment the counter if contract_id actually
    CHANGED (compare with the existing spec's contract_id).
    """

    def test_auto_numbering_condition_exists(self, update_handler_source):
        """
        The update handler must have the same auto-numbering guard:
        'if contract_id and not specification_number'
        """
        has_condition = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            update_handler_source
        )
        assert has_condition, (
            "Update handler must have auto-numbering condition: "
            "'if contract_id and not specification_number'. "
            "This triggers auto-generation when a contract is selected "
            "but no manual spec number is given."
        )

    def test_auto_numbering_fetches_contract_info(self, update_handler_source):
        """
        Auto-numbering in the update handler must fetch contract_number and
        next_specification_number from customer_contracts table.
        """
        has_contract_fetch = (
            "customer_contracts" in update_handler_source
            and "contract_number" in update_handler_source
            and "next_specification_number" in update_handler_source
        )
        assert has_contract_fetch, (
            "Update handler auto-numbering must fetch contract_number and "
            "next_specification_number from customer_contracts table."
        )

    def test_auto_numbering_format_matches_create_handler(self, update_handler_source):
        """
        Auto-generated spec number format must match create handler:
        '{contract_number}-{next_spec_num}' (e.g., 'DP-001/2025-1')
        """
        has_format = re.search(
            r'f".*\{contract_num.*\}-\{next_spec_num.*\}"',
            update_handler_source
        )
        assert has_format, (
            "Auto-generated specification number in update handler must use "
            "the same format as create handler: f\"{contract_num}-{next_spec_num}\""
        )

    def test_auto_numbering_increments_counter(self, update_handler_source):
        """
        After generating the spec number, the update handler must increment
        next_specification_number in the customer_contracts table.
        """
        has_increment = re.search(
            r'\.update\(\{.*next_specification_number.*next_spec_num\s*\+\s*1',
            update_handler_source,
            re.DOTALL
        )
        assert has_increment, (
            "Update handler auto-numbering must increment next_specification_number "
            "in customer_contracts after generating the spec number."
        )

    def test_counter_only_incremented_on_contract_change(self, update_handler_source):
        """
        CRITICAL: The counter must ONLY be incremented if contract_id actually
        CHANGED from the existing spec's contract_id. Otherwise, re-saving a
        spec with the same contract would wastefully increment the counter.

        Expected pattern: compare new contract_id with existing spec's contract_id
        (e.g., 'if contract_id != existing_contract_id' or
        'if contract_id != spec.get("contract_id")')
        """
        # Look for a comparison between new and existing contract_id
        has_change_check = (
            re.search(r'contract_id\s*!=\s*(existing_contract_id|spec\.get\(["\']contract_id["\']\)|current_contract_id|old_contract_id|spec\[["\']contract_id["\']\])', update_handler_source)
            or re.search(r'(existing_contract_id|current_contract_id|old_contract_id)\s*!=\s*contract_id', update_handler_source)
            # Also accept a pattern where auto-numbering is wrapped in "if changed" guard
            or re.search(r'contract.*changed', update_handler_source, re.IGNORECASE)
        )
        assert has_change_check, (
            "Auto-numbering counter must only be incremented when contract_id "
            "actually CHANGED. The handler must compare the new contract_id with "
            "the existing spec's contract_id before incrementing. "
            "Expected: 'if contract_id != spec.get(\"contract_id\")' or equivalent."
        )


# ==============================================================================
# 3. Spec fetch must include contract_id for comparison
# ==============================================================================

class TestSpecFetchIncludesContractId:
    """
    The existing spec fetch query (spec_result) selects 'id, status, quote_id'.
    To compare contract_id changes, it must ALSO select 'contract_id'.
    """

    def test_spec_fetch_selects_contract_id(self, update_handler_source):
        """
        The spec_result query must select contract_id in addition to existing fields.
        Without it, the handler cannot compare old vs new contract_id.
        """
        # Find the spec_result select statement
        spec_select_match = re.search(
            r'spec_result\s*=\s*supabase\.table\("specifications"\)\s*\\\s*\.select\("([^"]+)"\)',
            update_handler_source
        )
        assert spec_select_match, (
            "Could not find spec_result select statement in update handler"
        )

        selected_columns = spec_select_match.group(1)
        assert "contract_id" in selected_columns, (
            f"spec_result must select 'contract_id' for comparison. "
            f"Currently selects: '{selected_columns}'. "
            f"Without contract_id, cannot detect if contract changed on save."
        )


# ==============================================================================
# 4. delivery_days persistence in update handler
# ==============================================================================

class TestDeliveryDaysPersistenceInUpdate:
    """
    Verify delivery_days is correctly handled in the update handler.
    The update handler already has delivery_days in update_data (line 22552),
    but let's verify the full pattern is correct.
    """

    def test_delivery_days_in_update_data(self, update_handler_source):
        """delivery_days must be present in update_data dict."""
        has_delivery_days = re.search(
            r'update_data\s*=\s*\{[^}]*["\']delivery_days["\']',
            update_handler_source,
            re.DOTALL
        )
        assert has_delivery_days, (
            "update_data dict must include 'delivery_days' key."
        )

    def test_delivery_days_type_in_update_data(self, update_handler_source):
        """delivery_days_type must be present in update_data dict."""
        has_delivery_days_type = re.search(
            r'update_data\s*=\s*\{[^}]*["\']delivery_days_type["\']',
            update_handler_source,
            re.DOTALL
        )
        assert has_delivery_days_type, (
            "update_data dict must include 'delivery_days_type' key."
        )


# ==============================================================================
# 5. Edge cases
# ==============================================================================

class TestEdgeCases:
    """
    Edge case tests for the update handler's contract_id handling.
    """

    def test_no_contract_does_not_trigger_auto_numbering(self, update_handler_source):
        """
        When contract_id is empty/None, auto-numbering must NOT be triggered.
        The guard 'if contract_id and not specification_number' handles this.
        """
        has_guard = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            update_handler_source
        )
        assert has_guard, (
            "Auto-numbering guard must exist: 'if contract_id and not specification_number'. "
            "This ensures no auto-numbering when contract_id is empty."
        )

    def test_manual_number_with_contract_skips_auto_numbering(self, update_handler_source):
        """
        When both contract_id and specification_number are provided,
        the manual number should be used (auto-numbering NOT triggered).
        The 'and not specification_number' part of the guard handles this.
        """
        has_not_spec_number_guard = re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            update_handler_source
        )
        assert has_not_spec_number_guard, (
            "The guard 'if contract_id and not specification_number' must exist "
            "so that manual specification_number is preserved when provided."
        )

    def test_specification_number_normalized_from_parameter(self, update_handler_source):
        """
        specification_number must be normalized (or None) from the explicit parameter
        BEFORE the auto-numbering logic, so it can be checked in the guard.
        """
        has_normalization = re.search(
            r'specification_number\s*=\s*specification_number\s+or\s+None',
            update_handler_source
        )
        assert has_normalization, (
            "specification_number must be normalized from the explicit parameter "
            "before auto-numbering logic. Expected: "
            "specification_number = specification_number or None"
        )

    def test_contract_id_or_none_normalization(self, update_handler_source):
        """
        contract_id must be normalized to None when empty string.
        Expected: 'contract_id = contract_id or None'
        """
        has_normalization = re.search(
            r'contract_id\s*=\s*contract_id\s+or\s+None',
            update_handler_source
        )
        assert has_normalization, (
            "contract_id must be normalized: contract_id or None. "
            "Empty string from form must become None for proper DB storage."
        )

    def test_auto_numbering_has_error_handling(self, update_handler_source):
        """
        Auto-numbering in update handler must have try/except like the create handler.
        If contract lookup fails, the save should still succeed.
        """
        # Look for try block around auto-numbering logic
        auto_num_pos = update_handler_source.find("contract_id and not specification_number")
        if auto_num_pos == -1:
            pytest.fail("Auto-numbering condition not found (prerequisite for this test)")

        # Check there's a try block in the vicinity (within 300 chars before)
        nearby_source = update_handler_source[max(0, auto_num_pos - 300):auto_num_pos + 1000]
        has_try = "try:" in nearby_source
        has_except = "except" in nearby_source
        assert has_try and has_except, (
            "Auto-numbering logic must be wrapped in try/except for error resilience. "
            "If contract lookup fails, the spec save should still succeed."
        )


# ==============================================================================
# 6. Parity check: update handler vs create handler
# ==============================================================================

class TestCreateUpdateParity:
    """
    The update handler should have the same contract_id handling patterns
    as the create handler. These tests verify parity.
    """

    def test_create_handler_has_contract_id_in_data_dict(self, create_handler_source):
        """
        Baseline check: confirm create handler HAS contract_id in spec_data.
        This should PASS (it already exists). If it fails, something is broken.
        """
        has_contract_id = re.search(
            r'spec_data\s*=\s*\{[^}]*["\']contract_id["\']',
            create_handler_source,
            re.DOTALL
        )
        assert has_contract_id, (
            "BASELINE BROKEN: create handler must have contract_id in spec_data. "
            "This is a prerequisite for the update handler parity fix."
        )

    def test_both_handlers_have_contract_id_in_data_dict(
        self, create_handler_source, update_handler_source
    ):
        """
        Both the create handler (spec_data) and update handler (update_data)
        must include 'contract_id' in their data dicts.
        """
        create_has = "contract_id" in re.search(
            r'spec_data\s*=\s*\{(.*?)\}',
            create_handler_source,
            re.DOTALL
        ).group(1) if re.search(r'spec_data\s*=\s*\{(.*?)\}', create_handler_source, re.DOTALL) else False

        update_has = "contract_id" in re.search(
            r'update_data\s*=\s*\{(.*?)\}',
            update_handler_source,
            re.DOTALL
        ).group(1) if re.search(r'update_data\s*=\s*\{(.*?)\}', update_handler_source, re.DOTALL) else False

        assert create_has, "create handler spec_data must include contract_id"
        assert update_has, (
            "update handler update_data must include contract_id (PARITY BUG). "
            "The create handler has it but the update handler does not."
        )

    def test_both_handlers_normalize_contract_id(
        self, create_handler_source, update_handler_source
    ):
        """
        Both handlers must normalize contract_id (or None) before data dict building.
        """
        create_normalizes = bool(re.search(
            r'contract_id\s*=\s*contract_id\s+or\s+None',
            create_handler_source
        ))
        update_normalizes = bool(re.search(
            r'contract_id\s*=\s*contract_id\s+or\s+None',
            update_handler_source
        ))

        assert create_normalizes, "create handler must normalize contract_id"
        assert update_normalizes, (
            "update handler must normalize contract_id (PARITY BUG). "
            "The create handler normalizes it but the update handler does not."
        )

    def test_both_handlers_have_auto_numbering(
        self, create_handler_source, update_handler_source
    ):
        """
        Both handlers must have auto-numbering logic for contract-based spec numbers.
        """
        create_has_auto = bool(re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            create_handler_source
        ))
        update_has_auto = bool(re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            update_handler_source
        ))

        assert create_has_auto, "create handler must have auto-numbering condition"
        assert update_has_auto, (
            "update handler must have auto-numbering condition (PARITY BUG). "
            "The create handler auto-generates spec numbers from contracts "
            "but the update handler does not."
        )


# ==============================================================================
# 7. Verify current code has the bug (these MUST FAIL now, PASS after fix)
# ==============================================================================

class TestCurrentCodeHasBug:
    """
    These tests assert the FIX IS present. They FAIL now (proving the bug exists)
    and will PASS after the fix is applied.
    """

    def test_update_data_currently_missing_contract_id(self):
        """
        The update_data dict currently does NOT contain contract_id.
        This test asserts it IS present, so it FAILS now (confirming the bug).
        """
        source = _read_update_handler_source()
        update_data_match = re.search(
            r'update_data\s*=\s*\{(.*?)\}',
            source,
            re.DOTALL
        )
        assert update_data_match, "Could not find update_data dict in update handler"
        update_data_block = update_data_match.group(1)

        assert "contract_id" in update_data_block, (
            "BUG CONFIRMED: update_data dict is missing 'contract_id'. "
            "This means selecting a contract on an existing spec is silently ignored."
        )

    def test_update_handler_currently_lacks_auto_numbering(self):
        """
        The update handler currently has NO auto-numbering logic.
        This test asserts it IS present, so it FAILS now.
        """
        source = _read_update_handler_source()
        has_auto_numbering = bool(re.search(
            r'if\s+contract_id\s+and\s+not\s+specification_number',
            source
        ))
        assert has_auto_numbering, (
            "BUG CONFIRMED: update handler lacks auto-numbering logic. "
            "When contract is selected on edit, spec number is not auto-generated."
        )

    def test_update_handler_currently_has_contract_normalization(self):
        """
        The update handler must normalize contract_id from the explicit parameter.
        """
        source = _read_update_handler_source()
        has_normalization = bool(re.search(
            r'contract_id\s*=\s*contract_id\s+or\s+None',
            source
        ))
        assert has_normalization, (
            "BUG CONFIRMED: update handler does not normalize contract_id. "
            "The form field value is completely ignored on save."
        )

    def test_spec_fetch_currently_lacks_contract_id(self):
        """
        The spec_result select currently only fetches 'id, status, quote_id'.
        It does NOT fetch contract_id, which is needed for change detection.
        This test asserts contract_id IS in the select, so it FAILS now.
        """
        source = _read_update_handler_source()
        spec_select_match = re.search(
            r'spec_result\s*=\s*supabase\.table\("specifications"\)\s*\\\s*\.select\("([^"]+)"\)',
            source
        )
        assert spec_select_match, (
            "Could not find spec_result select statement"
        )

        selected_columns = spec_select_match.group(1)
        assert "contract_id" in selected_columns, (
            f"BUG CONFIRMED: spec_result select is '{selected_columns}' -- "
            "missing 'contract_id'. Cannot detect contract changes without it."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
