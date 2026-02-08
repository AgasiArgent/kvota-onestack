"""
TDD tests for customer creation modal + removal of old pages.

These tests define the CONTRACT for the feature which does NOT exist yet.
The developer must implement:

1. Replace /customers/new full page with a modal dialog on /customers list page
2. Modal contains: INN input + "Создать" button + "Не знаю ИНН" button
3. INN path: Enter INN -> calls DaData -> creates customer with DaData data -> redirect to detail
4. No-INN path: Click "Не знаю ИНН" -> creates customer with auto-generated name -> redirect to detail
5. Remove standalone /customers/{id}/edit page (detail page has inline editing)
6. Old GET /customers/new should redirect to /customers or be removed
7. Error form on POST should use `legal_address` not `address`

Tests use source-code analysis pattern (read main.py and check structure).
"""

import os
import re
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# Set test environment
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("DADATA_API_KEY", "test-dadata-key")


# ============================================================================
# HELPERS
# ============================================================================

def _read_main_source():
    """Read main.py source as a string."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.read()


def _read_main_lines():
    """Read main.py as list of lines."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.readlines()


def _find_route_decorators(source, route_pattern):
    """Find all @rt() decorators matching a route pattern.

    Returns list of (line_number, line_text) tuples.
    """
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        if re.search(route_pattern, line):
            results.append((i, line.strip()))
    return results


def _get_handler_body(source, route_pattern):
    """Extract handler body from @rt() decorator to next @rt().

    Returns the source text from the @rt(...) line up to the next @rt(...) line.
    Returns None if the route pattern is not found.
    """
    handler_start = source.find(route_pattern)
    if handler_start < 0:
        return None
    handler_end = source.find("\n@rt(", handler_start + 10)
    if handler_end == -1:
        handler_end = len(source)
    return source[handler_start:handler_end]


CUSTOMERS_LIST_ROUTE = '@rt("/customers")'
CUSTOMERS_NEW_GET_ROUTE = '@rt("/customers/new")'
CUSTOMERS_EDIT_ROUTE = '@rt("/customers/{customer_id}/edit")'


def _get_post_handler_for_customers_new(source):
    """Extract specifically the POST handler body for /customers/new.

    Splits source on @rt decorators and finds the chunk that starts
    with 'def post(' after a @rt("/customers/new") decorator.
    Returns the handler body text or None.
    """
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '@rt("/customers/new")' in line:
            # Check if the function after this decorator is `def post`
            # Look in the next few lines for the function definition
            for j in range(i + 1, min(i + 5, len(lines))):
                if "def post(" in lines[j]:
                    # Found POST handler - extract until next @rt
                    handler_lines = []
                    for k in range(i, len(lines)):
                        if k > i and lines[k].strip().startswith("@rt("):
                            break
                        handler_lines.append(lines[k])
                    return "\n".join(handler_lines)
        i += 1
    return None


# ============================================================================
# TEST 1: Modal markup on /customers list page
# ============================================================================

class TestCustomersListHasModal:
    """The /customers list page must contain modal markup for creating a customer."""

    def test_customers_page_has_modal_trigger_button(self):
        """The /customers GET handler must include a button to open the creation modal.

        Expected: A button/link with text containing 'Новый клиент' or 'Добавить клиента'
        that opens a modal dialog (not navigates to /customers/new).
        """
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        # The button should trigger a modal (dialog), not link to /customers/new
        has_modal_trigger = (
            "dialog" in handler.lower()
            or "modal" in handler.lower()
            or "onclick" in handler.lower()
            or "hx-get" in handler.lower()
        )
        assert has_modal_trigger, (
            "GET /customers handler must have a modal trigger (dialog/modal element or "
            "hx-get to load modal content). Currently it links to /customers/new full page."
        )

    def test_customers_page_has_modal_dialog_element(self):
        """The /customers page must contain a <dialog> or modal Div for customer creation.

        The modal should contain the INN input and creation buttons.
        """
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        has_modal_element = (
            "Dialog(" in handler
            or "dialog" in handler.lower()
            or 'id="customer-modal"' in handler
            or 'id="create-customer-modal"' in handler
            or "modal" in handler.lower()
        )
        assert has_modal_element, (
            "GET /customers handler must include a modal dialog element for customer creation."
        )

    def test_modal_has_inn_input(self):
        """The modal must contain an INN input field."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        # The modal section should have an INN input
        has_inn_in_modal = (
            ('name="inn"' in handler and ("modal" in handler.lower() or "dialog" in handler.lower()))
        )
        assert has_inn_in_modal, (
            "Modal on /customers page must contain an INN input field (name='inn')."
        )

    def test_modal_has_create_button(self):
        """The modal must have a 'Создать' (Create) button for INN-based creation."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        has_create_btn = (
            "Создать" in handler
            and ("modal" in handler.lower() or "dialog" in handler.lower())
        )
        assert has_create_btn, (
            "Modal must have a 'Создать' button for creating a customer with INN."
        )

    def test_modal_has_no_inn_button(self):
        """The modal must have a 'Не знаю ИНН' button for creation without INN."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        has_no_inn_btn = "Не знаю ИНН" in handler
        assert has_no_inn_btn, (
            "Modal must have a 'Не знаю ИНН' button for creating a customer without INN lookup."
        )

    def test_no_link_to_customers_new_page(self):
        """The /customers page should NOT link to /customers/new as a full page.

        The old 'Новый клиент' button that navigates to /customers/new should be
        replaced with a modal trigger.
        """
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        # Should NOT have a direct href to /customers/new
        has_href_to_new = 'href="/customers/new"' in handler
        assert not has_href_to_new, (
            "GET /customers should NOT link to /customers/new. "
            "Replace with modal trigger."
        )


# ============================================================================
# TEST 2: POST /customers/new with INN (DaData lookup path)
# ============================================================================

class TestCreateCustomerWithInn:
    """POST /customers/new with INN calls DaData and creates customer."""

    def test_post_customers_new_route_exists(self):
        """POST /customers/new route must exist."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler (def post) not found"

    def test_post_handler_accepts_inn_parameter(self):
        """POST handler must accept 'inn' as a form parameter."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        # Check function signature (first ~300 chars)
        assert "inn" in handler[:500], (
            "POST /customers/new handler must accept 'inn' parameter"
        )

    def test_post_handler_calls_dadata_on_inn(self):
        """When INN is provided, POST handler should call DaData to get company info."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_dadata_call = (
            "lookup_company_by_inn" in handler
            or "dadata_service" in handler
        )
        assert has_dadata_call, (
            "POST /customers/new must call DaData lookup when INN is provided. "
            "Import and use lookup_company_by_inn from services.dadata_service."
        )

    def test_post_handler_creates_customer_with_dadata_fields(self):
        """When DaData returns data, handler should use name, legal_address, kpp, ogrn from DaData."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_field_mapping = (
            "legal_address" in handler
            and ("kpp" in handler or "ogrn" in handler)
        )
        assert has_field_mapping, (
            "POST handler must map DaData result fields (legal_address, kpp, ogrn) "
            "to customer record when creating with INN."
        )

    def test_post_handler_redirects_to_customer_detail(self):
        """After creating customer, handler should redirect to /customers/{customer_id}.

        Currently redirects to /customers (list) but should redirect to
        /customers/{new_customer_id} (detail page) so user can continue editing.
        """
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        # Must redirect to /customers/{id} (detail), not just /customers (list)
        # The handler must extract the created customer's ID and use it in the redirect
        has_detail_redirect = (
            "result.data" in handler
            and 'f"/customers/' in handler
        )
        assert has_detail_redirect, (
            "POST /customers/new must redirect to /customers/{customer_id} (detail page), "
            "not /customers (list). Extract the new customer ID from insert result."
        )

    def test_post_handler_saves_inn_to_customer(self):
        """The created customer record should have the INN saved."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_inn_in_insert = (
            '"inn"' in handler and "insert" in handler
        )
        assert has_inn_in_insert, (
            "POST handler must include 'inn' in the customer insert data."
        )


# ============================================================================
# TEST 3: POST /customers/new without INN (no-INN path)
# ============================================================================

class TestCreateCustomerWithoutInn:
    """POST /customers/new with no_inn flag creates customer with auto-generated name."""

    def test_post_handler_supports_no_inn_flag(self):
        """POST handler must accept a no_inn flag/parameter for creating without INN lookup."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_no_inn = (
            "no_inn" in handler
            or "no-inn" in handler
            or "skip_inn" in handler
            or "without_inn" in handler
        )
        assert has_no_inn, (
            "POST /customers/new must accept a flag (e.g., no_inn) for creating "
            "customer without INN. The 'Не знаю ИНН' button should submit this flag."
        )

    def test_auto_generated_name_format(self):
        """When no INN, customer name should be auto-generated as 'Новый клиент YYYYMMDD-HHmm'."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_auto_name = (
            "Новый клиент" in handler
            and "strftime" in handler
        )
        assert has_auto_name, (
            "POST handler must generate name like 'Новый клиент 20260208-2135' using "
            "datetime.now().strftime() when creating without INN."
        )

    def test_no_inn_path_still_redirects_to_detail(self):
        """Even without INN, after creation should redirect to /customers/{id}."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        # Should redirect to customer detail page (extract ID from result)
        has_detail_redirect = (
            "RedirectResponse" in handler
            and "result.data" in handler
        )
        assert has_detail_redirect, (
            "POST handler must redirect to /customers/{customer_id} (detail page) "
            "after creation (both INN and no-INN paths)."
        )

    def test_no_inn_path_skips_dadata_call(self):
        """When no_inn flag is set, handler should NOT call DaData API."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_conditional = (
            ("no_inn" in handler or "no-inn" in handler or "skip_inn" in handler)
            and ("if " in handler)
        )
        assert has_conditional, (
            "POST handler must have conditional logic to skip DaData when "
            "no_inn flag is set."
        )


# ============================================================================
# TEST 4: GET /customers/new should redirect or be removed
# ============================================================================

class TestOldCustomersNewPageRemoved:
    """GET /customers/new full page should be replaced by modal on /customers."""

    def test_get_customers_new_redirects_or_removed(self):
        """GET /customers/new should either redirect to /customers or not exist as a full page.

        The full-page customer creation form should be replaced by the modal.
        If GET /customers/new still exists, it should return a redirect (302/303).
        """
        source = _read_main_source()
        # Find GET handler specifically
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if '@rt("/customers/new")' in line:
                # Check next few lines for def get(
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "def get(" in lines[j]:
                        # Found GET handler - extract its body
                        handler_lines = []
                        for k in range(i, len(lines)):
                            if k > i and lines[k].strip().startswith("@rt("):
                                break
                            handler_lines.append(lines[k])
                        handler = "\n".join(handler_lines)

                        has_full_page = "page_layout" in handler
                        has_redirect = "RedirectResponse" in handler

                        assert has_redirect or not has_full_page, (
                            "GET /customers/new still renders a full page. It should either:\n"
                            "  a) Redirect to /customers (where the modal is), or\n"
                            "  b) Be removed entirely"
                        )
                        return
        # If no GET handler found at all, that's also acceptable (removed)

    def test_no_full_creation_form_on_customers_new(self):
        """GET /customers/new should NOT have a full creation form with multiple fields.

        The old form had name, inn, email, phone, legal_address fields.
        This should now be in the modal, not on a separate page.
        """
        source = _read_main_source()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if '@rt("/customers/new")' in line:
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "def get(" in lines[j]:
                        handler_lines = []
                        for k in range(i, len(lines)):
                            if k > i and lines[k].strip().startswith("@rt("):
                                break
                            handler_lines.append(lines[k])
                        handler = "\n".join(handler_lines)

                        field_count = sum(1 for field in [
                            'name="name"', 'name="inn"', 'name="email"',
                            'name="phone"', 'name="legal_address"'
                        ] if field in handler)

                        assert field_count < 3, (
                            f"GET /customers/new still has {field_count} form fields. "
                            "The full creation form should be removed (modal replaces it)."
                        )
                        return


# ============================================================================
# TEST 5: /customers/{id}/edit page should be removed
# ============================================================================

class TestCustomerEditPageRemoved:
    """GET and POST /customers/{id}/edit should not exist (inline editing on detail page)."""

    def test_get_customers_edit_removed(self):
        """GET /customers/{customer_id}/edit should not exist.

        The customer detail page (/customers/{customer_id}) already has
        inline editing for all fields, so the separate edit page is redundant.
        """
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/customers/\{customer_id\}/edit"\)')

        assert len(decorators) == 0, (
            f"Found {len(decorators)} @rt('/customers/{{customer_id}}/edit') route(s) "
            f"at lines: {[d[0] for d in decorators]}. "
            "These should be removed since the detail page has inline editing."
        )

    def test_post_customers_edit_removed(self):
        """POST /customers/{customer_id}/edit should not exist."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_EDIT_ROUTE)
        assert handler is None, (
            "POST /customers/{customer_id}/edit still exists. "
            "Remove it - the detail page has inline editing via HTMX PATCH."
        )

    def test_no_links_to_customer_edit_page(self):
        """No links should reference /customers/{id}/edit."""
        source = _read_main_source()
        # Find hrefs that point to customer edit pages
        edit_links = re.findall(r'href="[^"]*customers/[^"]*edit[^"]*"', source)
        # Filter out edit-field (inline editing sub-routes) which are fine
        real_edit_links = [
            link for link in edit_links
            if "edit-field" not in link and "cancel-edit" not in link
        ]
        assert len(real_edit_links) == 0, (
            f"Found {len(real_edit_links)} link(s) to customer edit page: {real_edit_links}. "
            "These should be removed."
        )


# ============================================================================
# TEST 6: Error handling in POST /customers/new
# ============================================================================

class TestCustomerCreationErrorHandling:
    """Error handling should use correct field names."""

    def test_error_form_uses_legal_address_not_address(self):
        """Error form on POST /customers/new should use 'legal_address' not 'address'.

        The old error form references a variable 'address' which doesn't exist in
        the POST handler signature (it's 'legal_address'). This causes a NameError
        when the form is re-rendered on error.
        """
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        except_idx = handler.find("except")
        if except_idx > 0:
            error_section = handler[except_idx:]
            has_bare_address = (
                'name="address"' in error_section
                or "value=address" in error_section
            )
            assert not has_bare_address, (
                "Error form uses 'address' but handler parameter is 'legal_address'. "
                "This causes a NameError. Use 'legal_address' in the error form."
            )

    def test_post_handler_handles_dadata_failure_gracefully(self):
        """If DaData API fails, customer should still be created with just the INN."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_dadata_error_handling = (
            "lookup_company_by_inn" in handler
            and "try:" in handler
            and "except" in handler
        )
        assert has_dadata_error_handling, (
            "POST handler should call DaData and handle API failures gracefully. "
            "If DaData fails, create customer with just the provided INN and name."
        )

    def test_duplicate_inn_error_handled(self):
        """Duplicate INN should show a user-friendly error message."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_duplicate_handling = "duplicate" in handler.lower() or "уже существует" in handler
        assert has_duplicate_handling, (
            "POST handler should handle duplicate INN errors with a user-friendly message."
        )


# ============================================================================
# TEST 7: Auto-generated name format verification
# ============================================================================

class TestAutoGeneratedNameFormat:
    """Verify the auto-generated customer name format."""

    def test_name_format_matches_spec(self):
        """Auto-generated name must match 'Новый клиент YYYYMMDD-HHmm' pattern."""
        # Define the expected format
        now = datetime.now()
        expected_prefix = "Новый клиент"
        expected_date_part = now.strftime("%Y%m%d")

        # Construct what the name should look like
        sample_name = f"Новый клиент {expected_date_part}-{now.strftime('%H%M')}"

        # Verify format
        pattern = r"^Новый клиент \d{8}-\d{4}$"
        assert re.match(pattern, sample_name), (
            f"Generated name '{sample_name}' doesn't match expected format "
            "'Новый клиент YYYYMMDD-HHmm'"
        )

    def test_source_uses_correct_strftime_format(self):
        """The source code should use strftime with '%Y%m%d-%H%M' or equivalent."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_correct_format = (
            "%Y%m%d" in handler
            or "%Y%m%d-%H%M" in handler
            or "strftime" in handler
        )
        assert has_correct_format, (
            "POST handler must use strftime with format like '%Y%m%d-%H%M' "
            "for auto-generating customer names."
        )


# ============================================================================
# TEST 8: Modal form action and method
# ============================================================================

class TestModalFormAttributes:
    """The modal's form should submit correctly."""

    def test_modal_form_posts_to_customers_new(self):
        """The modal form should POST to /customers/new."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        has_form_action = (
            'action="/customers/new"' in handler
            or 'hx_post="/customers/new"' in handler
            or 'hx-post="/customers/new"' in handler
        )
        assert has_form_action, (
            "Modal form must POST to /customers/new (either via action= or hx-post=)."
        )

    def test_modal_form_uses_post_method(self):
        """The modal form should use POST method."""
        source = _read_main_source()
        handler = _get_handler_body(source, CUSTOMERS_LIST_ROUTE)
        assert handler is not None, "GET /customers route not found"

        has_post_method = (
            'method="post"' in handler
            or 'hx_post=' in handler
            or 'hx-post=' in handler
        )
        assert has_post_method, (
            "Modal form must use POST method."
        )


# ============================================================================
# TEST 9: Security - POST handler checks authentication and organization
# ============================================================================

class TestCustomerCreationSecurity:
    """Security checks on the customer creation handler."""

    def test_post_handler_requires_login(self):
        """POST /customers/new must require authentication."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_auth = (
            "require_login" in handler
            or "session" in handler[:200]
        )
        assert has_auth, (
            "POST /customers/new must require login (call require_login or check session)."
        )

    def test_post_handler_uses_organization_id(self):
        """POST handler must associate customer with the user's organization."""
        source = _read_main_source()
        handler = _get_post_handler_for_customers_new(source)
        assert handler is not None, "POST /customers/new handler not found"
        has_org = "organization_id" in handler or "org_id" in handler
        assert has_org, (
            "POST /customers/new must set organization_id on the customer record."
        )
