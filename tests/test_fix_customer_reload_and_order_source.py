"""
Tests for Fix 1 (Page reload after customer change on quote detail page).

Fix 1: Page reload after customer change on quote detail page
  - Script tag adds htmx:afterRequest listener on #inline-customer to reload page
  - Checks: correct rendering, no infinite loop, failure handling, event scoping

Note: Fix 2 (order_source direct supabase write) and Fix 3 (inline edit
organization_id authorization) tests were removed when the /customers area
was archived in Phase 6C-2B-1 (2026-04-20). Those handlers now live in
legacy-fasthtml/customers.py and are no longer mounted.
"""

import os
import re


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

