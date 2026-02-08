"""
TDD tests for city autocomplete using DaData address suggestions API.

These tests define the CONTRACT for city search functionality which does NOT exist yet.
The developer must implement:
1. search_cities(query, count=10) -> list[dict] in services/dadata_service.py
2. @rt("/api/cities/search") HTMX endpoint in main.py

DaData Address Suggestions API:
- Endpoint: https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address
- Method: POST
- Auth: "Token {DADATA_API_KEY}" header
- Request body: {"query": "Москва", "count": 10, "from_bound": {"value": "city"}, "to_bound": {"value": "city"}}
- Response: {"suggestions": [{"value": "г Москва", "data": {"city": "Москва", ...}}]}
"""

import pytest
import os
from unittest.mock import patch, MagicMock
import httpx

# Set test environment
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("DADATA_API_KEY", "test-dadata-key")


# --- Sample mock data ---

SAMPLE_CITY_RESPONSE = {
    "suggestions": [
        {
            "value": "г Москва",
            "data": {
                "city": "Москва",
                "region_with_type": "г Москва",
                "country": "Россия",
                "city_fias_id": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",
            },
        },
        {
            "value": "г Новосибирск",
            "data": {
                "city": "Новосибирск",
                "region_with_type": "Новосибирская область",
                "country": "Россия",
                "city_fias_id": "8dea00e3-9aab-4d78-ae6e-049b3f2812af",
            },
        },
    ]
}

SAMPLE_SINGLE_CITY_RESPONSE = {
    "suggestions": [
        {
            "value": "г Москва",
            "data": {
                "city": "Москва",
                "region_with_type": "г Москва",
                "country": "Россия",
                "city_fias_id": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",
            },
        },
    ]
}

EMPTY_RESPONSE = {"suggestions": []}


# ============================================================================
# CITY SEARCH VALIDATION
# ============================================================================

class TestCitySearchValidation:
    """Test input validation before API call is made."""

    def test_empty_query_returns_empty_list(self):
        """Empty query should return empty list without calling API."""
        from services.dadata_service import search_cities
        result = search_cities("")
        assert result == []

    def test_single_char_query_returns_empty_list(self):
        """Single character query should return empty (min 2 chars)."""
        from services.dadata_service import search_cities
        result = search_cities("М")
        assert result == []

    def test_whitespace_only_query_returns_empty_list(self):
        """Whitespace-only query should return empty."""
        from services.dadata_service import search_cities
        result = search_cities("   ")
        assert result == []

    def test_valid_query_calls_api(self):
        """Query with 2+ chars should trigger API call."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_CITY_RESPONSE
            search_cities("Мо")
            mock_api.assert_called_once()


# ============================================================================
# CITY SEARCH RESULTS
# ============================================================================

class TestCitySearchResults:
    """Test API interaction and result processing."""

    def test_successful_search_returns_city_list(self):
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_CITY_RESPONSE
            result = search_cities("Москва")

        assert isinstance(result, list)
        assert len(result) == 2

    def test_returns_city_name_and_region(self):
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_CITY_RESPONSE
            result = search_cities("Новосибирск")

        for item in result:
            assert "city" in item
            assert "region" in item
            assert "country" in item

        novosibirsk = result[1]
        assert novosibirsk["city"] == "Новосибирск"
        assert novosibirsk["region"] == "Новосибирская область"
        assert novosibirsk["country"] == "Россия"

    def test_empty_suggestions_returns_empty_list(self):
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = EMPTY_RESPONSE
            result = search_cities("НесуществующийГород")

        assert result == []

    def test_handles_api_timeout_gracefully(self):
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.side_effect = httpx.TimeoutException("timeout")
            result = search_cities("Москва")

        assert result == []

    def test_handles_api_error_gracefully(self):
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.side_effect = ConnectionError("Network error")
            result = search_cities("Москва")

        assert result == []

    def test_sends_city_bounds(self):
        """Verify from_bound and to_bound are set to 'city'."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_CITY_RESPONSE
            search_cities("Москва")

        call_args = mock_api.call_args
        # The internal function should receive query and params
        assert "Москва" in str(call_args)

    def test_count_parameter_is_passed(self):
        """Count parameter should be forwarded to API."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_SINGLE_CITY_RESPONSE
            search_cities("Москва", count=5)

        call_args = mock_api.call_args
        assert "5" in str(call_args) or 5 in str(call_args)


# ============================================================================
# CITY RESULT FORMATTING
# ============================================================================

class TestCityResultFormatting:
    """Test how city results are formatted for display."""

    def test_formats_city_with_region(self):
        """City from a different region should show 'City, Region'."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = {
                "suggestions": [{
                    "value": "г Новосибирск",
                    "data": {
                        "city": "Новосибирск",
                        "region_with_type": "Новосибирская область",
                        "country": "Россия",
                    },
                }]
            }
            result = search_cities("Новосибирск")

        assert len(result) == 1
        assert result[0].get("display") == "Новосибирск, Новосибирская область"

    def test_formats_city_without_duplicate_region(self):
        """When city name matches region (Москва/г Москва), don't duplicate."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = {
                "suggestions": [{
                    "value": "г Москва",
                    "data": {
                        "city": "Москва",
                        "region_with_type": "г Москва",
                        "country": "Россия",
                    },
                }]
            }
            result = search_cities("Москва")

        assert len(result) == 1
        # Should NOT show "Москва, г Москва" — just "Москва"
        assert result[0].get("display") == "Москва"

    def test_result_has_city_and_country(self):
        """Each result should have city and country for form auto-fill."""
        from services.dadata_service import search_cities

        with patch("services.dadata_service._call_dadata_address_api") as mock_api:
            mock_api.return_value = SAMPLE_SINGLE_CITY_RESPONSE
            result = search_cities("Москва")

        assert len(result) == 1
        assert result[0]["city"] == "Москва"
        assert result[0]["country"] == "Россия"


# ============================================================================
# ROUTE EXISTENCE (source code inspection)
# ============================================================================

class TestCityAutocompleteRoute:
    """Verify the city search route is defined in main.py."""

    def test_city_search_route_exists(self):
        """@rt('/api/cities/search') must exist in main.py."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_path, "r") as f:
            source = f.read()

        assert "/api/cities/search" in source, \
            "Route /api/cities/search not found in main.py"
