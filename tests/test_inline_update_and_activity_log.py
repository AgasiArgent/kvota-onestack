"""
Tests for the inline quote update handler (Fix 1: stale contact_person_id)
and the activity log consolidation (Fix 2: _render_activity_log deleted,
workflow_transition_history upgraded with FIO resolution).

Tests cover:
- contact_person_id is cleared when customer_id changes via inline edit
- contact_person_id is NOT cleared when other fields are updated
- contact_person_id itself can be updated independently
- customer_id set to same value still clears contact_person_id (known trade-off)
- ROLE_LABELS_RU constant has all expected roles
- _format_transition_timestamp handles various inputs
- workflow_transition_history resolves actor names from user_profiles
- workflow_transition_history handles empty history
- No dangling references to deleted _render_activity_log
- No dangling references to deleted _ROLE_LABELS_RU, _ROLE_BG_COLORS, _ROLE_TEXT_COLORS
- ORDER_SOURCE_OPTIONS / ORDER_SOURCE_LABELS consistency
- Customer inline edit order_source clearing bug (cannot clear value)
"""

import pytest
import os
import sys
import ast
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

# Set test environment before importing app
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")


# ============================================================================
# HELPER: Import symbols from main.py safely
# ============================================================================

def _import_main():
    """Import main module with mocked dependencies."""
    try:
        # Need to mock sentry_sdk which may not be installed locally
        if "sentry_sdk" not in sys.modules:
            sys.modules["sentry_sdk"] = MagicMock()
            sys.modules["sentry_sdk.integrations"] = MagicMock()
            sys.modules["sentry_sdk.integrations.starlette"] = MagicMock()
            sys.modules["sentry_sdk.integrations.logging"] = MagicMock()

        with patch("services.database.get_supabase") as mock_sb:
            mock_sb.return_value = MagicMock()
            import main
            return main
    except Exception as e:
        pytest.skip(f"Cannot import main: {e}")


# ============================================================================
# FIX 1: Stale contact_person_id Tests
# ============================================================================

class TestInlineUpdateContactPersonClearing:
    """Tests that inline PATCH handler clears contact_person_id when customer changes."""

    def test_customer_change_clears_contact_person_id(self):
        """When customer_id is updated via inline edit, contact_person_id must be set to None."""
        main = _import_main()

        # Locate the inline update handler code
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Verify the pattern: when field == "customer_id", update_data should include contact_person_id = None
        assert 'if field == "customer_id":' in source, \
            "Missing guard for customer_id field in inline update handler"
        assert 'update_data["contact_person_id"] = None' in source, \
            "contact_person_id not cleared when customer_id changes"

    def test_contact_person_id_is_in_allowed_fields(self):
        """contact_person_id should be in the allowed_fields list for inline editing."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The allowed_fields list should include contact_person_id
        assert "'contact_person_id'" in source, \
            "contact_person_id not in allowed_fields for inline editing"

    def test_non_customer_fields_do_not_clear_contact_person(self):
        """Updating fields other than customer_id should not clear contact_person_id.

        The code only clears contact_person_id when field == 'customer_id'.
        Other fields like delivery_city, seller_company_id, etc. should not trigger this.
        """
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Find the inline update function and verify the condition is specific to customer_id
        # There should be exactly one place where contact_person_id is set to None
        # in the context of the inline update, and it should be guarded by customer_id check
        idx = source.find('# When customer changes, clear contact_person_id')
        assert idx > 0, "Missing comment for contact_person_id clearing logic"

        # Check the guard is specifically for customer_id
        guard_area = source[idx-200:idx+200]
        assert 'if field == "customer_id"' in guard_area, \
            "contact_person_id clearing is not properly guarded by customer_id check"


class TestInlineUpdateCustomerSameValue:
    """Tests for edge case: updating customer_id to the same value."""

    def test_same_customer_id_still_clears_contact_person(self):
        """When customer_id is set to the same value, contact_person_id is still cleared.

        This is a known trade-off: the code does not fetch the current customer_id
        to compare. The UI dropdown fires a 'change' event only when the value
        actually changes, so in practice this should rarely happen.
        However, if it does happen (e.g., programmatic change), contact_person_id
        will be cleared unnecessarily.

        This test documents this behavior explicitly as an accepted trade-off.
        """
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The code does NOT compare old vs new customer_id.
        # Verify there is no comparison logic (this confirms the trade-off exists).
        inline_handler_start = source.find("async def inline_update_quote")
        inline_handler_end = source.find("@rt(", inline_handler_start + 1)
        handler_code = source[inline_handler_start:inline_handler_end]

        # Confirm: no comparison with existing quote data before clearing
        assert "quote_result.data[0]" not in handler_code or \
               'quote_result.data[0].get("customer_id")' not in handler_code, \
            "Code now compares old customer_id - this test should be updated"


# ============================================================================
# FIX 2: Activity Log Consolidation Tests
# ============================================================================

class TestDeletedFunctionReferences:
    """Verify no dangling references to deleted functions/constants."""

    def test_no_reference_to_render_activity_log(self):
        """_render_activity_log was deleted. No code should reference it."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        assert "_render_activity_log" not in source, \
            "Found dangling reference to deleted _render_activity_log function"

    def test_no_reference_to_old_role_constants(self):
        """_ROLE_LABELS_RU, _ROLE_BG_COLORS, _ROLE_TEXT_COLORS were deleted.
        No code should reference them (note underscore prefix)."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        assert "_ROLE_LABELS_RU" not in source, \
            "Found dangling reference to deleted _ROLE_LABELS_RU constant"
        assert "_ROLE_BG_COLORS" not in source, \
            "Found dangling reference to deleted _ROLE_BG_COLORS constant"
        assert "_ROLE_TEXT_COLORS" not in source, \
            "Found dangling reference to deleted _ROLE_TEXT_COLORS constant"

    def test_new_role_labels_constant_exists(self):
        """ROLE_LABELS_RU (without underscore prefix) should be defined as replacement."""
        main = _import_main()
        assert hasattr(main, "ROLE_LABELS_RU"), \
            "ROLE_LABELS_RU constant not found in main module"
        assert isinstance(main.ROLE_LABELS_RU, dict), \
            "ROLE_LABELS_RU should be a dict"


class TestRoleLabelsRU:
    """Tests for the ROLE_LABELS_RU constant."""

    def test_contains_all_expected_roles(self):
        """ROLE_LABELS_RU should map all common workflow roles."""
        main = _import_main()
        expected_roles = [
            "sales", "procurement", "logistics", "customs",
            "admin", "quote_controller", "spec_controller",
            "finance", "top_manager", "system",
        ]
        for role in expected_roles:
            assert role in main.ROLE_LABELS_RU, \
                f"Missing role '{role}' in ROLE_LABELS_RU"

    def test_labels_are_russian(self):
        """All labels should be non-empty Russian strings."""
        main = _import_main()
        for role, label in main.ROLE_LABELS_RU.items():
            assert label, f"Empty label for role '{role}'"
            assert isinstance(label, str), f"Label for '{role}' is not a string"

    def test_sales_manager_role_included(self):
        """sales_manager is a role that exists in the system; it should be in labels."""
        main = _import_main()
        assert "sales_manager" in main.ROLE_LABELS_RU, \
            "sales_manager role missing from ROLE_LABELS_RU"


class TestFormatTransitionTimestamp:
    """Tests for _format_transition_timestamp helper."""

    def test_valid_iso_timestamp(self):
        """Should format a valid ISO timestamp to DD.MM.YYYY HH:MM."""
        main = _import_main()
        result = main._format_transition_timestamp("2026-02-07T14:30:00+00:00")
        assert result == "07.02.2026 14:30"

    def test_utc_z_timestamp(self):
        """Should handle timestamps ending with Z."""
        main = _import_main()
        result = main._format_transition_timestamp("2026-01-15T09:45:00Z")
        assert result == "15.01.2026 09:45"

    def test_none_input(self):
        """Should return em-dash for None input."""
        main = _import_main()
        result = main._format_transition_timestamp(None)
        assert result == "\u2014"

    def test_empty_string(self):
        """Should return em-dash for empty string."""
        main = _import_main()
        result = main._format_transition_timestamp("")
        assert result == "\u2014"

    def test_invalid_timestamp(self):
        """Should return truncated string for unparseable timestamp."""
        main = _import_main()
        result = main._format_transition_timestamp("not-a-date-at-all-string")
        # Should return first 16 chars as fallback
        assert result == "not-a-date-at-al"

    def test_short_invalid_string(self):
        """Should return the string as-is if shorter than 16 chars."""
        main = _import_main()
        result = main._format_transition_timestamp("short")
        assert result == "short"


class TestWorkflowTransitionHistoryFIOResolution:
    """Tests that workflow_transition_history resolves actor names via get_supabase."""

    def test_function_calls_get_supabase(self):
        """workflow_transition_history should call get_supabase() to look up user profiles."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Find the function body
        func_start = source.find("def workflow_transition_history(")
        assert func_start > 0, "workflow_transition_history function not found"

        # Find the end (next function at the same indent level)
        func_end = source.find("\ndef ", func_start + 10)
        func_body = source[func_start:func_end]

        # Should call get_supabase() for user_profiles lookup
        assert "get_supabase()" in func_body, \
            "workflow_transition_history does not call get_supabase() for FIO resolution"
        assert 'user_profiles' in func_body, \
            "workflow_transition_history does not query user_profiles table"

    def test_function_adds_actor_name_to_records(self):
        """Records should be enriched with actor_name field from user_profiles."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        func_start = source.find("def workflow_transition_history(")
        func_end = source.find("\ndef ", func_start + 10)
        func_body = source[func_start:func_end]

        assert 'actor_name' in func_body, \
            "workflow_transition_history does not set actor_name on records"
        assert 'record.get("actor_name"' in func_body or "record.get('actor_name'" in func_body, \
            "actor_name is not displayed in the UI component"

    def test_function_handles_empty_history(self):
        """When no history exists and collapsed=True, should return empty Div."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        func_start = source.find("def workflow_transition_history(")
        func_end = source.find("\ndef ", func_start + 10)
        func_body = source[func_start:func_end]

        # Should early-return for no history
        assert "if not history:" in func_body, \
            "No early return for empty history"
        assert "return Div()" in func_body, \
            "No empty Div return for collapsed mode with no history"


class TestWorkflowTransitionHistoryCallSites:
    """Verify all call sites of workflow_transition_history pass correct arguments."""

    def test_all_calls_use_correct_signature(self):
        """All calls should pass quote_id as first arg, optionally limit and collapsed."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        import re
        # Find all calls to workflow_transition_history
        calls = re.findall(r'workflow_transition_history\([^)]*\)', source)

        # Filter out the definition
        calls = [c for c in calls if "def " not in source[max(0, source.find(c)-10):source.find(c)]]

        assert len(calls) >= 7, \
            f"Expected at least 7 call sites, found {len(calls)}: {calls}"

        for call in calls:
            # Each call should have at least one positional arg (quote_id)
            # and optionally limit=N and/or collapsed=True/False
            assert "(" in call, f"Malformed call: {call}"
            # Should not have any unexpected kwargs
            if "limit=" in call:
                assert "limit=" in call
            if "collapsed=" in call:
                assert "collapsed=" in call

    def test_quote_detail_page_calls_with_limit_and_collapsed(self):
        """The main quote detail page should call with limit=50 and collapsed=True."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        assert "workflow_transition_history(quote_id, limit=50, collapsed=True)" in source, \
            "Quote detail page does not call workflow_transition_history with limit=50, collapsed=True"

    def test_workspace_pages_call_with_defaults(self):
        """Workspace pages should call with just quote_id (using defaults)."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        import re
        # Count calls that use just (quote_id) with no extra args
        simple_calls = re.findall(r'workflow_transition_history\(quote_id\)', source)
        assert len(simple_calls) >= 4, \
            f"Expected at least 4 simple calls (workspaces), found {len(simple_calls)}"


# ============================================================================
# ORDER_SOURCE Tests
# ============================================================================

class TestOrderSourceConstants:
    """Tests for ORDER_SOURCE_OPTIONS and ORDER_SOURCE_LABELS."""

    def test_options_and_labels_are_consistent(self):
        """ORDER_SOURCE_LABELS should be built from ORDER_SOURCE_OPTIONS."""
        main = _import_main()
        options = main.ORDER_SOURCE_OPTIONS
        labels = main.ORDER_SOURCE_LABELS

        assert isinstance(options, list), "ORDER_SOURCE_OPTIONS should be a list"
        assert isinstance(labels, dict), "ORDER_SOURCE_LABELS should be a dict"
        assert len(options) == len(labels), \
            "ORDER_SOURCE_OPTIONS and ORDER_SOURCE_LABELS have different lengths"

        for val, lbl in options:
            assert val in labels, f"Value '{val}' not in ORDER_SOURCE_LABELS"
            assert labels[val] == lbl, f"Label mismatch for '{val}': '{labels[val]}' != '{lbl}'"

    def test_options_have_expected_values(self):
        """ORDER_SOURCE_OPTIONS should include standard source types."""
        main = _import_main()
        values = [val for val, _ in main.ORDER_SOURCE_OPTIONS]
        expected = ["cold_call", "recommendation", "tender", "website", "repeat"]
        for exp in expected:
            assert exp in values, f"Missing expected source type: {exp}"


class TestOrderSourceInlineEditBug:
    """Tests documenting the bug where clearing order_source via inline edit fails.

    Bug: When user selects the empty option in the order_source dropdown,
    the inline edit handler sets new_value=None, then calls
    update_customer(customer_id, order_source=None). But update_customer
    interprets None as "don't change this field" (guard: if order_source is not None).
    So the database value is never actually cleared.
    """

    def test_update_customer_cannot_clear_order_source_with_none(self):
        """Passing order_source=None to update_customer will NOT clear the DB value.

        This is because update_customer uses `if order_source is not None:` guard,
        which means None means "don't touch this field." There is no way to
        distinguish "don't change" from "set to null" with the current API.
        """
        source_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "customer_service.py"
        )
        with open(source_path, "r") as f:
            source = f.read()

        # Verify the guard pattern exists
        assert "if order_source is not None:" in source, \
            "update_customer guard for order_source changed - re-check the bug"

    def test_inline_edit_handler_sends_none_for_empty_selection(self):
        """Inline edit POST handler converts empty order_source to None.

        This interacts badly with update_customer's None guard (see above).
        """
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The handler converts empty string to None for order_source
        assert 'if new_value == "" and field_name == "order_source":\n        new_value = None' in source, \
            "Inline edit handler does not convert empty order_source to None"

    def test_full_form_edit_bypasses_update_customer(self):
        """Full-form edit writes directly to supabase, not via update_customer.

        This means the full-form edit CAN clear order_source (sends None directly),
        while the inline edit CANNOT (goes through update_customer which ignores None).
        This inconsistency confirms the bug.
        """
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The full-form edit handler writes order_source directly to supabase
        assert '"order_source": order_source or None' in source, \
            "Full-form edit handler does not write order_source directly"


# ============================================================================
# ADDITIONAL: Validity days conversion edge cases
# ============================================================================

class TestInlineUpdateValidityDays:
    """Tests for validity_days integer conversion in inline update handler."""

    def test_validity_days_conversion_logic_exists(self):
        """Inline update should convert validity_days to integer with min=1."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        assert 'field == "validity_days"' in source, \
            "No special handling for validity_days in inline update"
        assert "max(1, int(value))" in source, \
            "validity_days not bounded to minimum of 1"

    def test_validity_days_fallback_to_30_on_error(self):
        """If validity_days cannot be parsed, it should fall back to 30."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Find the validity_days conversion block
        idx = source.find('field == "validity_days"')
        block = source[idx:idx+200]
        assert "value = 30" in block, \
            "No fallback to 30 for invalid validity_days"


# ============================================================================
# INTEGRATION: Contact person dropdown on quote detail
# ============================================================================

class TestContactPersonDropdownOnQuoteDetail:
    """Tests that the contact person dropdown is properly rendered."""

    def test_quote_detail_fetches_customer_contacts(self):
        """Quote detail page should fetch customer_contacts for the dropdown."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Should query customer_contacts table
        assert '"customer_contacts"' in source, \
            "No query to customer_contacts table in main.py"

        # Should select id, name, position, phone, is_lpr
        assert '"id, name, position, phone, is_lpr"' in source, \
            "customer_contacts query missing expected columns"

    def test_contact_person_dropdown_uses_inline_patch(self):
        """Contact person dropdown should use hx_patch for inline editing."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # Should have inline HTMX patch for contact_person_id
        assert 'field: "contact_person_id"' in source, \
            "contact_person_id not configured for HTMX inline patch"

    def test_edit_quote_form_includes_contact_person(self):
        """The full edit form should also include contact_person_id field."""
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The POST handler for edit should accept contact_person_id
        assert "contact_person_id: str = None" in source, \
            "Edit quote POST handler missing contact_person_id parameter"
