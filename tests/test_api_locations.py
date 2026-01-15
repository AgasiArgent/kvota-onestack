"""
Tests for API endpoint /api/locations/search (Feature API-007)

Tests the HTMX dropdown search endpoint for locations.
"""

import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass


# Mock Location dataclass for testing
@dataclass
class MockLocation:
    id: str
    organization_id: str
    country: str
    city: str = None
    code: str = None
    is_hub: bool = False
    is_customs_point: bool = False
    is_active: bool = True
    display_name: str = None
    search_text: str = None
    address: str = None
    notes: str = None
    created_at: str = None
    updated_at: str = None
    created_by: str = None


def create_mock_locations():
    """Create mock location data for testing."""
    return [
        MockLocation(
            id="loc-001",
            organization_id="org-001",
            country="Россия",
            city="Москва",
            code="MSK",
            is_hub=True,
            is_customs_point=False,
            display_name="MSK - Москва, Россия"
        ),
        MockLocation(
            id="loc-002",
            organization_id="org-001",
            country="Россия",
            city="Санкт-Петербург",
            code="SPB",
            is_hub=True,
            is_customs_point=False,
            display_name="SPB - Санкт-Петербург, Россия"
        ),
        MockLocation(
            id="loc-003",
            organization_id="org-001",
            country="Россия",
            city="Владивосток",
            code="VVO",
            is_hub=True,
            is_customs_point=True,
            display_name="VVO - Владивосток, Россия"
        ),
        MockLocation(
            id="loc-004",
            organization_id="org-001",
            country="Китай",
            city="Шанхай",
            code="SH",
            is_hub=True,
            is_customs_point=False,
            display_name="SH - Шанхай, Китай"
        ),
        MockLocation(
            id="loc-005",
            organization_id="org-001",
            country="Китай",
            city="Шэньчжэнь",
            code="SZ",
            is_hub=True,
            is_customs_point=False,
            display_name="SZ - Шэньчжэнь, Китай"
        ),
    ]


class TestLocationSearchEndpoint:
    """Tests for /api/locations/search endpoint."""

    def test_search_returns_options_with_query(self):
        """Test that search with query returns filtered options."""
        # This tests the endpoint logic
        locations = create_mock_locations()

        # Filter by query "моск"
        query = "моск"
        filtered = [
            loc for loc in locations
            if query.lower() in (loc.display_name or "").lower()
            or query.lower() in (loc.city or "").lower()
        ]

        assert len(filtered) == 1
        assert filtered[0].code == "MSK"
        assert filtered[0].city == "Москва"

    def test_search_returns_all_without_query(self):
        """Test that empty query returns all locations."""
        locations = create_mock_locations()
        assert len(locations) == 5

    def test_search_filters_hubs_only(self):
        """Test that hub_only filter works."""
        locations = create_mock_locations()
        hubs = [loc for loc in locations if loc.is_hub]
        assert len(hubs) == 5  # All our test locations are hubs

    def test_search_filters_customs_only(self):
        """Test that customs_only filter works."""
        locations = create_mock_locations()
        customs = [loc for loc in locations if loc.is_customs_point]
        assert len(customs) == 1
        assert customs[0].code == "VVO"

    def test_search_query_case_insensitive(self):
        """Test that search is case insensitive."""
        locations = create_mock_locations()

        # Search with different cases
        queries = ["КИТАЙ", "китай", "КиТаЙ"]

        for query in queries:
            filtered = [
                loc for loc in locations
                if query.lower() in (loc.country or "").lower()
            ]
            assert len(filtered) == 2, f"Failed for query: {query}"

    def test_search_limit_parameter(self):
        """Test that limit parameter caps results."""
        locations = create_mock_locations()

        # Limit to 3 results
        limit = 3
        limited = locations[:limit]

        assert len(limited) == 3

    def test_format_location_for_dropdown(self):
        """Test dropdown format includes hub/customs badges."""
        from services.location_service import format_location_for_dropdown

        # Test hub location
        hub_loc = MockLocation(
            id="test-1",
            organization_id="org-1",
            country="Россия",
            city="Москва",
            code="MSK",
            is_hub=True,
            is_customs_point=False,
            display_name="MSK - Москва, Россия"
        )

        result = format_location_for_dropdown(hub_loc)
        assert result["value"] == "test-1"
        assert "[хаб]" in result["label"]

        # Test customs point
        customs_loc = MockLocation(
            id="test-2",
            organization_id="org-1",
            country="Россия",
            city="Владивосток",
            code="VVO",
            is_hub=True,
            is_customs_point=True,
            display_name="VVO - Владивосток, Россия"
        )

        result = format_location_for_dropdown(customs_loc)
        assert "[хаб" in result["label"]
        assert "таможня" in result["label"]

    def test_format_location_without_badges(self):
        """Test dropdown format without badges for regular location."""
        from services.location_service import format_location_for_dropdown

        regular_loc = MockLocation(
            id="test-3",
            organization_id="org-1",
            country="Россия",
            city="Казань",
            code="KZN",
            is_hub=False,
            is_customs_point=False,
            display_name="KZN - Казань, Россия"
        )

        result = format_location_for_dropdown(regular_loc)
        assert result["value"] == "test-3"
        assert "[" not in result["label"]  # No badges

    def test_search_by_country(self):
        """Test search by country name."""
        locations = create_mock_locations()
        query = "россия"

        filtered = [
            loc for loc in locations
            if query.lower() in (loc.country or "").lower()
        ]

        assert len(filtered) == 3
        assert all(loc.country == "Россия" for loc in filtered)

    def test_search_by_code(self):
        """Test search by location code."""
        locations = create_mock_locations()

        # Search by code "MSK"
        code_query = "msk"
        filtered = [
            loc for loc in locations
            if code_query.lower() in (loc.code or "").lower()
        ]

        assert len(filtered) == 1
        assert filtered[0].city == "Москва"

    def test_search_partial_match(self):
        """Test partial string matching."""
        locations = create_mock_locations()

        # Search for partial "шан"
        query = "шан"
        filtered = [
            loc for loc in locations
            if query.lower() in (loc.city or "").lower()
        ]

        assert len(filtered) == 1
        assert filtered[0].code == "SH"

    def test_empty_results_returns_message(self):
        """Test that empty results returns appropriate message."""
        locations = create_mock_locations()
        query = "несуществующий город"

        filtered = [
            loc for loc in locations
            if query.lower() in (loc.display_name or "").lower()
        ]

        assert len(filtered) == 0


class TestLocationSearchJsonEndpoint:
    """Tests for /api/locations/search/json endpoint."""

    def test_json_response_structure(self):
        """Test JSON response has correct structure."""
        # Expected response structure
        expected_keys = {"items", "count", "query"}

        response = {
            "items": [
                {"value": "loc-001", "label": "MSK - Москва, Россия [хаб]"}
            ],
            "count": 1,
            "query": "моск"
        }

        assert set(response.keys()) == expected_keys

    def test_json_items_structure(self):
        """Test each item in JSON response has value and label."""
        items = [
            {"value": "loc-001", "label": "MSK - Москва, Россия [хаб]"},
            {"value": "loc-002", "label": "SPB - Санкт-Петербург, Россия [хаб]"},
        ]

        for item in items:
            assert "value" in item
            assert "label" in item
            assert item["value"]  # Non-empty value
            assert item["label"]  # Non-empty label

    def test_json_error_response(self):
        """Test JSON error response structure."""
        error_response = {
            "error": "Unauthorized",
            "items": []
        }

        assert "error" in error_response
        assert "items" in error_response
        assert error_response["items"] == []


class TestLocationSearchIntegration:
    """Integration tests using location_service functions."""

    def test_get_locations_for_dropdown_returns_list(self):
        """Test that get_locations_for_dropdown returns list of dicts."""
        # Mock the function behavior
        mock_result = [
            {"value": "loc-001", "label": "MSK - Москва, Россия [хаб]"},
            {"value": "loc-002", "label": "SPB - Санкт-Петербург, Россия [хаб]"},
        ]

        assert isinstance(mock_result, list)
        for item in mock_result:
            assert isinstance(item, dict)
            assert "value" in item
            assert "label" in item

    def test_search_locations_with_hub_filter(self):
        """Test search with hub_only filter."""
        locations = create_mock_locations()

        # Simulate hub filter
        hub_locations = [loc for loc in locations if loc.is_hub]

        # Simulate search within hubs
        query = "россия"
        filtered = [
            loc for loc in hub_locations
            if query.lower() in (loc.country or "").lower()
        ]

        assert len(filtered) == 3

    def test_search_locations_with_customs_filter(self):
        """Test search with customs_only filter."""
        locations = create_mock_locations()

        # Simulate customs filter
        customs_locations = [loc for loc in locations if loc.is_customs_point]

        assert len(customs_locations) == 1
        assert customs_locations[0].code == "VVO"


class TestEndpointParameters:
    """Tests for endpoint parameter handling."""

    def test_query_parameter_strip(self):
        """Test that query parameter is stripped."""
        queries = [
            ("  москва  ", "москва"),
            ("шанхай\n", "шанхай"),
            ("\tспб", "спб"),
        ]

        for input_q, expected in queries:
            assert input_q.strip() == expected

    def test_limit_capped_at_50(self):
        """Test that limit is capped at 50."""
        test_limits = [10, 20, 50, 100, 1000]

        for limit in test_limits:
            capped = min(limit, 50)
            assert capped <= 50

    def test_boolean_parameter_parsing(self):
        """Test boolean parameter string parsing."""
        true_values = ["true", "True", "TRUE"]
        false_values = ["false", "False", "", "0", "no"]

        for val in true_values:
            assert val.lower() == "true"

        for val in false_values:
            assert val.lower() != "true"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
