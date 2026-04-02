"""
Tests for Procurement Routing with Sales Group -> Brand Cascade.

Tests cover:
1. Service CRUD (route_procurement_assignment_service):
   - ProcurementGroupAssignment dataclass
   - create_assignment, get_assignment, get_all_assignments
   - get_procurement_user_for_group, get_group_mapping
   - upsert_assignment, update_assignment, delete_assignment

2. Cascade logic in workflow_service.assign_procurement_users_to_quote():
   - Priority 1: Sales group routing (all items get same user)
   - Priority 2: Brand fallback (existing brand_assignments logic)
   - No match -> items stay unassigned

TDD: Tests written BEFORE implementation.
"""

import pytest
from unittest.mock import patch, MagicMock, call
from uuid import uuid4
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    return str(uuid4())


@pytest.fixture
def sales_group_id():
    return str(uuid4())


@pytest.fixture
def quote_id():
    return str(uuid4())


@pytest.fixture
def procurement_user_id():
    """Procurement user assigned via sales group routing."""
    return str(uuid4())


@pytest.fixture
def procurement_user_brand_a():
    """Procurement user assigned to brand A via brand_assignments."""
    return str(uuid4())


@pytest.fixture
def procurement_user_brand_b():
    """Procurement user assigned to brand B via brand_assignments."""
    return str(uuid4())


@pytest.fixture
def sales_user_id():
    """Sales manager who created the quote."""
    return str(uuid4())


@pytest.fixture
def admin_user_id():
    return str(uuid4())


@pytest.fixture
def item_id_1():
    return str(uuid4())


@pytest.fixture
def item_id_2():
    return str(uuid4())


@pytest.fixture
def item_id_3():
    return str(uuid4())


# =============================================================================
# TEST GROUP 1: Service CRUD — ProcurementGroupAssignment dataclass
# =============================================================================

class TestProcurementGroupAssignmentDataclass:
    """Tests for ProcurementGroupAssignment dataclass."""

    def test_create_minimal(self, org_id, sales_group_id, procurement_user_id):
        """Can create with minimal fields."""
        from services.route_procurement_assignment_service import ProcurementGroupAssignment

        assignment = ProcurementGroupAssignment(
            id="test-uuid",
            organization_id=org_id,
            sales_group_id=sales_group_id,
            user_id=procurement_user_id,
        )
        assert assignment.id == "test-uuid"
        assert assignment.organization_id == org_id
        assert assignment.sales_group_id == sales_group_id
        assert assignment.user_id == procurement_user_id
        assert assignment.created_at is None
        assert assignment.created_by is None

    def test_create_full(self, org_id, sales_group_id, procurement_user_id, admin_user_id):
        """Can create with all fields including optional."""
        from services.route_procurement_assignment_service import ProcurementGroupAssignment

        now = datetime.now(timezone.utc)
        assignment = ProcurementGroupAssignment(
            id="test-uuid",
            organization_id=org_id,
            sales_group_id=sales_group_id,
            user_id=procurement_user_id,
            created_at=now,
            created_by=admin_user_id,
            user_email="procurement@example.com",
            user_name="Ivan Ivanov",
            sales_group_name="Sales Team 1",
        )
        assert assignment.created_at == now
        assert assignment.created_by == admin_user_id
        assert assignment.user_email == "procurement@example.com"
        assert assignment.user_name == "Ivan Ivanov"
        assert assignment.sales_group_name == "Sales Team 1"


# =============================================================================
# TEST GROUP 2: Service CRUD — create, read, update, delete
# =============================================================================

class TestServiceCRUD:
    """Tests for route_procurement_assignment_service CRUD operations."""

    def _mock_supabase(self):
        """Create a mock supabase client with chainable query builder."""
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        # Make chainable
        mock_table.select.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.delete.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        mock_table.order.return_value = mock_table

        return mock_client, mock_table

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_create_assignment(self, mock_get_sb, org_id, sales_group_id, procurement_user_id, admin_user_id):
        """create_assignment inserts a row and returns ProcurementGroupAssignment."""
        from services.route_procurement_assignment_service import create_assignment, ProcurementGroupAssignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        now_iso = datetime.now(timezone.utc).isoformat()
        assignment_id = str(uuid4())
        mock_table.execute.return_value = MagicMock(data=[{
            "id": assignment_id,
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": procurement_user_id,
            "created_at": now_iso,
            "created_by": admin_user_id,
        }])

        result = create_assignment(
            organization_id=org_id,
            sales_group_id=sales_group_id,
            user_id=procurement_user_id,
            created_by=admin_user_id,
        )

        assert result is not None
        assert isinstance(result, ProcurementGroupAssignment)
        assert result.organization_id == org_id
        assert result.sales_group_id == sales_group_id
        assert result.user_id == procurement_user_id
        mock_client.table.assert_called_with("route_procurement_group_assignments")

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_assignment(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """get_assignment returns a single assignment by ID."""
        from services.route_procurement_assignment_service import get_assignment, ProcurementGroupAssignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        assignment_id = str(uuid4())
        mock_table.execute.return_value = MagicMock(data=[{
            "id": assignment_id,
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": procurement_user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": None,
        }])

        result = get_assignment(assignment_id)
        assert result is not None
        assert result.id == assignment_id
        mock_table.eq.assert_called_with("id", assignment_id)

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_assignment_by_group(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """get_assignment_by_group finds assignment for org+group pair."""
        from services.route_procurement_assignment_service import get_assignment_by_group

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        mock_table.execute.return_value = MagicMock(data=[{
            "id": str(uuid4()),
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": procurement_user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": None,
        }])

        result = get_assignment_by_group(org_id, sales_group_id)
        assert result is not None
        assert result.sales_group_id == sales_group_id

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_all_assignments(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """get_all_assignments returns a list for the org."""
        from services.route_procurement_assignment_service import get_all_assignments

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        group2 = str(uuid4())
        user2 = str(uuid4())
        mock_table.execute.return_value = MagicMock(data=[
            {
                "id": str(uuid4()),
                "organization_id": org_id,
                "sales_group_id": sales_group_id,
                "user_id": procurement_user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": None,
            },
            {
                "id": str(uuid4()),
                "organization_id": org_id,
                "sales_group_id": group2,
                "user_id": user2,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": None,
            },
        ])

        result = get_all_assignments(org_id)
        assert len(result) == 2

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_procurement_user_for_group(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """get_procurement_user_for_group returns just the user_id."""
        from services.route_procurement_assignment_service import get_procurement_user_for_group

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        mock_table.execute.return_value = MagicMock(data=[{
            "id": str(uuid4()),
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": procurement_user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": None,
        }])

        result = get_procurement_user_for_group(org_id, sales_group_id)
        assert result == procurement_user_id

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_procurement_user_for_group_no_match(self, mock_get_sb, org_id, sales_group_id):
        """get_procurement_user_for_group returns None when no mapping exists."""
        from services.route_procurement_assignment_service import get_procurement_user_for_group

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client
        mock_table.execute.return_value = MagicMock(data=[])

        result = get_procurement_user_for_group(org_id, sales_group_id)
        assert result is None

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_get_group_mapping(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """get_group_mapping returns dict of sales_group_id -> user_id."""
        from services.route_procurement_assignment_service import get_group_mapping

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        group2 = str(uuid4())
        user2 = str(uuid4())
        mock_table.execute.return_value = MagicMock(data=[
            {
                "id": str(uuid4()),
                "organization_id": org_id,
                "sales_group_id": sales_group_id,
                "user_id": procurement_user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": None,
            },
            {
                "id": str(uuid4()),
                "organization_id": org_id,
                "sales_group_id": group2,
                "user_id": user2,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": None,
            },
        ])

        result = get_group_mapping(org_id)
        assert result == {sales_group_id: procurement_user_id, group2: user2}

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_upsert_assignment(self, mock_get_sb, org_id, sales_group_id, procurement_user_id, admin_user_id):
        """upsert_assignment creates or updates an assignment."""
        from services.route_procurement_assignment_service import upsert_assignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        mock_table.execute.return_value = MagicMock(data=[{
            "id": str(uuid4()),
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": procurement_user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": admin_user_id,
        }])

        result = upsert_assignment(
            organization_id=org_id,
            sales_group_id=sales_group_id,
            user_id=procurement_user_id,
            created_by=admin_user_id,
        )
        assert result is not None
        assert result.user_id == procurement_user_id
        mock_table.upsert.assert_called_once()

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_update_assignment(self, mock_get_sb, org_id, sales_group_id, procurement_user_id):
        """update_assignment changes the user_id for an existing assignment."""
        from services.route_procurement_assignment_service import update_assignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client

        assignment_id = str(uuid4())
        new_user = str(uuid4())
        mock_table.execute.return_value = MagicMock(data=[{
            "id": assignment_id,
            "organization_id": org_id,
            "sales_group_id": sales_group_id,
            "user_id": new_user,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": None,
        }])

        result = update_assignment(assignment_id, new_user)
        assert result is not None
        assert result.user_id == new_user

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_delete_assignment(self, mock_get_sb):
        """delete_assignment removes the assignment and returns True."""
        from services.route_procurement_assignment_service import delete_assignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client
        mock_table.execute.return_value = MagicMock(data=[{"id": "deleted"}])

        result = delete_assignment(str(uuid4()))
        assert result is True

    @patch("services.route_procurement_assignment_service._get_supabase")
    def test_delete_assignment_not_found(self, mock_get_sb):
        """delete_assignment returns False when nothing deleted."""
        from services.route_procurement_assignment_service import delete_assignment

        mock_client, mock_table = self._mock_supabase()
        mock_get_sb.return_value = mock_client
        mock_table.execute.return_value = MagicMock(data=[])

        result = delete_assignment(str(uuid4()))
        assert result is False


# =============================================================================
# TEST GROUP 3: Cascade — sales group has priority over brand
# =============================================================================

class TestCascadeSalesGroupPriority:
    """When a sales group routing rule exists, ALL items get the group's procurement user."""

    @patch("services.workflow_service.get_supabase")
    def test_cascade_sales_group_priority(
        self,
        mock_get_sb,
        org_id,
        quote_id,
        sales_group_id,
        procurement_user_id,
        sales_user_id,
        procurement_user_brand_a,
        procurement_user_brand_b,
        item_id_1,
        item_id_2,
        item_id_3,
    ):
        """
        Sales group routing takes priority over brand routing.
        All items should be assigned to the group's procurement user,
        even if brand_assignments exist for some items.
        """
        from services.workflow_service import assign_procurement_users_to_quote

        mock_client = MagicMock()
        mock_get_sb.return_value = mock_client

        # Track calls to table() and build responses
        call_count = {"n": 0}
        table_calls = {}

        def make_table_mock(table_name):
            mock_table = MagicMock()
            mock_table.select.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.update.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.single.return_value = mock_table
            mock_table.ilike.return_value = mock_table
            mock_table.order.return_value = mock_table
            table_calls[table_name] = mock_table
            return mock_table

        # Set up table responses
        quotes_table = make_table_mock("quotes")
        quotes_table.execute.return_value = MagicMock(data={
            "id": quote_id,
            "organization_id": org_id,

            "created_by": sales_user_id,
        })

        items_table = make_table_mock("quote_items")
        items_table.execute.return_value = MagicMock(data=[
            {"id": item_id_1, "brand": "BOSCH"},
            {"id": item_id_2, "brand": "SIEMENS"},
            {"id": item_id_3, "brand": "ABB"},
        ])

        user_profiles_table = make_table_mock("user_profiles")
        user_profiles_table.execute.return_value = MagicMock(data={
            "sales_group_id": sales_group_id,
        })

        # Brand assignments also exist but should NOT be used
        brand_assignments_table = make_table_mock("brand_assignments")
        brand_assignments_table.execute.return_value = MagicMock(data=[
            {"brand": "BOSCH", "user_id": procurement_user_brand_a},
            {"brand": "SIEMENS", "user_id": procurement_user_brand_b},
        ])

        def table_router(name):
            if name not in table_calls:
                return make_table_mock(name)
            return table_calls[name]

        mock_client.table.side_effect = table_router

        # Mock the sales group lookup service (lazy import inside function body)
        with patch(
            "services.route_procurement_assignment_service.get_procurement_user_for_group",
            return_value=procurement_user_id,
        ):
            result = assign_procurement_users_to_quote(quote_id)

        assert result["success"] is True
        assert procurement_user_id in result["assigned_users"]
        assert result["assigned_items"] == 3  # ALL items assigned
        assert result["unassigned_brands"] == []


# =============================================================================
# TEST GROUP 4: Cascade — brand fallback when no sales group match
# =============================================================================

class TestCascadeBrandFallback:
    """When no sales group rule exists, items are assigned by brand (existing behavior)."""

    @patch("services.workflow_service.get_supabase")
    def test_cascade_brand_fallback(
        self,
        mock_get_sb,
        org_id,
        quote_id,
        sales_user_id,
        procurement_user_brand_a,
        procurement_user_brand_b,
        item_id_1,
        item_id_2,
        item_id_3,
    ):
        """
        No sales group routing rule -> fall through to brand assignments.
        Items with matching brands get assigned; others stay unassigned.
        """
        from services.workflow_service import assign_procurement_users_to_quote

        mock_client = MagicMock()
        mock_get_sb.return_value = mock_client

        table_calls = {}

        def make_table_mock(table_name):
            mock_table = MagicMock()
            mock_table.select.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.update.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.single.return_value = mock_table
            mock_table.ilike.return_value = mock_table
            mock_table.order.return_value = mock_table
            table_calls[table_name] = mock_table
            return mock_table

        quotes_table = make_table_mock("quotes")
        quotes_table.execute.return_value = MagicMock(data={
            "id": quote_id,
            "organization_id": org_id,

            "created_by": sales_user_id,
        })

        items_table = make_table_mock("quote_items")
        items_table.execute.return_value = MagicMock(data=[
            {"id": item_id_1, "brand": "BOSCH"},
            {"id": item_id_2, "brand": "SIEMENS"},
            {"id": item_id_3, "brand": "UNKNOWN_BRAND"},
        ])

        # No sales_group_id for this user
        user_profiles_table = make_table_mock("user_profiles")
        user_profiles_table.execute.return_value = MagicMock(data={
            "sales_group_id": None,
        })

        brand_assignments_table = make_table_mock("brand_assignments")
        brand_assignments_table.execute.return_value = MagicMock(data=[
            {"brand": "BOSCH", "user_id": procurement_user_brand_a},
            {"brand": "SIEMENS", "user_id": procurement_user_brand_b},
        ])

        def table_router(name):
            if name not in table_calls:
                return make_table_mock(name)
            return table_calls[name]

        mock_client.table.side_effect = table_router

        # No group routing match (lazy import inside function body)
        with patch(
            "services.route_procurement_assignment_service.get_procurement_user_for_group",
            return_value=None,
        ):
            result = assign_procurement_users_to_quote(quote_id)

        assert result["success"] is True
        assert procurement_user_brand_a in result["assigned_users"]
        assert procurement_user_brand_b in result["assigned_users"]
        assert result["assigned_items"] == 2  # BOSCH and SIEMENS matched
        assert "UNKNOWN_BRAND" in result["unassigned_brands"]


# =============================================================================
# TEST GROUP 5: No sales group, no brand match -> unassigned
# =============================================================================

class TestNoMatchUnassigned:
    """Items with no sales group routing and no brand match stay unassigned."""

    @patch("services.workflow_service.get_supabase")
    def test_no_sales_group_no_brand_match(
        self,
        mock_get_sb,
        org_id,
        quote_id,
        sales_user_id,
        item_id_1,
        item_id_2,
    ):
        """
        No sales group rule + no brand assignments -> all items unassigned.
        """
        from services.workflow_service import assign_procurement_users_to_quote

        mock_client = MagicMock()
        mock_get_sb.return_value = mock_client

        table_calls = {}

        def make_table_mock(table_name):
            mock_table = MagicMock()
            mock_table.select.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.update.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.single.return_value = mock_table
            mock_table.ilike.return_value = mock_table
            mock_table.order.return_value = mock_table
            table_calls[table_name] = mock_table
            return mock_table

        quotes_table = make_table_mock("quotes")
        quotes_table.execute.return_value = MagicMock(data={
            "id": quote_id,
            "organization_id": org_id,

            "created_by": sales_user_id,
        })

        items_table = make_table_mock("quote_items")
        items_table.execute.return_value = MagicMock(data=[
            {"id": item_id_1, "brand": "ORPHAN_BRAND_1"},
            {"id": item_id_2, "brand": "ORPHAN_BRAND_2"},
        ])

        # No sales group
        user_profiles_table = make_table_mock("user_profiles")
        user_profiles_table.execute.return_value = MagicMock(data={
            "sales_group_id": None,
        })

        # No brand assignments at all
        brand_assignments_table = make_table_mock("brand_assignments")
        brand_assignments_table.execute.return_value = MagicMock(data=[])

        def table_router(name):
            if name not in table_calls:
                return make_table_mock(name)
            return table_calls[name]

        mock_client.table.side_effect = table_router

        with patch(
            "services.route_procurement_assignment_service.get_procurement_user_for_group",
            return_value=None,
        ):
            result = assign_procurement_users_to_quote(quote_id)

        assert result["success"] is True
        assert result["assigned_users"] == []
        assert result["assigned_items"] == 0
        assert set(result["unassigned_brands"]) == {"ORPHAN_BRAND_1", "ORPHAN_BRAND_2"}


# =============================================================================
# TEST GROUP 7: Edge cases
# =============================================================================

class TestEdgeCases:
    """Edge cases for the cascade logic."""

    @patch("services.workflow_service.get_supabase")
    def test_no_user_profile_falls_to_brand(
        self,
        mock_get_sb,
        org_id,
        quote_id,
        sales_user_id,
        procurement_user_brand_a,
        item_id_1,
    ):
        """
        If user_profiles query returns no data (user has no profile),
        should fall back to brand routing gracefully.
        """
        from services.workflow_service import assign_procurement_users_to_quote

        mock_client = MagicMock()
        mock_get_sb.return_value = mock_client

        table_calls = {}

        def make_table_mock(table_name):
            mock_table = MagicMock()
            mock_table.select.return_value = mock_table
            mock_table.insert.return_value = mock_table
            mock_table.update.return_value = mock_table
            mock_table.eq.return_value = mock_table
            mock_table.single.return_value = mock_table
            mock_table.ilike.return_value = mock_table
            mock_table.order.return_value = mock_table
            table_calls[table_name] = mock_table
            return mock_table

        quotes_table = make_table_mock("quotes")
        quotes_table.execute.return_value = MagicMock(data={
            "id": quote_id,
            "organization_id": org_id,

            "created_by": sales_user_id,
        })

        items_table = make_table_mock("quote_items")
        items_table.execute.return_value = MagicMock(data=[
            {"id": item_id_1, "brand": "BOSCH"},
        ])

        # No user profile found
        user_profiles_table = make_table_mock("user_profiles")
        user_profiles_table.execute.return_value = MagicMock(data=None)

        brand_assignments_table = make_table_mock("brand_assignments")
        brand_assignments_table.execute.return_value = MagicMock(data=[
            {"brand": "BOSCH", "user_id": procurement_user_brand_a},
        ])

        def table_router(name):
            if name not in table_calls:
                return make_table_mock(name)
            return table_calls[name]

        mock_client.table.side_effect = table_router

        result = assign_procurement_users_to_quote(quote_id)

        assert result["success"] is True
        assert procurement_user_brand_a in result["assigned_users"]
        assert result["assigned_items"] == 1

    @patch("services.workflow_service.get_supabase")
    def test_quote_not_found(self, mock_get_sb, quote_id):
        """If quote doesn't exist, return success=False."""
        from services.workflow_service import assign_procurement_users_to_quote

        mock_client = MagicMock()
        mock_get_sb.return_value = mock_client

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=None)
        mock_client.table.return_value = mock_table

        result = assign_procurement_users_to_quote(quote_id)
        assert result["success"] is False
        assert "not found" in result["error_message"].lower() or "not found" in result.get("error_message", "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
