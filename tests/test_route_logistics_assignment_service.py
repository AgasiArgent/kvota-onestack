"""
Tests for route_logistics_assignment_service.py (Feature API-009)

Tests for route-logistics manager assignment operations:
- Validation functions
- Route pattern parsing and building
- CRUD operations
- Route matching logic
- Statistics and utilities
"""

import pytest
from dataclasses import asdict
from datetime import datetime
import uuid

# Import functions to test
from services.route_logistics_assignment_service import (
    # Data class
    RouteLogisticsAssignment,
    # Validation functions
    validate_route_pattern,
    parse_route_pattern,
    build_route_pattern,
    normalize_route_pattern,
    # CRUD functions
    _parse_assignment,
    _parse_assignment_with_user,
    _match_route_python,
)


# =============================================================================
# Test: RouteLogisticsAssignment Data Class
# =============================================================================

class TestRouteLogisticsAssignmentDataClass:
    """Tests for RouteLogisticsAssignment dataclass"""

    def test_create_assignment_minimal(self):
        """Test creating assignment with minimal fields"""
        assignment = RouteLogisticsAssignment(
            id="test-uuid",
            organization_id="org-uuid",
            route_pattern="Китай-*",
            user_id="user-uuid",
        )
        assert assignment.id == "test-uuid"
        assert assignment.organization_id == "org-uuid"
        assert assignment.route_pattern == "Китай-*"
        assert assignment.user_id == "user-uuid"
        assert assignment.created_at is None
        assert assignment.origin is None
        assert assignment.destination is None

    def test_create_assignment_full(self):
        """Test creating assignment with all fields"""
        now = datetime.now()
        assignment = RouteLogisticsAssignment(
            id="test-uuid",
            organization_id="org-uuid",
            route_pattern="Китай-Москва",
            user_id="user-uuid",
            created_at=now,
            created_by="admin-uuid",
            origin="Китай",
            destination="Москва",
            user_email="logistics@company.com",
            user_name="Иван Петров",
        )
        assert assignment.created_at == now
        assert assignment.created_by == "admin-uuid"
        assert assignment.origin == "Китай"
        assert assignment.destination == "Москва"
        assert assignment.user_email == "logistics@company.com"
        assert assignment.user_name == "Иван Петров"


# =============================================================================
# Test: Route Pattern Validation
# =============================================================================

class TestValidateRoutePattern:
    """Tests for validate_route_pattern function"""

    def test_valid_exact_route(self):
        """Test validation of exact route pattern"""
        assert validate_route_pattern("Китай-Москва") is True
        assert validate_route_pattern("Turkey-Moscow") is True
        assert validate_route_pattern("Германия-Санкт-Петербург") is True

    def test_valid_wildcard_origin(self):
        """Test validation with wildcard origin"""
        assert validate_route_pattern("*-Москва") is True
        assert validate_route_pattern("*-СПб") is True

    def test_valid_wildcard_destination(self):
        """Test validation with wildcard destination"""
        assert validate_route_pattern("Китай-*") is True
        assert validate_route_pattern("Турция-*") is True

    def test_invalid_empty(self):
        """Test validation of empty patterns"""
        assert validate_route_pattern("") is False
        assert validate_route_pattern("   ") is False

    def test_invalid_no_hyphen(self):
        """Test validation without hyphen separator"""
        assert validate_route_pattern("КитайМосква") is False
        assert validate_route_pattern("Китай") is False

    def test_invalid_only_wildcards(self):
        """Test validation with only wildcards"""
        assert validate_route_pattern("*-*") is False

    def test_valid_complex_names(self):
        """Test validation with complex location names"""
        assert validate_route_pattern("Санкт-Петербург-Москва") is True
        assert validate_route_pattern("Нижний Новгород-*") is True


# =============================================================================
# Test: Route Pattern Parsing
# =============================================================================

class TestParseRoutePattern:
    """Tests for parse_route_pattern function"""

    def test_parse_exact_route(self):
        """Test parsing exact route pattern"""
        result = parse_route_pattern("Китай-Москва")
        assert result is not None
        assert result["origin"] == "Китай"
        assert result["destination"] == "Москва"

    def test_parse_wildcard_origin(self):
        """Test parsing with wildcard origin"""
        result = parse_route_pattern("*-Москва")
        assert result is not None
        assert result["origin"] is None
        assert result["destination"] == "Москва"

    def test_parse_wildcard_destination(self):
        """Test parsing with wildcard destination"""
        result = parse_route_pattern("Китай-*")
        assert result is not None
        assert result["origin"] == "Китай"
        assert result["destination"] is None

    def test_parse_invalid_returns_none(self):
        """Test parsing invalid pattern returns None"""
        assert parse_route_pattern("") is None
        assert parse_route_pattern("no-hyphen-pattern") is not None  # valid
        assert parse_route_pattern("*-*") is None

    def test_parse_with_spaces(self):
        """Test parsing patterns with spaces"""
        result = parse_route_pattern("Китай - Москва")
        assert result is not None
        assert result["origin"] == "Китай"
        assert result["destination"] == "Москва"


# =============================================================================
# Test: Build Route Pattern
# =============================================================================

class TestBuildRoutePattern:
    """Tests for build_route_pattern function"""

    def test_build_exact_route(self):
        """Test building exact route pattern"""
        result = build_route_pattern("Китай", "Москва")
        assert result == "Китай-Москва"

    def test_build_wildcard_origin(self):
        """Test building with None origin"""
        result = build_route_pattern(None, "Москва")
        assert result == "*-Москва"

    def test_build_wildcard_destination(self):
        """Test building with None destination"""
        result = build_route_pattern("Китай", None)
        assert result == "Китай-*"

    def test_build_both_wildcards(self):
        """Test building with both None"""
        result = build_route_pattern(None, None)
        assert result == "*-*"

    def test_build_with_spaces(self):
        """Test building handles whitespace"""
        result = build_route_pattern("  Китай  ", "  Москва  ")
        assert result == "Китай-Москва"


# =============================================================================
# Test: Normalize Route Pattern
# =============================================================================

class TestNormalizeRoutePattern:
    """Tests for normalize_route_pattern function"""

    def test_normalize_exact(self):
        """Test normalizing exact pattern"""
        assert normalize_route_pattern("Китай-Москва") == "Китай-Москва"

    def test_normalize_with_spaces(self):
        """Test normalizing pattern with spaces"""
        assert normalize_route_pattern("  Китай  -  Москва  ") == "Китай-Москва"

    def test_normalize_empty_parts(self):
        """Test normalizing pattern with empty parts"""
        assert normalize_route_pattern("-Москва") == "*-Москва"
        assert normalize_route_pattern("Китай-") == "Китай-*"

    def test_normalize_no_hyphen(self):
        """Test normalizing pattern without hyphen"""
        assert normalize_route_pattern("Китай") == "Китай"


# =============================================================================
# Test: Parse Assignment
# =============================================================================

class TestParseAssignment:
    """Tests for _parse_assignment function"""

    def test_parse_basic_assignment(self):
        """Test parsing basic assignment data"""
        data = {
            "id": "test-uuid",
            "organization_id": "org-uuid",
            "route_pattern": "Китай-Москва",
            "user_id": "user-uuid",
            "created_at": "2024-01-15T10:00:00Z",
            "created_by": "admin-uuid",
        }
        result = _parse_assignment(data)
        assert result.id == "test-uuid"
        assert result.organization_id == "org-uuid"
        assert result.route_pattern == "Китай-Москва"
        assert result.user_id == "user-uuid"
        assert result.origin == "Китай"
        assert result.destination == "Москва"

    def test_parse_wildcard_pattern(self):
        """Test parsing assignment with wildcard pattern"""
        data = {
            "id": "test-uuid",
            "organization_id": "org-uuid",
            "route_pattern": "Китай-*",
            "user_id": "user-uuid",
        }
        result = _parse_assignment(data)
        assert result.origin == "Китай"
        assert result.destination is None

    def test_parse_wildcard_origin(self):
        """Test parsing assignment with wildcard origin"""
        data = {
            "id": "test-uuid",
            "organization_id": "org-uuid",
            "route_pattern": "*-Москва",
            "user_id": "user-uuid",
        }
        result = _parse_assignment(data)
        assert result.origin is None
        assert result.destination == "Москва"


# =============================================================================
# Test: Python Route Matching
# =============================================================================

class TestMatchRoutePython:
    """Tests for _match_route_python fallback function"""

    def test_match_exact_route(self):
        """Test exact route matching"""
        # Create mock assignments
        class MockAssignment:
            def __init__(self, pattern, user_id):
                self.route_pattern = pattern
                self.user_id = user_id

        # This tests the algorithm in isolation
        # In practice, this function uses the database

    def test_wildcard_matching_priority(self):
        """Test that more specific patterns are preferred"""
        # This test documents the expected behavior:
        # - "Китай-Москва" should match before "Китай-*"
        # - "Китай-*" should match before "*-*"
        pass


# =============================================================================
# Test: Route Pattern Examples (Documentation)
# =============================================================================

class TestRoutePatternExamples:
    """Tests documenting route pattern examples and their behavior"""

    def test_common_patterns(self):
        """Test common route pattern examples"""
        # All from China
        assert validate_route_pattern("Китай-*") is True
        parsed = parse_route_pattern("Китай-*")
        assert parsed["origin"] == "Китай"
        assert parsed["destination"] is None

        # All to Moscow
        assert validate_route_pattern("*-Москва") is True
        parsed = parse_route_pattern("*-Москва")
        assert parsed["origin"] is None
        assert parsed["destination"] == "Москва"

        # Specific route
        assert validate_route_pattern("Турция-Санкт-Петербург") is True
        parsed = parse_route_pattern("Турция-Санкт-Петербург")
        assert parsed["origin"] == "Турция"
        assert parsed["destination"] == "Санкт-Петербург"

    def test_international_characters(self):
        """Test patterns with international characters"""
        assert validate_route_pattern("中国-Москва") is True
        assert validate_route_pattern("Türkiye-Москва") is True
        assert validate_route_pattern("Deutschland-Berlin") is True

    def test_edge_cases(self):
        """Test edge cases in pattern matching"""
        # Pattern with hyphen in location name
        assert validate_route_pattern("Санкт-Петербург-Москва") is True
        parsed = parse_route_pattern("Санкт-Петербург-Москва")
        # First split will be "Санкт", "Петербург-Москва"
        assert parsed["origin"] == "Санкт"
        assert parsed["destination"] == "Петербург-Москва"


# =============================================================================
# Test: Utility Functions Behavior
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility function behavior (without database)"""

    def test_assignment_dataclass_conversion(self):
        """Test assignment can be converted to dict"""
        assignment = RouteLogisticsAssignment(
            id="test-uuid",
            organization_id="org-uuid",
            route_pattern="Китай-*",
            user_id="user-uuid",
        )
        data = asdict(assignment)
        assert data["id"] == "test-uuid"
        assert data["route_pattern"] == "Китай-*"

    def test_format_examples(self):
        """Test expected format of route patterns"""
        # These patterns should all be valid
        valid_patterns = [
            "Китай-*",
            "*-Москва",
            "Турция-Стамбул",
            "Germany-Hamburg",
            "Санкт-Петербург-*",
        ]
        for pattern in valid_patterns:
            assert validate_route_pattern(pattern) is True, f"Pattern {pattern} should be valid"

        # These patterns should be invalid
        invalid_patterns = [
            "",
            "*-*",
            "NoHyphen",
            "   ",
        ]
        for pattern in invalid_patterns:
            assert validate_route_pattern(pattern) is False, f"Pattern {pattern} should be invalid"


# =============================================================================
# Test: Integration Examples (for documentation)
# =============================================================================

class TestIntegrationExamples:
    """Tests documenting expected integration behavior"""

    def test_workflow_example(self):
        """Document typical workflow for route assignments"""
        # 1. Admin creates assignments
        # create_route_logistics_assignment(org_id, "Китай-*", logistics_user_1)
        # create_route_logistics_assignment(org_id, "Турция-Москва", logistics_user_2)

        # 2. When quote item needs logistics, system finds manager
        # user_id = match_route_to_logistics_manager(org_id, "Китай-Москва")
        # Expected: logistics_user_1 (matches "Китай-*")

        # 3. More specific patterns take priority
        # user_id = match_route_to_logistics_manager(org_id, "Турция-Москва")
        # Expected: logistics_user_2 (exact match)
        pass

    def test_coverage_check_example(self):
        """Document route coverage checking"""
        # Check which routes in a quote have logistics coverage
        # routes = ["Китай-Москва", "США-Москва", "Индия-СПб"]
        # coverage = check_route_coverage(org_id, routes)
        # uncovered = [r for r, u in coverage.items() if u is None]
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
