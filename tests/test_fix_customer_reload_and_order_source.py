"""
Tests for two small fixes in main.py:

Fix 1: Page reload after customer change on quote detail page
  - Script tag adds htmx:afterRequest listener on #inline-customer to reload page
  - Checks: correct rendering, no infinite loop, failure handling, event scoping

Fix 2: order_source direct supabase write in inline edit handler
  - Handler now writes order_source directly to supabase instead of update_customer()
  - Checks: missing customer, org_id authorization, response rendering, no side effects

Fix 3 (SECURITY): organization_id authorization on inline customer field edit
  - Both POST /customers/{id}/update-field/{field} and GET /customers/{id}/cancel-edit/{field}
    now verify customer.organization_id == user["org_id"] before proceeding
  - The direct supabase write for order_source now includes .eq("organization_id", ...)
  - Previously these handlers lacked org-level isolation (documented as bugs, now fixed)

Bugs found are documented as explicit test cases with clear descriptions.
"""

import pytest
import os
import sys
import re
from unittest.mock import patch, MagicMock


# Set test environment before importing app
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")


# ============================================================================
# HELPER: Read main.py source
# ============================================================================

def _read_main_source():
    """Read main.py source as a string."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.read()


def _get_handler_body(source, route_pattern):
    """Extract the body of a handler identified by its @rt() decorator pattern.

    Returns the source text from the @rt(...) line up to the next @rt(...) line.
    """
    handler_start = source.find(route_pattern)
    assert handler_start > 0, f"Route not found: {route_pattern}"
    handler_end = source.find("\n@rt(", handler_start + 10)
    if handler_end == -1:
        handler_end = len(source)
    return source[handler_start:handler_end]


UPDATE_FIELD_ROUTE = '@rt("/customers/{customer_id}/update-field/{field_name}")'
CANCEL_EDIT_ROUTE = '@rt("/customers/{customer_id}/cancel-edit/{field_name}")'


def _import_main():
    """Import main module with mocked dependencies."""
    try:
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
# FIX 1: Page reload after customer change (Script + htmx:afterRequest)
# ============================================================================

class TestCustomerChangeReloadScript:
    """Tests for the Script tag that reloads the page after customer_id change."""

    def test_script_tag_renders_correctly_in_fasthtml(self):
        """Script tag should be a sibling of the Select element inside the Div.

        FastHTML renders Script(...) as a <script> tag in HTML.
        Verify the Script is properly placed after the Select, inside the
        same parent Div, which is a common pattern in this codebase.
        """
        source = _read_main_source()

        # The Script tag should appear right after the Select's closing paren
        # and before the Div's style= attribute
        select_end_idx = source.find('hx_swap="none"\n                    ),\n                    Script("""')
        assert select_end_idx > 0, (
            "Script tag not found immediately after the #inline-customer Select. "
            "Expected pattern: hx_swap='none' ), Script(..."
        )

    def test_no_infinite_loop_risk_from_page_load(self):
        """Page reload should NOT trigger another htmx:afterRequest on #inline-customer.

        The event listener is on the element's htmx:afterRequest, which only fires
        after an HTMX request initiated BY that element. A page reload does not
        trigger any HTMX request on #inline-customer. The Select uses
        hx_trigger="change", which only fires on user interaction (dropdown change),
        not on page load.

        Verify: no hx_trigger="load" on the Select element.
        """
        source = _read_main_source()

        # Find the inline-customer Select definition
        select_start = source.find('id="inline-customer"')
        assert select_start > 0, "inline-customer Select not found"

        # Get the surrounding context (the whole Select element)
        # Look backward to find Select( and forward enough to capture hx_trigger
        select_area = source[select_start - 300:select_start + 500]

        # The trigger must be "change", not "load" or anything auto-firing
        assert 'hx_trigger="change"' in select_area, (
            "inline-customer Select must use hx_trigger='change' to avoid auto-fire"
        )

        # No "load" trigger anywhere on this element
        assert 'hx_trigger="load' not in select_area, (
            "inline-customer Select has hx_trigger='load' which would cause infinite reload loop"
        )

    def test_reload_only_fires_on_successful_request(self):
        """FIXED: The reload script now checks event.detail.successful before reloading.

        The current code does:
            element.addEventListener('htmx:afterRequest', function(event) {
                if (event.detail.successful) { window.location.reload(); }
            });

        Previously the reload was unconditional (fired on both success and failure).
        Now it only reloads when the HTMX request succeeds, preventing:
        1. Losing dropdown state on failed requests
        2. Showing stale data after a failed PATCH
        """
        source = _read_main_source()

        # Find the reload script
        script_start = source.find("document.getElementById('inline-customer').addEventListener('htmx:afterRequest'")
        assert script_start > 0, "Reload script not found"

        # Get the script body
        script_end = source.find('"""\n', script_start)
        script_body = source[script_start:script_end]

        # FIXED: The script now checks for success before reloading
        has_success_check = (
            "event.detail.successful" in script_body or
            "detail.successful" in script_body
        )

        assert has_success_check, (
            "Reload script does not check event.detail.successful. "
            "Unconditional reload will cause poor UX on failed requests."
        )

        # Confirm the reload is still present (just conditional now)
        assert "window.location.reload()" in script_body, (
            "Expected window.location.reload() in the script"
        )

    def test_event_listener_scoped_to_inline_customer_element(self):
        """The event listener should be on the #inline-customer element, not document.body.

        htmx:afterRequest bubbles up from the triggering element. By attaching
        the listener to the specific element (getElementById), it only fires
        when THAT element's HTMX request completes, not for any other HTMX
        request on the page.

        This is correct scoping - if it were on document.body, every HTMX
        request (e.g., inline edits on other fields) would trigger a reload.
        """
        source = _read_main_source()

        # Find the reload listener
        pattern = r"document\.getElementById\('inline-customer'\)\.addEventListener\('htmx:afterRequest'"
        match = re.search(pattern, source)
        assert match is not None, (
            "Event listener not attached to getElementById('inline-customer')"
        )

        # Verify it's NOT on document.body (there is one on document.body for
        # feedback tracking, but the reload one should be element-scoped)
        # Find the specific script block
        script_start = source.find("document.getElementById('inline-customer').addEventListener('htmx:afterRequest'")
        script_end = source.find('"""\n', script_start)
        script_body = source[script_start:script_end]

        assert "document.body" not in script_body, (
            "Reload listener should be on the element, not document.body"
        )

    def test_other_inline_selects_do_not_have_reload_script(self):
        """Only #inline-customer has a reload script. Other selects (seller, delivery, etc.)
        should NOT reload the page on change.

        The customer change is special because it affects the contact person dropdown
        and other customer-dependent UI. Other fields are independent.
        """
        source = _read_main_source()

        # Count reload scripts (may be conditional or unconditional)
        reload_scripts = re.findall(
            r"addEventListener\('htmx:afterRequest',\s*function\([^)]*\)\s*\{[^}]*window\.location\.reload",
            source
        )

        assert len(reload_scripts) == 1, (
            f"Expected exactly 1 reload script (for #inline-customer), "
            f"found {len(reload_scripts)}"
        )


# ============================================================================
# FIX 2: order_source direct supabase write
# ============================================================================

class TestOrderSourceDirectWrite:
    """Tests for the order_source inline edit handler's direct supabase write."""

    def test_handler_checks_customer_exists(self):
        """The handler calls get_customer() and returns error if not found.

        Line: customer = get_customer(customer_id); if not customer: return Div("...")
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        assert "get_customer(customer_id)" in handler_body, (
            "Handler does not call get_customer() to verify customer exists"
        )
        assert 'return Div("' in handler_body, (
            "Handler does not return error Div when customer not found"
        )

    def test_direct_write_includes_organization_id_check(self):
        """FIXED: The direct supabase write now includes organization_id filter.

        The handler at line ~31439 now does:
            supabase.table("customers").update({"order_source": new_value})
                .eq("id", customer_id)
                .eq("organization_id", user["org_id"])
                .execute()

        This was previously a security bug where the direct write only filtered
        by customer_id, without checking org membership. The fix adds
        .eq("organization_id", user["org_id"]) to the supabase write chain.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # The direct supabase write for order_source
        direct_write_idx = handler_body.find('supabase.table("customers").update({"order_source"')
        assert direct_write_idx > 0, "Direct supabase write for order_source not found"

        # Get the line with the direct write
        write_line_end = handler_body.find("\n", direct_write_idx)
        write_line = handler_body[direct_write_idx:write_line_end]

        # FIXED: Now includes organization_id check
        assert "organization_id" in write_line, (
            "Direct supabase write for order_source is still missing organization_id check. "
            "This is a security issue: users could update customers from other organizations."
        )

        # Verify the specific pattern used
        assert '.eq("organization_id", user["org_id"])' in write_line, (
            "organization_id check does not use the expected pattern: "
            '.eq("organization_id", user["org_id"])'
        )

    def test_update_customer_service_still_lacks_org_check(self):
        """The update_customer() service function still does not check organization_id.

        This is acceptable because the handler now performs its own org check
        BEFORE calling update_customer(). The handler at line ~31423 returns
        early with "Клиент не найден" if the customer does not belong to the
        user's organization.
        """
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "customer_service.py"
        )
        with open(service_path, "r") as f:
            service_source = f.read()

        # Find update_customer function body
        func_start = service_source.find("def update_customer(")
        func_end = service_source.find("\ndef ", func_start + 10)
        func_body = service_source[func_start:func_end]

        # The update only filters by id, not organization_id
        assert '.eq("id", customer_id)' in func_body, (
            "update_customer should filter by customer_id"
        )

        # Service still does not check org_id - that is now the handler's job
        # If this changes in the future, the test should be updated but the
        # security posture would be improved, not weakened
        if "organization_id" in func_body:
            # Service was updated too - this is fine, test passes either way
            pass

    def test_inline_edit_handler_requires_login(self):
        """The handler at least requires login (authentication).

        Even without org check, the require_login check ensures only
        authenticated users can hit the endpoint.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        assert "require_login(session)" in handler_body, (
            "Handler does not call require_login - authentication missing"
        )

    def test_direct_write_handles_exception_gracefully(self):
        """If the supabase write throws an exception, success=False is set
        and the handler returns an error Div.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # Exception handling around direct write
        assert "except Exception:" in handler_body, (
            "Direct supabase write for order_source has no exception handling"
        )
        assert "success = False" in handler_body, (
            "Exception handler does not set success = False"
        )

        # Error response for failure
        assert 'if not success:' in handler_body, (
            "Handler does not check for success/failure"
        )

    def test_direct_write_returns_correct_display_for_none_value(self):
        """When order_source is cleared (None), _render_field_display receives "".

        Line: return _render_field_display(customer_id, field_name, new_value or "")

        When new_value is None (user selected empty option), `None or ""` evaluates
        to "", which is correctly passed to _render_field_display. The display
        function then shows "Ne ukazan" for empty values.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # The return uses `new_value or ""` to handle None
        assert 'new_value or ""' in handler_body, (
            "Handler does not use `new_value or ''` fallback for _render_field_display"
        )

    def test_render_field_display_shows_not_specified_for_empty_order_source(self):
        """_render_field_display shows 'Ne ukazan' when order_source value is empty."""
        source = _read_main_source()

        func_start = source.find("def _render_field_display(")
        func_end = source.find("\ndef ", func_start + 10)
        func_body = source[func_start:func_end]

        # For empty value, it should show default placeholder
        assert 'display_value = value if value else "' in func_body, (
            "_render_field_display does not handle empty value with a placeholder"
        )

    def test_no_other_update_field_routes_affected(self):
        """The update-field route pattern is used for customer fields, contact fields,
        and profile fields. Verify the order_source special case only applies to
        the customer update-field handler.
        """
        source = _read_main_source()

        # Find all update-field route definitions
        update_field_routes = re.findall(r'@rt\("[^"]*update-field[^"]*"\)', source)

        # Should have exactly 3: customers, contacts, profile
        assert len(update_field_routes) == 3, (
            f"Expected 3 update-field routes (customers, contacts, profile), "
            f"found {len(update_field_routes)}: {update_field_routes}"
        )

        # The order_source special case should only be in the customer handler
        for i, route_match in enumerate(re.finditer(r'@rt\("([^"]*update-field[^"]*)"\)', source)):
            route_path = route_match.group(1)
            handler_start = route_match.start()
            handler_end = source.find("\n@rt(", handler_start + 10)
            if handler_end == -1:
                handler_end = len(source)
            handler_body = source[handler_start:handler_end]

            if "customer_id" in route_path and "contact_id" not in route_path:
                # Customer handler SHOULD have order_source logic
                assert "order_source" in handler_body, (
                    f"Customer update-field handler missing order_source logic"
                )
            else:
                # Other handlers should NOT have order_source logic
                assert "order_source" not in handler_body, (
                    f"Route {route_path} unexpectedly contains order_source logic"
                )


# ============================================================================
# FIX 3 (SECURITY): organization_id authorization checks
# ============================================================================

class TestUpdateFieldOrgIdAuthorization:
    """Tests that POST /customers/{id}/update-field/{field} checks organization_id.

    This was a security fix: previously the handler did not verify that the
    customer belonged to the requesting user's organization. A user could
    potentially update fields on customers from other organizations by
    crafting the customer_id parameter.
    """

    def test_handler_extracts_user_from_session(self):
        """Handler must extract the user dict from session to access org_id."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        assert 'user = session["user"]' in handler_body, (
            "Handler does not extract user from session. "
            "Without user, cannot check organization_id."
        )

    def test_handler_checks_org_id_before_update(self):
        """Handler must compare customer.organization_id with user['org_id'].

        The check should happen AFTER get_customer() but BEFORE any update logic.
        This ensures org isolation for ALL field updates, not just order_source.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # Must have the org_id comparison
        assert 'customer.organization_id != user["org_id"]' in handler_body, (
            "Handler does not compare customer.organization_id with user org_id"
        )

    def test_handler_returns_access_denied_on_org_mismatch(self):
        """When org_id does not match, handler returns a Div with access denied message.

        The response must include the field id so HTMX can swap it correctly.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # Check for access denied return
        assert 'return Div("' in handler_body

        # The access denied Div should have the correct id for HTMX targeting
        # Pattern: return Div("Клиент не найден", id=f"field-{field_name}")
        access_denied_pattern = re.search(
            r'if customer\.organization_id != user\["org_id"\]:\s*\n\s*return Div\([^)]*id=f"field-\{field_name\}"',
            handler_body
        )
        assert access_denied_pattern is not None, (
            "Access denied response does not include id=f'field-{field_name}' for HTMX swap. "
            "Without this id, the HTMX swap target will not be found."
        )

    def test_org_check_is_before_form_data_read(self):
        """The organization check must happen BEFORE reading form data.

        This is important for defense-in-depth: if the org check fails,
        we should not process the request body at all.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        org_check_pos = handler_body.find('customer.organization_id != user["org_id"]')
        form_data_pos = handler_body.find("request.form()")

        assert org_check_pos > 0, "org_id check not found"
        assert form_data_pos > 0, "form data read not found"
        assert org_check_pos < form_data_pos, (
            "Organization check happens AFTER reading form data. "
            "It should happen before to avoid processing unauthorized requests."
        )

    def test_org_check_is_before_supabase_write(self):
        """The organization check must happen BEFORE any supabase write."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        org_check_pos = handler_body.find('customer.organization_id != user["org_id"]')
        supabase_write_pos = handler_body.find('supabase.table("customers").update')

        assert org_check_pos > 0, "org_id check not found"
        assert supabase_write_pos > 0, "supabase write not found"
        assert org_check_pos < supabase_write_pos, (
            "Organization check happens AFTER supabase write. "
            "This means unauthorized writes can still happen."
        )

    def test_org_check_is_before_update_customer_call(self):
        """The organization check must happen BEFORE the update_customer() call."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        org_check_pos = handler_body.find('customer.organization_id != user["org_id"]')
        update_call_pos = handler_body.find("update_customer(customer_id")

        assert org_check_pos > 0, "org_id check not found"
        assert update_call_pos > 0, "update_customer call not found"
        assert org_check_pos < update_call_pos, (
            "Organization check happens AFTER update_customer call. "
            "This means unauthorized updates can still happen."
        )


class TestCancelEditOrgIdAuthorization:
    """Tests that GET /customers/{id}/cancel-edit/{field} checks organization_id.

    Even though cancel-edit is a read-only operation (returns current value),
    it should still verify org membership. Otherwise, an attacker could
    enumerate field values of customers from other organizations.
    """

    def test_cancel_edit_handler_exists(self):
        """The cancel-edit route should exist."""
        source = _read_main_source()
        assert CANCEL_EDIT_ROUTE in source, (
            "cancel-edit route not found in main.py"
        )

    def test_cancel_edit_requires_login(self):
        """Cancel-edit handler must require authentication."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        assert "require_login(session)" in handler_body, (
            "cancel-edit handler does not require login"
        )

    def test_cancel_edit_extracts_user_from_session(self):
        """Cancel-edit handler must extract user from session."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        assert 'user = session["user"]' in handler_body, (
            "cancel-edit handler does not extract user from session"
        )

    def test_cancel_edit_checks_org_id(self):
        """Cancel-edit handler must check customer.organization_id against user org_id."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        assert 'customer.organization_id != user["org_id"]' in handler_body, (
            "cancel-edit handler does not check organization_id. "
            "This allows reading customer field values from other organizations."
        )

    def test_cancel_edit_returns_access_denied_on_org_mismatch(self):
        """Cancel-edit should return access denied Div with correct field id."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        access_denied_pattern = re.search(
            r'if customer\.organization_id != user\["org_id"\]:\s*\n\s*return Div\([^)]*id=f"field-\{field_name\}"',
            handler_body
        )
        assert access_denied_pattern is not None, (
            "cancel-edit access denied response does not include correct HTMX target id"
        )

    def test_cancel_edit_checks_customer_exists(self):
        """Cancel-edit should return error if customer not found."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        assert "get_customer(customer_id)" in handler_body, (
            "cancel-edit does not call get_customer()"
        )
        assert "if not customer:" in handler_body, (
            "cancel-edit does not check for missing customer"
        )

    def test_cancel_edit_org_check_is_before_value_read(self):
        """Org check should happen before reading the current field value."""
        source = _read_main_source()
        handler_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        org_check_pos = handler_body.find('customer.organization_id != user["org_id"]')
        getattr_pos = handler_body.find("getattr(customer, field_name")

        assert org_check_pos > 0, "org_id check not found in cancel-edit"
        assert getattr_pos > 0, "getattr call not found in cancel-edit"
        assert org_check_pos < getattr_pos, (
            "Org check happens AFTER reading field value in cancel-edit. "
            "Field value could be leaked to unauthorized users."
        )


class TestOrgIdCheckConsistency:
    """Tests verifying consistency of org_id checks across both handlers."""

    def test_both_handlers_use_same_org_check_pattern(self):
        """Both update-field and cancel-edit should use the exact same org check pattern."""
        source = _read_main_source()
        update_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)
        cancel_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        org_check = 'customer.organization_id != user["org_id"]'
        assert org_check in update_body, "update-field missing org check"
        assert org_check in cancel_body, "cancel-edit missing org check"

    def test_both_handlers_use_same_access_denied_message(self):
        """Both handlers should return the same access denied message for consistency."""
        source = _read_main_source()
        update_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)
        cancel_body = _get_handler_body(source, CANCEL_EDIT_ROUTE)

        # Both should use the same "not found" message (avoids leaking resource existence)
        denied_msg = '"Клиент не найден"'
        assert denied_msg in update_body, (
            f"update-field does not use not-found message: {denied_msg}"
        )
        assert denied_msg in cancel_body, (
            f"cancel-edit does not use not-found message: {denied_msg}"
        )

    def test_both_handlers_check_customer_not_found_before_org_check(self):
        """Both handlers should check customer existence BEFORE org check.

        Order matters: if customer is None, accessing customer.organization_id
        would raise AttributeError. So "not found" check must come first.
        """
        source = _read_main_source()

        for route_label, route_pattern in [
            ("update-field", UPDATE_FIELD_ROUTE),
            ("cancel-edit", CANCEL_EDIT_ROUTE),
        ]:
            handler_body = _get_handler_body(source, route_pattern)

            not_found_pos = handler_body.find("if not customer:")
            org_check_pos = handler_body.find('customer.organization_id != user["org_id"]')

            assert not_found_pos > 0, f"{route_label}: 'if not customer' check not found"
            assert org_check_pos > 0, f"{route_label}: org_id check not found"
            assert not_found_pos < org_check_pos, (
                f"{route_label}: org_id check happens BEFORE customer existence check. "
                "This would cause AttributeError when customer is None."
            )

    def test_full_form_edit_also_checks_org_id(self):
        """For reference: the full-form edit at /customers/{id}/edit also checks org_id.

        This verifies the security fix is consistent with the full form approach.
        """
        source = _read_main_source()

        # The full-form edit should have an org_id check in its supabase write
        edit_handler_pattern = '.eq("id", customer_id).eq("organization_id", user["org_id"])'
        assert edit_handler_pattern in source, (
            "Full-form edit at /customers/{id}/edit should also check organization_id. "
            "The inline edit fix should be consistent with this pattern."
        )


# ============================================================================
# ORDER_SOURCE CLEARING BEHAVIOR
# ============================================================================

class TestOrderSourceClearingBehavior:
    """Tests verifying that the direct write correctly handles the clearing scenario
    that update_customer cannot handle."""

    def test_why_direct_write_exists(self):
        """The direct supabase write exists because update_customer() cannot clear
        nullable fields (it uses `if field is not None:` guards).

        Verify this limitation still exists.
        """
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "customer_service.py"
        )
        with open(service_path, "r") as f:
            service_source = f.read()

        # The guard that prevents clearing
        assert "if order_source is not None:" in service_source, (
            "update_customer guard for order_source changed - "
            "direct write in handler may no longer be needed"
        )

    def test_empty_string_converted_to_none_before_write(self):
        """When user selects empty option, form sends "", which is converted
        to None before the direct supabase write.
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # The conversion: empty string -> None for order_source
        assert 'new_value == "" and field_name == "order_source"' in handler_body, (
            "Empty string to None conversion for order_source not found"
        )
        assert "new_value = None" in handler_body, (
            "new_value is not set to None for empty order_source"
        )

    def test_supabase_update_with_none_sets_null_in_db(self):
        """When supabase.table().update({"order_source": None}) is called,
        it sends a JSON null to PostgREST, which sets the column to NULL.

        This is the correct behavior for clearing the field.
        (This test validates the pattern by checking the code sends None, not "".)
        """
        source = _read_main_source()
        handler_body = _get_handler_body(source, UPDATE_FIELD_ROUTE)

        # The direct write sends new_value which is None at this point
        assert 'update({"order_source": new_value})' in handler_body, (
            "Direct write does not use new_value (which is None for clearing)"
        )


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
