"""
TDD tests for form-first quote creation (GET /quotes/new shows form, POST creates record).

CURRENT BEHAVIOR (broken):
- GET /quotes/new immediately inserts a draft quote into DB and redirects to /quotes/{id}
- No form shown, no user confirmation
- Accidental clicks create junk records in the database

DESIRED BEHAVIOR:
- GET /quotes/new: Renders a creation FORM with essential fields
- POST /quotes/new: Creates DB record only when user submits the form
- After creation: Redirect to /quotes/{id} detail page

These tests are written BEFORE implementation (TDD).
All tests should FAIL against the current code because:
  - GET handler currently contains .insert() (should not)
  - GET handler does not render a Form (should)
  - POST handler does not exist yet (should)

Source-code scanning pattern: reads main.py text and asserts on structure.
No network calls, no imports of the app, no flaky dependencies.
"""

import os
import re
import pytest


# ============================================================================
# HELPERS
# ============================================================================

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code as a single string."""
    with open(MAIN_PY) as f:
        return f.read()


def _get_handler_body(source, route_decorator, handler_type="get"):
    """Extract handler body from @rt() decorator to next @rt() or end of file.

    Finds the specific handler (get or post) after the given route decorator.
    Returns the source text from the @rt(...) line through the handler body,
    or None if not found.
    """
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if route_decorator in line:
            # Check next few lines for the correct def type
            for j in range(i + 1, min(i + 5, len(lines))):
                if f"def {handler_type}(" in lines[j]:
                    # Found the right handler - extract until next @rt
                    handler_lines = []
                    for k in range(i, len(lines)):
                        if k > i and lines[k].strip().startswith("@rt("):
                            break
                        handler_lines.append(lines[k])
                    return "\n".join(handler_lines)
        i += 1
    return None


QUOTES_NEW_ROUTE = '@rt("/quotes/new")'


# ============================================================================
# TEST 1: GET /quotes/new must NOT insert into DB
# ============================================================================

class TestGetQuotesNewNoInsert:
    """GET /quotes/new must render a form, NOT insert into the database."""

    def test_get_handler_exists(self):
        """GET /quotes/new handler must exist."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, (
            "GET /quotes/new handler (def get) not found in main.py"
        )

    def test_get_handler_does_not_insert(self):
        """GET /quotes/new must NOT contain any .insert() call.

        Currently the GET handler creates a draft quote on every request.
        After the fix, only the POST handler should insert.
        """
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_insert = ".insert(" in handler
        assert not has_insert, (
            "GET /quotes/new handler must NOT contain .insert() call. "
            "Currently it inserts a draft quote on every GET request, creating junk records. "
            "Move the insert logic to the POST handler."
        )

    def test_get_handler_does_not_generate_idn(self):
        """GET /quotes/new should NOT generate an idn_quote number.

        IDN generation belongs in the POST handler (only on actual creation).
        """
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_idn_gen = "idn_quote" in handler
        assert not has_idn_gen, (
            "GET /quotes/new handler must NOT generate idn_quote. "
            "IDN generation should happen only in the POST handler on actual creation."
        )


# ============================================================================
# TEST 2: GET /quotes/new must render a Form
# ============================================================================

class TestGetQuotesNewRendersForm:
    """GET /quotes/new must render a creation form with proper attributes."""

    def test_get_handler_renders_form(self):
        """GET handler must render a Form element."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_form = "Form(" in handler
        assert has_form, (
            "GET /quotes/new must render a Form element. "
            "Currently it just inserts and redirects without showing any form."
        )

    def test_form_uses_post_method(self):
        """The form must use method='post'."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_post_method = 'method="post"' in handler
        assert has_post_method, (
            "Form on GET /quotes/new must use method='post' to submit data."
        )

    def test_form_action_points_to_quotes_new(self):
        """The form action must point to /quotes/new."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_action = 'action="/quotes/new"' in handler
        assert has_action, (
            "Form on GET /quotes/new must have action='/quotes/new' "
            "so that it POSTs to the creation endpoint."
        )

    def test_form_has_page_layout_with_form(self):
        """GET handler must use page_layout to render a form page (not just error layout)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        # page_layout must be used together with Form() in the main rendering path,
        # not just in the except/error branch
        has_form = "Form(" in handler
        has_layout = "page_layout(" in handler
        assert has_form and has_layout, (
            "GET /quotes/new must use page_layout() to render a page with a Form() element. "
            "Currently it only uses page_layout in the error branch, not for the main form."
        )


# ============================================================================
# TEST 3: GET /quotes/new form must have required fields
# ============================================================================

class TestGetQuotesNewFormFields:
    """GET /quotes/new form must contain the correct fields."""

    def test_form_has_customer_id_select(self):
        """Form must contain a customer_id Select dropdown (required field)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_customer_select = (
            'name="customer_id"' in handler
            and "Select(" in handler
        )
        assert has_customer_select, (
            "Form must have a Select element with name='customer_id'. "
            "Customer is a required field for quote creation."
        )

    def test_customer_field_is_required(self):
        """The customer_id field must be marked as required."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        # Look for required=True near customer_id in the handler
        # The Select for customer_id should have required=True
        customer_section_start = handler.find('name="customer_id"')
        assert customer_section_start >= 0, "customer_id field not found in handler"

        # Check the surrounding ~500 chars for required attribute
        section_start = max(0, customer_section_start - 300)
        section_end = min(len(handler), customer_section_start + 200)
        customer_section = handler[section_start:section_end]

        has_required = "required=True" in customer_section or "required" in customer_section
        assert has_required, (
            "customer_id Select must have required=True. "
            "A quote without a customer makes no sense."
        )

    def test_form_has_seller_company_id_select(self):
        """Form must contain a seller_company_id Select dropdown (optional)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_seller = 'name="seller_company_id"' in handler
        assert has_seller, (
            "Form must have a field with name='seller_company_id' for selecting the seller company."
        )

    def test_form_has_delivery_city_input(self):
        """Form must contain a delivery_city text input (optional)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_city = 'name="delivery_city"' in handler
        assert has_city, (
            "Form must have a field with name='delivery_city' for delivery city input."
        )

    def test_form_has_delivery_country_input(self):
        """Form must contain a delivery_country text input (optional)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_country = 'name="delivery_country"' in handler
        assert has_country, (
            "Form must have a field with name='delivery_country' for delivery country input."
        )

    def test_form_has_delivery_method_select(self):
        """Form must contain a delivery_method Select dropdown (optional)."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_method = 'name="delivery_method"' in handler
        assert has_method, (
            "Form must have a field with name='delivery_method' for delivery method selection."
        )

    def test_delivery_method_has_correct_options(self):
        """delivery_method Select must have the 4 standard delivery options in an Option() element."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        # Options must be inside Option() elements within the form (not in a map/dict elsewhere)
        has_option_elements = "Option(" in handler and 'name="delivery_method"' in handler
        assert has_option_elements, (
            "delivery_method must be a Select with Option() elements. "
            "Currently the GET handler has no form, so no Option elements exist."
        )

        # Additionally check for all 4 delivery method values
        expected_values = ['"air"', '"auto"', '"sea"', '"multimodal"']
        missing = [v for v in expected_values if v not in handler]
        assert not missing, (
            f"delivery_method Select is missing option values: {missing}. "
            "Must have: air, auto, sea, multimodal."
        )


# ============================================================================
# TEST 4: GET /quotes/new form buttons
# ============================================================================

class TestGetQuotesNewFormButtons:
    """GET /quotes/new form must have submit and cancel buttons."""

    def test_form_has_submit_button(self):
        """Form must have a submit button with text containing 'Создать КП'."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_submit = "Создать КП" in handler
        assert has_submit, (
            "Form must have a submit button with text 'Создать КП'."
        )

    def test_form_has_cancel_link(self):
        """Form must have a cancel link back to /quotes."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_cancel = (
            "Отмена" in handler
            and 'href="/quotes"' in handler
        )
        assert has_cancel, (
            "Form must have an 'Отмена' cancel link with href='/quotes' "
            "to navigate back to the quotes list."
        )


# ============================================================================
# TEST 5: POST /quotes/new handler must exist
# ============================================================================

class TestPostQuotesNewExists:
    """POST /quotes/new handler must exist and handle form submission."""

    def test_post_handler_exists(self):
        """POST /quotes/new handler (def post) must exist in main.py."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, (
            "POST /quotes/new handler (def post) not found in main.py. "
            "Currently only GET exists which auto-inserts. "
            "A POST handler must be created to handle form submission."
        )

    def test_post_handler_has_insert(self):
        """POST /quotes/new must contain .insert() call to create the quote."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        has_insert = ".insert(" in handler
        assert has_insert, (
            "POST /quotes/new must contain .insert() call to create the quote in DB."
        )

    def test_post_handler_generates_idn(self):
        """POST handler must generate idn_quote for the new quote."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        has_idn = "idn_quote" in handler
        assert has_idn, (
            "POST /quotes/new must generate idn_quote for the new quote."
        )


# ============================================================================
# TEST 6: POST /quotes/new handler parameters
# ============================================================================

class TestPostQuotesNewParameters:
    """POST /quotes/new must accept correct typed parameters."""

    def test_post_handler_accepts_customer_id(self):
        """POST handler must accept customer_id as a typed parameter."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        # Check function signature for customer_id with type annotation
        sig_match = re.search(r'def post\([^)]*customer_id\s*:\s*str', handler)
        assert sig_match is not None, (
            "POST handler must accept 'customer_id: str' as a typed parameter. "
            "FastHTML ignores parameters without type annotations."
        )

    def test_post_handler_accepts_seller_company_id(self):
        """POST handler must accept seller_company_id as a typed parameter."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        sig_match = re.search(r'def post\([^)]*seller_company_id\s*:\s*str', handler)
        assert sig_match is not None, (
            "POST handler must accept 'seller_company_id: str' as a typed parameter."
        )

    def test_post_handler_accepts_delivery_fields(self):
        """POST handler must accept delivery_city, delivery_country, delivery_method."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        # Check for all three delivery fields in the function signature area
        sig_end = handler.find("):", 0, 1000)  # function signature ends with ):
        if sig_end < 0:
            sig_end = 500
        sig_area = handler[:sig_end + 2]

        missing = []
        for field in ["delivery_city", "delivery_country", "delivery_method"]:
            if field not in sig_area:
                missing.append(field)

        assert not missing, (
            f"POST handler signature is missing parameters: {missing}. "
            "All form fields must be accepted as typed parameters."
        )


# ============================================================================
# TEST 7: POST /quotes/new redirect behavior
# ============================================================================

class TestPostQuotesNewRedirects:
    """POST /quotes/new must redirect correctly on success and on validation failure."""

    def test_post_success_redirects_to_quote_detail(self):
        """On success, POST must redirect to /quotes/{id}."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        has_redirect = (
            "RedirectResponse" in handler
            and 'f"/quotes/' in handler
        )
        assert has_redirect, (
            "POST /quotes/new must redirect to /quotes/{id} after successful creation. "
            "Use RedirectResponse(f'/quotes/{new_quote[\"id\"]}', status_code=303)."
        )

    def test_post_empty_customer_redirects_back(self):
        """When customer_id is empty, POST must redirect back to /quotes/new."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        # There should be a check for empty customer_id and redirect back
        has_validation = (
            "not customer_id" in handler or "customer_id ==" in handler or 'customer_id.strip()' in handler
        )
        has_redirect_back = '"/quotes/new"' in handler

        assert has_validation and has_redirect_back, (
            "POST /quotes/new must validate customer_id is not empty and redirect "
            "back to /quotes/new if it is. customer_id is required for quote creation."
        )


# ============================================================================
# TEST 8: POST /quotes/new authentication and security
# ============================================================================

class TestPostQuotesNewSecurity:
    """POST /quotes/new must check authentication and use org_id."""

    def test_post_handler_requires_login(self):
        """POST handler must require authentication."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        has_auth = "require_login" in handler
        assert has_auth, (
            "POST /quotes/new must call require_login(session) for authentication."
        )

    def test_post_handler_uses_organization_id(self):
        """POST handler must associate quote with user's organization."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "post")
        assert handler is not None, "POST /quotes/new handler not found"

        has_org = "organization_id" in handler or "org_id" in handler
        assert has_org, (
            "POST /quotes/new must set organization_id on the quote record."
        )


# ============================================================================
# TEST 9: GET /quotes/new fetches data for dropdowns
# ============================================================================

class TestGetQuotesNewFetchesData:
    """GET /quotes/new must fetch customers and seller companies for dropdowns."""

    def test_get_handler_fetches_customers(self):
        """GET handler must fetch customers for the dropdown."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_customers_fetch = (
            "get_all_customers" in handler
            or ('table("customers")' in handler and ".select(" in handler)
        )
        assert has_customers_fetch, (
            "GET /quotes/new must fetch customers for the dropdown. "
            "Use get_all_customers from services.customer_service or direct query."
        )

    def test_get_handler_fetches_seller_companies(self):
        """GET handler must fetch seller companies for the dropdown."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        has_seller_fetch = (
            "get_all_seller_companies" in handler
            or ('table("seller_companies")' in handler and ".select(" in handler)
        )
        assert has_seller_fetch, (
            "GET /quotes/new must fetch seller companies for the dropdown. "
            "Use get_all_seller_companies from services.seller_company_service."
        )


# ============================================================================
# TEST 10: Verify no accidental DB writes from GET
# ============================================================================

class TestNoAccidentalDbWrites:
    """GET /quotes/new must not write anything to the database."""

    def test_get_handler_has_no_table_mutations(self):
        """GET handler must not call .insert(), .update(), or .delete() on any table."""
        source = _read_main_source()
        handler = _get_handler_body(source, QUOTES_NEW_ROUTE, "get")
        assert handler is not None, "GET /quotes/new handler not found"

        mutations = []
        if ".insert(" in handler:
            mutations.append(".insert()")
        if ".update(" in handler:
            mutations.append(".update()")
        if ".delete(" in handler:
            mutations.append(".delete()")

        assert not mutations, (
            f"GET /quotes/new handler contains DB mutation calls: {mutations}. "
            "GET handlers must be read-only. Move all mutations to POST handler."
        )
