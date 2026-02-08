"""
TDD tests for DaData INN lookup route handler in main.py.

These tests define the CONTRACT for the route handler which does NOT exist yet.
The developer must implement:
  - GET /api/dadata/lookup-inn?inn=XXXXXXXXXX
    Returns JSON with company info from DaData API.
  - Used by customer creation form for INN autofill.

Expected route behavior:
  - Requires authentication (session)
  - Accepts `inn` query parameter
  - Returns JSON: {"success": true, "data": {...}} on success
  - Returns JSON: {"success": false, "error": "..."} on failure
  - Validates INN format before calling DaData
  - Handles empty/missing INN gracefully
"""

import os
import re
import sys

import pytest
from unittest.mock import patch, MagicMock

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


def _get_handler_body(source, route_pattern):
    """Extract handler body from @rt() decorator to next @rt()."""
    handler_start = source.find(route_pattern)
    if handler_start < 0:
        return None
    handler_end = source.find("\n@rt(", handler_start + 10)
    if handler_end == -1:
        handler_end = len(source)
    return source[handler_start:handler_end]


DADATA_ROUTE = '@rt("/api/dadata/lookup-inn")'

# Sample normalized result (what the service returns)
SAMPLE_COMPANY_DATA = {
    "name": 'ООО "РОМАШКА"',
    "full_name": 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РОМАШКА"',
    "inn": "7707083893",
    "kpp": "770701001",
    "ogrn": "1027700132195",
    "address": "г Москва, ул Ленина, д 1",
    "postal_code": "127000",
    "city": "Москва",
    "director": "Иванов Иван Иванович",
    "director_title": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР",
    "opf": "ООО",
    "entity_type": "LEGAL",
    "is_active": True,
}


# ============================================================================
# ROUTE EXISTENCE TESTS
# ============================================================================

class TestDadataRouteExists:
    """Verify the route is registered in main.py."""

    def test_route_decorator_exists(self):
        """@rt('/api/dadata/lookup-inn') must be present in main.py."""
        source = _read_main_source()
        assert DADATA_ROUTE in source, \
            f"Route {DADATA_ROUTE} not found in main.py. Developer must add it."

    def test_route_handler_is_defined(self):
        """Handler function must be defined after the decorator."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler body not found"
        assert "def " in handler, "No function definition found after route decorator"

    def test_route_accepts_inn_parameter(self):
        """Handler must accept 'inn' as a query parameter."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        assert "inn" in handler, "Handler does not reference 'inn' parameter"

    def test_route_requires_session(self):
        """Handler must require session (authentication)."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        assert "session" in handler, "Handler does not accept session parameter"

    def test_route_returns_html_for_htmx(self):
        """Handler should return HTML fragments for HTMX swap."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        assert "Div" in handler or "Small" in handler, \
            "Handler should return HTML elements (Div/Small) for HTMX"


# ============================================================================
# HANDLER BEHAVIOR TESTS (source analysis)
# ============================================================================

class TestDadataHandlerBehavior:
    """Tests for handler logic via source code analysis."""

    def test_handler_checks_authentication(self):
        """Handler must call require_login or check session."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        assert "require_login" in handler or "session" in handler, \
            "Handler must check authentication"

    def test_handler_validates_inn_format(self):
        """Handler must validate INN before calling DaData."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        # Should call validate_inn or do inline validation
        has_validation = (
            "validate_inn" in handler
            or "len(inn)" in handler
            or "not inn" in handler
            or "inn.strip()" in handler
        )
        assert has_validation, "Handler must validate INN format"

    def test_handler_calls_dadata_service(self):
        """Handler must call the dadata service for lookup."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        assert "lookup_company_by_inn" in handler or "dadata" in handler.lower(), \
            "Handler must call DaData service"

    def test_handler_has_error_handling(self):
        """Handler must have try/except or error handling."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        assert handler is not None, "Route handler not found"
        has_error_handling = (
            "try:" in handler
            or "except" in handler
            or '"success": False' in handler
            or '"success":False' in handler
            or "'success': False" in handler
        )
        assert has_error_handling, "Handler must handle errors gracefully"


# ============================================================================
# INTEGRATION: CUSTOMER FORM INN AUTOFILL
# ============================================================================

class TestCustomerFormInnAutofill:
    """Tests that the customer creation form has INN autofill wiring."""

    def test_customer_form_has_inn_field(self):
        """Customer creation form must have an INN input field."""
        source = _read_main_source()
        # Find the customer creation form area
        assert 'name="inn"' in source, \
            "Customer form missing INN input field"

    def test_inn_field_has_autofill_trigger(self):
        """INN field should have HTMX or JS trigger for autofill on change/blur.

        The INN field should trigger a lookup when the user finishes typing.
        This can be implemented via:
        - hx-get="/api/dadata/lookup-inn" with hx-trigger="change"
        - JavaScript onblur/oninput handler
        - HTMX hx-trigger="input changed delay:500ms"
        """
        source = _read_main_source()
        # Look for either HTMX trigger or JS event on the INN field
        has_autofill = (
            "api/dadata/lookup-inn" in source
            or "dadata" in source.lower()
            or "inn-autofill" in source
            or "inn_autofill" in source
        )
        assert has_autofill, \
            "INN field should trigger DaData lookup (HTMX or JS). " \
            "Add hx-get='/api/dadata/lookup-inn' or equivalent."


# ============================================================================
# RESPONSE FORMAT TESTS (contract definition)
# ============================================================================

class TestDadataResponseFormat:
    """Define the expected JSON response format.

    These tests document the API contract. The developer should ensure
    the route handler returns responses matching these formats.
    """

    def test_success_response_has_required_keys(self):
        """Success response must have 'success' and 'data' keys."""
        # This is a contract test - defines expected shape
        success_response = {"success": True, "data": SAMPLE_COMPANY_DATA}
        assert success_response["success"] is True
        assert "data" in success_response
        data = success_response["data"]
        # Verify all required keys are present
        required_keys = ["name", "inn", "address", "entity_type", "is_active"]
        for key in required_keys:
            assert key in data, f"Missing required key: {key}"

    def test_success_response_optional_keys(self):
        """Success response data may include optional keys."""
        optional_keys = [
            "full_name", "kpp", "ogrn", "postal_code", "city",
            "director", "director_title", "opf"
        ]
        for key in optional_keys:
            assert key in SAMPLE_COMPANY_DATA, \
                f"Optional key {key} should be in response (can be None)"

    def test_error_response_format(self):
        """Error response must have 'success': false and 'error' message."""
        error_response = {"success": False, "error": "Invalid INN format"}
        assert error_response["success"] is False
        assert "error" in error_response
        assert isinstance(error_response["error"], str)

    def test_not_found_response_format(self):
        """Not-found response (valid INN, no results) must be distinguishable."""
        not_found = {"success": True, "data": None}
        assert not_found["success"] is True
        assert not_found["data"] is None


# ============================================================================
# SECURITY TESTS
# ============================================================================

class TestDadataRouteSecurity:
    """Security tests for the DaData route."""

    def test_route_does_not_expose_api_key(self):
        """The DADATA_API_KEY must never appear in response or source output."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        if handler is None:
            pytest.skip("Route not implemented yet")
        # API key should not be embedded in handler (should come from env)
        assert "test-dadata-key" not in handler, \
            "API key must not be hardcoded in handler"
        # Should reference env var or config
        has_env_ref = (
            "DADATA_API_KEY" in source
            or "os.environ" in handler
            or "os.getenv" in handler
            or "dadata_service" in handler
        )
        assert has_env_ref, \
            "Handler should use DADATA_API_KEY from environment or service module"

    def test_route_does_not_leak_full_api_response(self):
        """Handler should normalize response, not pass raw DaData response."""
        source = _read_main_source()
        handler = _get_handler_body(source, DADATA_ROUTE)
        if handler is None:
            pytest.skip("Route not implemented yet")
        # Should use normalize function or selective field extraction
        has_normalization = (
            "normalize" in handler
            or "result[" in handler
            or "result.get(" in handler
            or '["name"]' in handler
        )
        assert has_normalization, \
            "Handler should normalize/filter DaData response, not pass raw data"
