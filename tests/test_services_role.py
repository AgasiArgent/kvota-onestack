"""
Tests for role_service.py

Tests role management:
- Role data class
- get_user_roles function
- get_user_role_codes function
- has_role function
- require_role decorator
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4

from services.role_service import (
    Role,
    UserRole,
    get_user_roles,
    get_user_role_codes,
    has_role,
    has_any_role,
    require_role,
    require_any_role,
)


class TestRoleDataClass:
    """Tests for Role data class."""

    def test_role_creation(self):
        """Role can be created with required fields."""
        role = Role(
            id=uuid4(),
            code="sales",
            name="Sales Manager"
        )
        assert role.code == "sales"
        assert role.name == "Sales Manager"

    def test_role_with_description(self):
        """Role can have optional description."""
        role = Role(
            id=uuid4(),
            code="admin",
            name="Administrator",
            description="System administrator"
        )
        assert role.description == "System administrator"

    def test_role_description_defaults_to_none(self):
        """Role description defaults to None."""
        role = Role(
            id=uuid4(),
            code="test",
            name="Test"
        )
        assert role.description is None


class TestUserRoleDataClass:
    """Tests for UserRole data class."""

    def test_user_role_creation(self):
        """UserRole can be created with all fields."""
        role = Role(id=uuid4(), code="sales", name="Sales")
        user_role = UserRole(
            id=uuid4(),
            user_id=uuid4(),
            organization_id=uuid4(),
            role=role,
            created_at="2025-01-15T00:00:00Z"
        )
        assert user_role.role.code == "sales"


class TestGetUserRoles:
    """Tests for get_user_roles function."""

    @patch('services.role_service.get_supabase')
    def test_returns_list_of_roles(self, mock_get_supabase):
        """get_user_roles should return a list of Role objects."""
        # Setup mock
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": str(uuid4()),
                "user_id": "user-123",
                "organization_id": "org-456",
                "role_id": str(uuid4()),
                "created_at": "2025-01-15",
                "roles": {
                    "id": str(uuid4()),
                    "slug": "sales",
                    "name": "Sales Manager",
                    "description": "Sales role"
                }
            }
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        # Execute
        roles = get_user_roles("user-123", "org-456")

        # Verify
        assert isinstance(roles, list)
        assert len(roles) == 1
        assert roles[0].code == "sales"
        assert roles[0].name == "Sales Manager"

    @patch('services.role_service.get_supabase')
    def test_returns_empty_list_for_no_roles(self, mock_get_supabase):
        """get_user_roles should return empty list for user with no roles."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []

        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        roles = get_user_roles("user-123", "org-456")

        assert roles == []

    @patch('services.role_service.get_supabase')
    def test_handles_multiple_roles(self, mock_get_supabase):
        """get_user_roles should return multiple roles for multi-role user."""
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [
            {
                "id": str(uuid4()),
                "user_id": "user-123",
                "organization_id": "org-456",
                "role_id": str(uuid4()),
                "created_at": "2025-01-15",
                "roles": {
                    "id": str(uuid4()),
                    "slug": "sales",
                    "name": "Sales Manager",
                    "description": None
                }
            },
            {
                "id": str(uuid4()),
                "user_id": "user-123",
                "organization_id": "org-456",
                "role_id": str(uuid4()),
                "created_at": "2025-01-15",
                "roles": {
                    "id": str(uuid4()),
                    "slug": "admin",
                    "name": "Administrator",
                    "description": None
                }
            }
        ]

        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        roles = get_user_roles("user-123", "org-456")

        assert len(roles) == 2
        role_codes = [r.code for r in roles]
        assert "sales" in role_codes
        assert "admin" in role_codes


class TestGetUserRoleCodes:
    """Tests for get_user_role_codes function."""

    @patch('services.role_service.get_user_roles')
    def test_returns_list_of_codes(self, mock_get_roles):
        """get_user_role_codes should return list of code strings."""
        mock_get_roles.return_value = [
            Role(id=uuid4(), code="sales", name="Sales"),
            Role(id=uuid4(), code="admin", name="Admin")
        ]

        codes = get_user_role_codes("user-123", "org-456")

        assert codes == ["sales", "admin"]

    @patch('services.role_service.get_user_roles')
    def test_returns_empty_list_for_no_roles(self, mock_get_roles):
        """get_user_role_codes should return empty list for no roles."""
        mock_get_roles.return_value = []

        codes = get_user_role_codes("user-123", "org-456")

        assert codes == []


class TestHasRole:
    """Tests for has_role function."""

    @patch('services.role_service.get_user_role_codes')
    def test_returns_true_when_has_role(self, mock_get_codes):
        """has_role should return True when user has the role."""
        mock_get_codes.return_value = ["sales", "admin"]

        result = has_role("user-123", "org-456", "sales")

        assert result is True

    @patch('services.role_service.get_user_role_codes')
    def test_returns_false_when_lacks_role(self, mock_get_codes):
        """has_role should return False when user lacks the role."""
        mock_get_codes.return_value = ["sales"]

        result = has_role("user-123", "org-456", "admin")

        assert result is False

    @patch('services.role_service.get_user_role_codes')
    def test_returns_false_for_no_roles(self, mock_get_codes):
        """has_role should return False when user has no roles."""
        mock_get_codes.return_value = []

        result = has_role("user-123", "org-456", "sales")

        assert result is False


class TestHasAnyRole:
    """Tests for has_any_role function."""

    @patch('services.role_service.get_user_role_codes')
    def test_returns_true_when_has_any(self, mock_get_codes):
        """has_any_role should return True when user has any of the roles."""
        mock_get_codes.return_value = ["sales"]

        result = has_any_role("user-123", "org-456", ["sales", "admin"])

        assert result is True

    @patch('services.role_service.get_user_role_codes')
    def test_returns_false_when_has_none(self, mock_get_codes):
        """has_any_role should return False when user has none of the roles."""
        mock_get_codes.return_value = ["procurement"]

        result = has_any_role("user-123", "org-456", ["sales", "admin"])

        assert result is False


class TestRequireRoleFunction:
    """Tests for require_role function."""

    def test_function_exists(self):
        """require_role function should exist."""
        assert callable(require_role)

    @patch('services.role_service.has_role')
    def test_returns_none_when_has_role(self, mock_has_role):
        """require_role should return None when user has required role."""
        mock_has_role.return_value = True
        session = {
            "user": {"id": "user-123", "org_id": "org-456"}
        }
        result = require_role(session, "sales")
        assert result is None

    @patch('services.role_service.has_role')
    def test_returns_redirect_when_lacks_role(self, mock_has_role):
        """require_role should return RedirectResponse when user lacks role."""
        mock_has_role.return_value = False
        session = {
            "user": {"id": "user-123", "org_id": "org-456"}
        }
        result = require_role(session, "admin")
        # Should be a redirect response
        assert result is not None
        assert hasattr(result, 'status_code')

    def test_returns_redirect_when_not_logged_in(self):
        """require_role should redirect when session has no user."""
        session = {}
        result = require_role(session, "sales")
        assert result is not None
        assert hasattr(result, 'status_code')
        assert result.status_code == 303


class TestRequireAnyRoleFunction:
    """Tests for require_any_role function."""

    def test_function_exists(self):
        """require_any_role function should exist."""
        assert callable(require_any_role)

    @patch('services.role_service.has_any_role')
    def test_returns_none_when_has_any_role(self, mock_has_any):
        """require_any_role should return None when user has any of the roles."""
        mock_has_any.return_value = True
        session = {
            "user": {"id": "user-123", "org_id": "org-456"}
        }
        result = require_any_role(session, ["sales", "admin"])
        assert result is None

    @patch('services.role_service.has_any_role')
    def test_returns_redirect_when_lacks_all_roles(self, mock_has_any):
        """require_any_role should return redirect when user lacks all roles."""
        mock_has_any.return_value = False
        session = {
            "user": {"id": "user-123", "org_id": "org-456"}
        }
        result = require_any_role(session, ["admin", "top_manager"])
        assert result is not None
        assert hasattr(result, 'status_code')
