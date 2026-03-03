"""
Tests for logistics auto-assignment when procurement completes.

Tests the new function assign_logistics_user_to_quote() in workflow_service.py
that auto-assigns a logistics manager to a quote based on supplier countries
in quote items, using route_logistics_assignment_service routing rules.

TDD: These tests are written BEFORE the implementation exists.
All tests should FAIL until the feature is implemented.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# TDD import: function does not exist yet. Import will succeed once implemented.
try:
    from services.workflow_service import assign_logistics_user_to_quote
except ImportError:
    assign_logistics_user_to_quote = None

from services.workflow_service import complete_procurement


def _require_function():
    """Assert that assign_logistics_user_to_quote exists. Fails with clear message in TDD."""
    assert assign_logistics_user_to_quote is not None, (
        "assign_logistics_user_to_quote() is not yet implemented in services/workflow_service.py"
    )


# =============================================================================
# CONSTANTS used across tests
# =============================================================================

QUOTE_ID = "quote-uuid-1234"
ORG_ID = "org-uuid-5678"
EKATERINA_ID = "ekaterina-uuid-001"
IVAN_ID = "ivan-uuid-002"
CATCHALL_ID = "catchall-uuid-003"


# =============================================================================
# HELPERS for building mock Supabase responses
# =============================================================================

class MockResponse:
    """Minimal mock for Supabase .execute() response."""
    def __init__(self, data=None):
        self.data = data


def make_mock_supabase(quote_data=None, items_data=None):
    """
    Build a mock supabase client that routes .table() calls to preset data.

    Args:
        quote_data: Data returned by supabase.table("quotes").select(...).single().execute()
        items_data: Data returned by supabase.table("quote_items").select(...).execute()
    """
    mock_sb = MagicMock()

    def table_router(table_name):
        builder = MagicMock()
        builder.select.return_value = builder
        builder.eq.return_value = builder
        builder.single.return_value = builder
        builder.update.return_value = builder
        builder.insert.return_value = builder

        if table_name == "quotes":
            builder.execute.return_value = MockResponse(data=quote_data)
        elif table_name == "quote_items":
            builder.execute.return_value = MockResponse(data=items_data)
        else:
            builder.execute.return_value = MockResponse(data=[])

        return builder

    mock_sb.table = MagicMock(side_effect=table_router)
    return mock_sb


# =============================================================================
# Test: assign_logistics_user_to_quote -- Unit Tests
# =============================================================================

class TestAssignLogisticsUserToQuote:
    """Unit tests for assign_logistics_user_to_quote function."""

    def test_happy_path_single_country_single_manager(self):
        """
        All items from same country -> correct manager assigned.

        Scenario: 3 items from China, routing rule maps China -> ekaterina.
        Expected: assigned_user_id = ekaterina, success = True.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=EKATERINA_ID, create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        assert "Китай" in result["countries_checked"]
        assert result["error_message"] is None

        # Routing should have been called once for the single unique country
        mock_routing.assert_called_once_with(
            organization_id=ORG_ID,
            origin_country="Китай",
            destination_city="Москва",
        )

    def test_mixed_countries_same_manager(self):
        """
        Mixed countries mapping to same manager (China + Taiwan -> ekaterina).

        Scenario: 2 items from China, 1 from Taiwan, both route to ekaterina.
        Expected: assigned_user_id = ekaterina, countries_checked includes both.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Тайвань"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        def routing_side_effect(organization_id, origin_country, destination_city):
            # Both China and Taiwan route to ekaterina
            return EKATERINA_ID

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   side_effect=routing_side_effect, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        assert set(result["countries_checked"]) == {"Китай", "Тайвань"}
        assert result["error_message"] is None

    def test_mixed_countries_different_managers_picks_most_items(self):
        """
        Items route to different managers -> pick one with most items.

        Scenario: 3 items from China (ekaterina), 1 from Turkey (ivan).
        Expected: ekaterina wins because she has more items.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Турция"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        def routing_side_effect(organization_id, origin_country, destination_city):
            if origin_country == "Китай":
                return EKATERINA_ID
            elif origin_country == "Турция":
                return IVAN_ID
            return None

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   side_effect=routing_side_effect, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        assert len(result["countries_checked"]) == 2

    def test_unknown_country_uses_catchall_manager(self):
        """
        Unknown country -> catch-all manager resolves.

        Scenario: Items from "Бразилия" (no specific rule), but "*-*" catch-all exists.
        Expected: routing service returns the catch-all manager.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Бразилия"},
            {"supplier_country": "Бразилия"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=CATCHALL_ID, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == CATCHALL_ID
        assert "Бразилия" in result["countries_checked"]

    def test_no_supplier_country_on_items_returns_success_no_assignment(self):
        """
        No supplier_country on items -> no assignment, success=True.

        Scenario: Items have null/empty supplier_country.
        Expected: success=True, assigned_user_id=None, countries_checked=[].
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": None},
            {"supplier_country": ""},
            {"supplier_country": "  "},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] is None
        assert result["countries_checked"] == []
        assert result["error_message"] is None
        # Routing should never be called if no countries to check
        mock_routing.assert_not_called()

    def test_no_items_returns_success_no_assignment(self):
        """
        Quote has no items at all -> success=True, no assignment.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = []  # No items
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] is None
        assert result["countries_checked"] == []
        mock_routing.assert_not_called()

    def test_no_delivery_city_still_works(self):
        """
        No delivery_city on quote -> still works (wildcard destination).

        Scenario: Quote has no delivery_city, routing uses None for destination.
        Expected: routing called with destination_city=None, assignment proceeds.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": None,  # No city set
        }
        items_data = [
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=EKATERINA_ID, create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        # Should be called with destination_city=None
        mock_routing.assert_called_once_with(
            organization_id=ORG_ID,
            origin_country="Китай",
            destination_city=None,
        )

    def test_no_routing_rules_returns_success_no_assignment(self):
        """
        No routing rules exist -> no assignment, success=True.

        Scenario: Routing service returns None for all countries.
        Expected: success=True, assigned_user_id=None, countries are still checked.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Турция"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=None, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] is None
        assert set(result["countries_checked"]) == {"Китай", "Турция"}
        assert result["error_message"] is None

    def test_routing_service_raises_exception_returns_failure(self):
        """
        Error in routing service -> success=False, error logged.

        Scenario: get_logistics_manager_for_locations raises an exception.
        Expected: success=False, error_message set.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   side_effect=Exception("DB connection error"), create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is False
        assert result["assigned_user_id"] is None
        assert result["error_message"] is not None
        assert "DB connection error" in result["error_message"]

    def test_quote_not_found_returns_failure(self):
        """
        Quote not found -> success=False.
        """
        _require_function()

        mock_sb = make_mock_supabase(quote_data=None, items_data=[])

        with patch("services.workflow_service.get_supabase", return_value=mock_sb):
            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is False
        assert result["assigned_user_id"] is None
        assert result["error_message"] is not None

    def test_quote_missing_organization_id_returns_failure(self):
        """
        Quote has no organization_id -> success=False.
        """
        _require_function()

        quote_data = {
            "organization_id": None,
            "delivery_city": "Москва",
        }
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=[])

        with patch("services.workflow_service.get_supabase", return_value=mock_sb):
            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is False
        assert "organization_id" in (result["error_message"] or "").lower()

    def test_writes_assigned_logistics_user_to_quotes_table(self):
        """
        After resolving manager, updates quotes.assigned_logistics_user.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=EKATERINA_ID, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        # Verify the quotes table was accessed at least twice (select + update)
        quotes_table_calls = [
            c for c in mock_sb.table.call_args_list if c[0][0] == "quotes"
        ]
        assert len(quotes_table_calls) >= 2, (
            "Expected at least 2 calls to quotes table (select + update), "
            f"got {len(quotes_table_calls)}"
        )

    def test_return_dict_shape(self):
        """
        Return value always has the expected keys.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = []
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb):
            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert "success" in result
        assert "assigned_user_id" in result
        assert "countries_checked" in result
        assert "error_message" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["countries_checked"], list)


# =============================================================================
# Test: Integration with complete_procurement()
# =============================================================================

class TestCompleteProcurementLogisticsIntegration:
    """
    Tests verifying that complete_procurement() calls
    assign_logistics_user_to_quote() as a best-effort step.
    """

    def _make_procurement_supabase(self):
        """
        Build a mock supabase that lets complete_procurement() pass its
        validation checks (role, status, all-items-complete).
        """
        mock_sb = MagicMock()

        def table_router(table_name):
            builder = MagicMock()
            builder.select.return_value = builder
            builder.eq.return_value = builder
            builder.neq.return_value = builder
            builder.single.return_value = builder
            builder.in_.return_value = builder
            builder.insert.return_value = builder
            builder.update.return_value = builder
            builder.order.return_value = builder
            builder.limit.return_value = builder

            if table_name == "quotes":
                builder.execute.return_value = MockResponse(data={
                    "id": QUOTE_ID,
                    "workflow_status": "pending_procurement",
                    "procurement_completed_at": None,
                })
            elif table_name == "workflow_transitions":
                builder.execute.return_value = MockResponse(data=[{"id": "transition-uuid"}])
            else:
                builder.execute.return_value = MockResponse(data=[])

            return builder

        mock_sb.table = MagicMock(side_effect=table_router)
        return mock_sb

    def test_complete_procurement_calls_assign_logistics(self):
        """
        Integration: complete_procurement() calls assign_logistics_user_to_quote.

        When procurement completes successfully, the logistics auto-assignment
        function should be called with the quote_id.
        """
        mock_sb = self._make_procurement_supabase()

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.check_all_procurement_complete",
                   return_value={"is_complete": True, "pending_items": 0, "total_items": 5}), \
             patch("services.workflow_service.assign_logistics_user_to_quote",
                   create=True) as mock_assign:

            mock_assign.return_value = {
                "success": True,
                "assigned_user_id": EKATERINA_ID,
                "countries_checked": ["Китай"],
                "error_message": None,
            }

            result = complete_procurement(
                quote_id=QUOTE_ID,
                actor_id="actor-uuid",
                actor_roles=["procurement"]
            )

        assert result.success is True
        mock_assign.assert_called_once_with(QUOTE_ID)

    def test_complete_procurement_succeeds_even_if_routing_raises(self):
        """
        Integration: complete_procurement() succeeds even if routing raises exception.

        Logistics auto-assignment is best-effort. If it raises an exception,
        complete_procurement() should still return success=True.
        """
        mock_sb = self._make_procurement_supabase()

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.check_all_procurement_complete",
                   return_value={"is_complete": True, "pending_items": 0, "total_items": 5}), \
             patch("services.workflow_service.assign_logistics_user_to_quote",
                   create=True) as mock_assign:

            # Simulate routing failure via exception
            mock_assign.side_effect = Exception("Routing service unavailable")

            result = complete_procurement(
                quote_id=QUOTE_ID,
                actor_id="actor-uuid",
                actor_roles=["procurement"]
            )

        # Procurement completion should succeed despite routing failure
        assert result.success is True
        assert result.to_status == "pending_logistics_and_customs"

    def test_complete_procurement_succeeds_when_routing_returns_failure(self):
        """
        Integration: complete_procurement() succeeds when routing returns success=False.

        Even when assign_logistics_user_to_quote returns success=False,
        the procurement completion should not be affected.
        """
        mock_sb = self._make_procurement_supabase()

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.check_all_procurement_complete",
                   return_value={"is_complete": True, "pending_items": 0, "total_items": 5}), \
             patch("services.workflow_service.assign_logistics_user_to_quote",
                   create=True) as mock_assign:

            mock_assign.return_value = {
                "success": False,
                "assigned_user_id": None,
                "countries_checked": [],
                "error_message": "Quote has no organization_id",
            }

            result = complete_procurement(
                quote_id=QUOTE_ID,
                actor_id="actor-uuid",
                actor_roles=["procurement"]
            )

        assert result.success is True


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestAssignLogisticsEdgeCases:
    """Additional edge cases for assign_logistics_user_to_quote."""

    def test_items_with_mixed_null_and_valid_countries(self):
        """
        Mix of null and valid supplier_country -> only valid ones checked.

        Scenario: 2 items with country, 1 with null, 1 with empty string.
        Expected: Only the 2 valid countries are checked.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": None},
            {"supplier_country": ""},
            {"supplier_country": "Турция"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        def routing_side_effect(organization_id, origin_country, destination_city):
            if origin_country == "Китай":
                return EKATERINA_ID
            elif origin_country == "Турция":
                return IVAN_ID
            return None

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   side_effect=routing_side_effect, create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        # Only 2 routing calls for valid countries
        assert mock_routing.call_count == 2
        assert set(result["countries_checked"]) == {"Китай", "Турция"}

    def test_duplicate_country_counted_correctly(self):
        """
        Multiple items from same country -> counted as one country, multiple items.

        Scenario: 5 items from China. Routing called once for China.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=EKATERINA_ID, create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        # Routing should be called once (deduplication by country)
        mock_routing.assert_called_once()

    def test_some_countries_have_no_routing_rule(self):
        """
        Some countries route to a manager, others return None.

        Scenario: China -> ekaterina, India -> None (no rule).
        Expected: Only ekaterina is assigned (the only match).
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "Китай"},
            {"supplier_country": "Китай"},
            {"supplier_country": "Индия"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        def routing_side_effect(organization_id, origin_country, destination_city):
            if origin_country == "Китай":
                return EKATERINA_ID
            return None  # India has no rule

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   side_effect=routing_side_effect, create=True):

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        assert result["assigned_user_id"] == EKATERINA_ID
        assert set(result["countries_checked"]) == {"Китай", "Индия"}

    def test_whitespace_in_country_names_stripped(self):
        """
        Whitespace in supplier_country values is stripped before processing.
        """
        _require_function()

        quote_data = {
            "organization_id": ORG_ID,
            "delivery_city": "Москва",
        }
        items_data = [
            {"supplier_country": "  Китай  "},
            {"supplier_country": "Китай"},
        ]
        mock_sb = make_mock_supabase(quote_data=quote_data, items_data=items_data)

        with patch("services.workflow_service.get_supabase", return_value=mock_sb), \
             patch("services.workflow_service.get_logistics_manager_for_locations",
                   return_value=EKATERINA_ID, create=True) as mock_routing:

            result = assign_logistics_user_to_quote(QUOTE_ID)

        assert result["success"] is True
        # Should be called once (both "  Китай  " and "Китай" normalize to "Китай")
        mock_routing.assert_called_once()
        assert result["countries_checked"] == ["Китай"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
