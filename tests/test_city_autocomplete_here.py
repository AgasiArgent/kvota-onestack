"""
TDD tests for replacing DaData city autocomplete with HERE Geocoding API.

These tests define the CONTRACT for the migration which does NOT exist yet.
The developer must implement:

1. New service: services/here_service.py with search_cities(query, count=10)
2. HERE API: https://geocode.search.hereapi.com/v1/geocode?q={query}&apiKey={key}&limit=10
3. International city coverage (not just Russia)
4. Return format: list of dicts with keys: city, region, country, display
5. Environment variable: HERE_API_KEY
6. Route /api/cities/search should use HERE instead of DaData
7. delivery_city fields on quote forms should have HTMX datalist autocomplete
8. Handle API errors gracefully (return empty list)
9. Min 2 chars query length

Tests use source-code analysis + mock-based unit testing.
"""

import os
import re
import pytest
from unittest.mock import patch, MagicMock
import httpx


# Set test environment
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("HERE_API_KEY", "test-here-api-key")


# ============================================================================
# SAMPLE HERE API RESPONSES
# ============================================================================

# HERE Autosuggest API returns this structure
SAMPLE_HERE_RESPONSE = {
    "items": [
        {
            "title": "Moscow, Russia",
            "id": "here:cm:namedplace:20002830",
            "resultType": "locality",
            "address": {
                "label": "Moscow, Russia",
                "city": "Moscow",
                "stateCode": "MOW",
                "state": "Moscow",
                "countryName": "Russia",
                "countryCode": "RUS",
            },
        },
        {
            "title": "Moscow, Idaho, United States",
            "id": "here:cm:namedplace:20071854",
            "resultType": "locality",
            "address": {
                "label": "Moscow, Idaho, United States",
                "city": "Moscow",
                "state": "Idaho",
                "stateCode": "ID",
                "countryName": "United States",
                "countryCode": "USA",
            },
        },
    ]
}

SAMPLE_HERE_RESPONSE_INTERNATIONAL = {
    "items": [
        {
            "title": "Beijing, China",
            "id": "here:cm:namedplace:20038980",
            "resultType": "locality",
            "address": {
                "label": "Beijing, China",
                "city": "Beijing",
                "state": "Beijing",
                "countryName": "China",
                "countryCode": "CHN",
            },
        },
        {
            "title": "Istanbul, Turkey",
            "id": "here:cm:namedplace:20014219",
            "resultType": "locality",
            "address": {
                "label": "Istanbul, Turkey",
                "city": "Istanbul",
                "state": "Istanbul",
                "countryName": "Turkey",
                "countryCode": "TUR",
            },
        },
        {
            "title": "Dubai, United Arab Emirates",
            "id": "here:cm:namedplace:20020478",
            "resultType": "locality",
            "address": {
                "label": "Dubai, United Arab Emirates",
                "city": "Dubai",
                "state": "Dubai",
                "countryName": "United Arab Emirates",
                "countryCode": "ARE",
            },
        },
    ]
}

SAMPLE_HERE_RESPONSE_SINGLE = {
    "items": [
        {
            "title": "Berlin, Germany",
            "id": "here:cm:namedplace:20187403",
            "resultType": "locality",
            "address": {
                "label": "Berlin, Germany",
                "city": "Berlin",
                "state": "Berlin",
                "countryName": "Germany",
                "countryCode": "DEU",
            },
        },
    ]
}

EMPTY_HERE_RESPONSE = {"items": []}


# ============================================================================
# HELPERS
# ============================================================================

def _read_main_source():
    """Read main.py source as a string."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.read()


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


CITY_SEARCH_ROUTE = '@rt("/api/cities/search")'


# ============================================================================
# TEST 1: services/here_service.py exists and has search_cities
# ============================================================================

class TestHereServiceExists:
    """services/here_service.py must exist with search_cities function."""

    def test_here_service_module_exists(self):
        """services/here_service.py must be importable."""
        try:
            import services.here_service
        except ImportError:
            pytest.fail(
                "Cannot import services.here_service. "
                "Create services/here_service.py with search_cities() function."
            )

    def test_search_cities_function_exists(self):
        """services.here_service must export search_cities function."""
        try:
            from services.here_service import search_cities
        except ImportError:
            pytest.fail(
                "Cannot import search_cities from services.here_service. "
                "Implement: def search_cities(query: str, count: int = 10) -> list[dict]"
            )

    def test_search_cities_signature(self):
        """search_cities must accept query and optional count parameter."""
        try:
            from services.here_service import search_cities
            import inspect
            sig = inspect.signature(search_cities)
            params = list(sig.parameters.keys())
            assert "query" in params, "search_cities must have 'query' parameter"
            assert "count" in params, "search_cities must have 'count' parameter"
        except ImportError:
            pytest.fail("Cannot import search_cities from services.here_service")


# ============================================================================
# TEST 2: search_cities() input validation
# ============================================================================

class TestHereCitySearchValidation:
    """Input validation before HERE API call."""

    def test_empty_query_returns_empty_list(self):
        """Empty query should return [] without calling API."""
        from services.here_service import search_cities
        result = search_cities("")
        assert result == []

    def test_none_query_returns_empty_list(self):
        """None query should return [] without calling API."""
        from services.here_service import search_cities
        result = search_cities(None)
        assert result == []

    def test_single_char_returns_empty_list(self):
        """Single character query should return [] (min 2 chars)."""
        from services.here_service import search_cities
        result = search_cities("M")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        """Whitespace-only query should return []."""
        from services.here_service import search_cities
        result = search_cities("   ")
        assert result == []

    def test_two_char_query_calls_api(self):
        """Query with 2+ chars should trigger API call."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            result = search_cities("Mo")
            mock_api.assert_called_once()


# ============================================================================
# TEST 3: search_cities() calls HERE API correctly
# ============================================================================

class TestHereApiCall:
    """Verify the HERE API is called with correct URL and parameters."""

    def test_calls_here_autosuggest_url(self):
        """Must call HERE Autosuggest endpoint, not DaData."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            search_cities("Moscow")

        mock_api.assert_called_once()
        call_args = mock_api.call_args
        # The query "Moscow" should be passed to the internal API call
        assert "Moscow" in str(call_args), "Query must be passed to HERE API"

    def test_uses_here_api_key_env_var(self):
        """Must use HERE_API_KEY environment variable for authentication."""
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "here_service.py"
        )
        if not os.path.exists(service_path):
            pytest.fail("services/here_service.py does not exist")

        with open(service_path, "r") as f:
            source = f.read()

        assert "HERE_API_KEY" in source, (
            "services/here_service.py must reference HERE_API_KEY environment variable"
        )

    def test_uses_result_type_city(self):
        """HERE API call must include resultTypes=city parameter."""
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "here_service.py"
        )
        if not os.path.exists(service_path):
            pytest.fail("services/here_service.py does not exist")

        with open(service_path, "r") as f:
            source = f.read()

        has_city_filter = (
            "resultTypes" in source
            or "resultType" in source
            or "city" in source.lower()
        )
        assert has_city_filter, (
            "HERE API call must filter by resultTypes=city"
        )

    def test_count_parameter_limits_results(self):
        """count parameter should limit number of results."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            search_cities("Moscow", count=5)

        call_args = mock_api.call_args
        # count/limit should be passed somehow
        assert "5" in str(call_args) or 5 in (call_args.args + tuple(call_args.kwargs.values())), (
            "count parameter must be forwarded to HERE API call"
        )


# ============================================================================
# TEST 4: search_cities() returns normalized format
# ============================================================================

class TestHereCityResultFormat:
    """Verify results are normalized to city/region/country/display format."""

    def test_returns_list_of_dicts(self):
        """search_cities must return a list of dicts."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            result = search_cities("Moscow")

        assert isinstance(result, list)
        assert len(result) == 2
        for item in result:
            assert isinstance(item, dict)

    def test_each_result_has_required_keys(self):
        """Each result must have: city, region, country, display."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            result = search_cities("Moscow")

        required_keys = ["city", "region", "country", "display"]
        for item in result:
            for key in required_keys:
                assert key in item, f"Result missing required key: {key}"

    def test_city_field_extracted_correctly(self):
        """city field should contain the city name from HERE response."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_SINGLE
            result = search_cities("Berlin")

        assert len(result) == 1
        assert result[0]["city"] == "Berlin"

    def test_country_field_extracted_correctly(self):
        """country field should contain the country name from HERE response."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_SINGLE
            result = search_cities("Berlin")

        assert result[0]["country"] == "Germany"

    def test_region_field_extracted(self):
        """region field should contain the state/region from HERE response."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            result = search_cities("Moscow")

        # Second result is Moscow, Idaho - should have region "Idaho"
        idaho_result = result[1]
        assert idaho_result["region"] == "Idaho"

    def test_display_field_for_city_with_region(self):
        """display should show 'City, Region, Country' or similar for disambiguation."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE
            result = search_cities("Moscow")

        # Two results: Moscow Russia and Moscow Idaho
        # Both should have distinguishing display strings
        displays = [r["display"] for r in result]
        assert len(set(displays)) == 2, (
            "Display strings for two different Moscow cities must be different"
        )

    def test_display_field_contains_country(self):
        """display field should contain country for international results."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_SINGLE
            result = search_cities("Berlin")

        display = result[0]["display"]
        assert "Germany" in display, (
            "Display string must include country name for international cities"
        )


# ============================================================================
# TEST 5: International coverage (not just Russia)
# ============================================================================

class TestHereInternationalCoverage:
    """HERE API provides international city search, not just Russian cities."""

    def test_returns_non_russian_cities(self):
        """search_cities must handle non-Russian cities correctly."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_INTERNATIONAL
            result = search_cities("Bei")

        assert len(result) >= 1
        countries = [r["country"] for r in result]
        # Should have at least one non-Russian country
        assert any(c != "Russia" and c != "Россия" for c in countries), (
            "HERE service must return international results (not just Russian)"
        )

    def test_chinese_city_parsed_correctly(self):
        """Chinese cities should be parsed from HERE response."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_INTERNATIONAL
            result = search_cities("Beijing")

        beijing = result[0]
        assert beijing["city"] == "Beijing"
        assert beijing["country"] == "China"

    def test_multiple_countries_in_results(self):
        """A broad query should return cities from multiple countries."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = SAMPLE_HERE_RESPONSE_INTERNATIONAL
            result = search_cities("B")  # Would match Beijing, Berlin, etc.

        countries = set(r["country"] for r in result)
        assert len(countries) >= 2, (
            f"Expected cities from multiple countries, got: {countries}"
        )


# ============================================================================
# TEST 6: Error handling
# ============================================================================

class TestHereErrorHandling:
    """HERE API errors should be handled gracefully."""

    def test_network_error_returns_empty_list(self):
        """Network errors should return [] not raise."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.side_effect = ConnectionError("Network unreachable")
            result = search_cities("Moscow")

        assert result == []

    def test_timeout_returns_empty_list(self):
        """Timeout should return [] not raise."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.side_effect = httpx.TimeoutException("timeout")
            result = search_cities("Moscow")

        assert result == []

    def test_http_error_returns_empty_list(self):
        """HTTP errors (401, 429, 500) should return []."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.side_effect = RuntimeError("HTTP 429 Too Many Requests")
            result = search_cities("Moscow")

        assert result == []

    def test_malformed_response_returns_empty_list(self):
        """Malformed JSON responses should return []."""
        from services.here_service import search_cities

        with patch("services.here_service._call_here_api") as mock_api:
            mock_api.return_value = {"unexpected": "format"}
            result = search_cities("Moscow")

        assert result == []

    def test_missing_api_key_returns_empty_or_raises(self):
        """Missing HERE_API_KEY should be handled (not crash silently)."""
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "here_service.py"
        )
        if not os.path.exists(service_path):
            pytest.fail("services/here_service.py does not exist")

        with open(service_path, "r") as f:
            source = f.read()

        # Service should check for API key
        has_key_check = (
            "HERE_API_KEY" in source
            and ("not " in source or "raise" in source or '""' in source)
        )
        assert has_key_check, (
            "Service must validate that HERE_API_KEY is configured"
        )


# ============================================================================
# TEST 7: /api/cities/search route uses HERE instead of DaData
# ============================================================================

class TestCitySearchRouteUsesHere:
    """/api/cities/search route must import from here_service, not dadata_service."""

    def test_route_imports_here_service(self):
        """The route handler must import from services.here_service."""
        source = _read_main_source()
        handler = _get_handler_body(source, CITY_SEARCH_ROUTE)
        assert handler is not None, "/api/cities/search route not found"

        has_here_import = (
            "here_service" in handler
            or "from services.here_service" in handler
        )
        assert has_here_import, (
            "/api/cities/search route still imports from dadata_service. "
            "Change to: from services.here_service import search_cities"
        )

    def test_route_does_not_import_dadata_for_cities(self):
        """The route handler should NOT import search_cities from dadata_service."""
        source = _read_main_source()
        handler = _get_handler_body(source, CITY_SEARCH_ROUTE)
        assert handler is not None, "/api/cities/search route not found"

        has_dadata_city_import = (
            "dadata_service import search_cities" in handler
            or "from services.dadata_service import search_cities" in handler
        )
        assert not has_dadata_city_import, (
            "/api/cities/search still imports search_cities from dadata_service. "
            "Replace with import from services.here_service."
        )

    def test_route_still_returns_html_options(self):
        """Route must still return HTML <option> elements for HTMX datalist."""
        source = _read_main_source()
        handler = _get_handler_body(source, CITY_SEARCH_ROUTE)
        assert handler is not None, "/api/cities/search route not found"

        has_option_output = "Option(" in handler or "option" in handler.lower()
        assert has_option_output, (
            "/api/cities/search must return HTML Option elements for datalist"
        )

    def test_route_still_requires_auth(self):
        """Route must still require authentication."""
        source = _read_main_source()
        handler = _get_handler_body(source, CITY_SEARCH_ROUTE)
        assert handler is not None, "/api/cities/search route not found"

        assert "require_login" in handler or "session" in handler[:200], (
            "/api/cities/search must require authentication"
        )


# ============================================================================
# TEST 8: Quote forms have HTMX city autocomplete
# ============================================================================

class TestQuoteFormsCityAutocomplete:
    """delivery_city fields on quote forms should use HTMX datalist for autocomplete."""

    def test_quote_detail_delivery_city_has_autocomplete(self):
        """Quote detail page delivery_city input should have HTMX autocomplete via datalist.

        Currently the field is a plain text input with hx_patch for inline editing.
        It should ALSO have a datalist for city autocomplete, connected to /api/cities/search.
        """
        source = _read_main_source()

        # Find the delivery_city input and check the surrounding context
        # for datalist / hx_get wiring (within ~20 lines of the input)
        lines = source.splitlines()
        found_autocomplete = False
        for i, line in enumerate(lines):
            if 'name="delivery_city"' in line:
                # Check surrounding context (20 lines before and after)
                context = "\n".join(lines[max(0, i - 20):i + 20])
                if "cities/search" in context and ("list=" in context or "datalist" in context.lower()):
                    found_autocomplete = True
                    break

        assert found_autocomplete, (
            "delivery_city input on quote detail page must have HTMX autocomplete "
            "connected to /api/cities/search via a datalist element. "
            "Currently it's a plain text input without autocomplete."
        )

    def test_quote_edit_form_delivery_city_has_autocomplete(self):
        """Quote edit form delivery_city should also have HTMX autocomplete."""
        source = _read_main_source()

        # Find the quote edit form handler
        edit_handler = _get_handler_body(source, '@rt("/quotes/{quote_id}/edit")')
        if edit_handler is None:
            pytest.skip("Quote edit route not found")

        # Look for delivery_city with autocomplete in the GET handler
        # (the form rendering part, not the POST handler)
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if '@rt("/quotes/{quote_id}/edit")' in line:
                for j in range(i + 1, min(i + 5, len(lines))):
                    if "def get(" in lines[j]:
                        # Found GET edit handler - extract body
                        handler_lines = []
                        for k in range(i, len(lines)):
                            if k > i and lines[k].strip().startswith("@rt("):
                                break
                            handler_lines.append(lines[k])
                        get_handler = "\n".join(handler_lines)

                        has_city_autocomplete = (
                            "delivery_city" in get_handler
                            and ("datalist" in get_handler.lower() or "cities/search" in get_handler)
                        )
                        assert has_city_autocomplete, (
                            "Quote edit form delivery_city field must have HTMX autocomplete "
                            "connected to /api/cities/search."
                        )
                        return

        pytest.fail("Quote edit GET handler not found")

    def test_datalist_element_exists_for_city(self):
        """A dedicated datalist element for city autocomplete must exist near delivery_city inputs."""
        source = _read_main_source()

        # Check that there's a datalist specifically for cities (not for suppliers/companies)
        # Look for a datalist with "city" or "cities" in its id
        has_city_datalist = (
            'id="cities-datalist"' in source
            or 'id="city-list"' in source
            or 'id="city-datalist"' in source
            or 'id="datalist-delivery-city"' in source
        )
        assert has_city_datalist, (
            "Must have a dedicated datalist element for city autocomplete "
            "(e.g., id='cities-datalist'). Existing datalists are for suppliers/companies, "
            "not for city search."
        )


# ============================================================================
# TEST 9: HERE API key not hardcoded
# ============================================================================

class TestHereApiKeySecurity:
    """HERE_API_KEY must not be hardcoded."""

    def test_api_key_not_in_source(self):
        """HERE API key must come from environment, not hardcoded."""
        service_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "services", "here_service.py"
        )
        if not os.path.exists(service_path):
            pytest.fail("services/here_service.py does not exist")

        with open(service_path, "r") as f:
            source = f.read()

        # Should use os.environ or os.getenv
        has_env_ref = (
            "os.environ" in source
            or "os.getenv" in source
        )
        assert has_env_ref, (
            "HERE_API_KEY must be read from environment (os.environ/os.getenv), "
            "not hardcoded."
        )

    def test_api_key_not_in_main_py(self):
        """main.py should not contain HERE_API_KEY value."""
        source = _read_main_source()
        assert "test-here-api-key" not in source, (
            "HERE API key value must not appear in main.py"
        )
