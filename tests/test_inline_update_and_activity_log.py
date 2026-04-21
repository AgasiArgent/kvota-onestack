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
- update_customer() service-layer guard for order_source (still documented
  post-archive of the FastHTML /customers area in Phase 6C-2B-1)
"""

# Phase 6C-3 (2026-04-21): FastHTML shell retired; main.py is now a 22-line stub.
# These tests parse main.py source or access removed attributes to validate
# archived FastHTML code. Skipping keeps the suite green while a follow-up PR
# decides whether to delete, rewrite against legacy-fasthtml/, or port to
# Next.js E2E tests.
import pytest
pytest.skip(
    "Tests validate archived FastHTML code in main.py (Phase 6C-3). "
    "Follow-up: delete or retarget to legacy-fasthtml/.",
    allow_module_level=True,
)


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
# Inline-update tests for /quotes/{id}/inline deleted in Phase 6C-2B Mega-C
# (2026-04-20). The handler was archived to
# legacy-fasthtml/quote_detail_and_workflow.py. Previously removed classes:
# TestInlineUpdateContactPersonClearing, TestInlineUpdateCustomerSameValue.
# ============================================================================

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


# ============================================================================
# TestWorkflowTransitionHistoryCallSites REMOVED in Phase 6C-2B Mega-C
# (2026-04-20). All known call sites (/quotes/{id} detail + workspace
# /procurement, /logistics, /customs, /quote-control, /spec-control) were
# archived across Mega-A/B/C. The remaining caller lives inside
# _finance_main_tab_content via quote.get("id"), which is not the
# pattern these tests asserted on. workflow_transition_history itself is
# preserved in main.py — covered by TestWorkflowTransitionHistoryFIOResolution.
# ============================================================================


# ============================================================================
# ORDER_SOURCE Tests — REMOVED
# ============================================================================
# ORDER_SOURCE_OPTIONS / ORDER_SOURCE_LABELS constants and the inline edit
# handler for order_source lived in the /customers FastHTML area, which was
# archived to legacy-fasthtml/customers.py in Phase 6C-2B-1 (2026-04-20).
# The remaining tests in this class documented archived handler behavior.


class TestOrderSourceServiceBehavior:
    """Tests for order_source behavior in services/customer_service.py.

    The UI layer moved to Next.js and the FastHTML inline edit handler was
    archived in Phase 6C-2B-1, but the service-layer behavior documented
    here still applies (for /api/customers/* consumers).
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

    def test_full_form_edit_route_absent(self):
        """Full-form /customers/{id}/edit route must not exist in main.py.

        The /customers area was archived in Phase 6C-2B-1. The entire
        /customers/{customer_id}/edit handler now lives in
        legacy-fasthtml/customers.py (if it existed) or was removed earlier.
        """
        source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(source_path, "r") as f:
            source = f.read()

        # The standalone edit route should no longer exist
        assert '@rt("/customers/{customer_id}/edit")' not in source, \
            "/customers/{id}/edit route should be absent post-archive"


# ============================================================================
# ADDITIONAL: Validity days conversion edge cases
# ============================================================================

# ============================================================================
# TestInlineUpdateValidityDays REMOVED in Phase 6C-2B Mega-C (2026-04-20).
# The /quotes/{id}/inline PATCH handler was archived to
# legacy-fasthtml/quote_detail_and_workflow.py.
# ============================================================================


# ============================================================================
# TestContactPersonDropdownOnQuoteDetail REMOVED in Phase 6C-2B Mega-C
# (2026-04-20). The /quotes/{id} GET handler was archived to
# legacy-fasthtml/quote_detail_and_workflow.py. The contact-person dropdown
# lives in Next.js /quotes/[id] and is covered by frontend e2e tests.
# ============================================================================
