"""
Shared pytest fixtures for OneStack tests.

Provides:
- Test client for FastHTML app
- Mock Supabase client
- Test data factories
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime, date
from uuid import uuid4

# Set test environment before importing app
os.environ["TESTING"] = "true"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-key"
os.environ["APP_SECRET"] = "test-secret"


# ============================================================================
# MOCK FACTORIES
# ============================================================================

def make_uuid():
    """Generate a UUID string."""
    return str(uuid4())


def make_user(
    user_id=None,
    email="test@example.com",
    name="Test User",
    organization_id=None
):
    """Create a mock user dict."""
    return {
        "id": user_id or make_uuid(),
        "email": email,
        "user_metadata": {"full_name": name},
        "organization_id": organization_id or make_uuid()
    }


def make_role(code="sales", name="Sales Manager"):
    """Create a mock role dict."""
    return {
        "id": make_uuid(),
        "slug": code,
        "name": name,
        "description": f"{name} role"
    }


def make_quote(
    quote_id=None,
    customer_id=None,
    organization_id=None,
    status="draft",
    title="Test Quote"
):
    """Create a mock quote dict."""
    return {
        "id": quote_id or make_uuid(),
        "customer_id": customer_id or make_uuid(),
        "organization_id": organization_id or make_uuid(),
        "workflow_status": status,
        "title": title,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }


def make_quote_item(
    item_id=None,
    quote_id=None,
    sku="TEST-001",
    description="Test Item",
    quantity=10,
    base_price=Decimal("100.00")
):
    """Create a mock quote item dict."""
    return {
        "id": item_id or make_uuid(),
        "quote_id": quote_id or make_uuid(),
        "sku": sku,
        "description": description,
        "quantity": quantity,
        "base_price": str(base_price),
        "base_price_vat": str(base_price * Decimal("1.2")),
        "currency": "USD"
    }


def make_customer(
    customer_id=None,
    name="Test Customer",
    organization_id=None
):
    """Create a mock customer dict."""
    return {
        "id": customer_id or make_uuid(),
        "name": name,
        "organization_id": organization_id or make_uuid(),
        "email": "customer@example.com",
        "phone": "+1234567890"
    }


# ============================================================================
# SUPABASE MOCK
# ============================================================================

class MockSupabaseResponse:
    """Mock response from Supabase queries."""
    def __init__(self, data=None, error=None):
        self.data = data or []
        self.error = error


class MockSupabaseQuery:
    """Mock Supabase query builder."""

    def __init__(self, table_name, data=None):
        self.table_name = table_name
        self._data = data or []
        self._filters = {}

    def select(self, columns="*"):
        return self

    def insert(self, data):
        return self

    def update(self, data):
        return self

    def delete(self):
        return self

    def eq(self, column, value):
        self._filters[column] = value
        return self

    def neq(self, column, value):
        return self

    def in_(self, column, values):
        return self

    def single(self):
        return self

    def order(self, column, desc=False):
        return self

    def limit(self, count):
        return self

    def execute(self):
        # Filter data based on eq() calls
        result = self._data
        for col, val in self._filters.items():
            result = [r for r in result if r.get(col) == val]
        return MockSupabaseResponse(data=result)


class MockSupabaseClient:
    """Mock Supabase client for testing."""

    def __init__(self):
        self._tables = {}

    def set_table_data(self, table_name, data):
        """Set mock data for a table."""
        self._tables[table_name] = data

    def table(self, name):
        """Return a mock query for the table."""
        return MockSupabaseQuery(name, self._tables.get(name, []))

    def auth(self):
        """Mock auth module."""
        return MagicMock()


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    return MockSupabaseClient()


@pytest.fixture
def mock_supabase_with_roles(mock_supabase):
    """Mock Supabase with pre-populated roles."""
    roles = [
        {"id": make_uuid(), "slug": "sales", "name": "Sales Manager", "description": "Sales"},
        {"id": make_uuid(), "slug": "procurement", "name": "Procurement", "description": "Procurement"},
        {"id": make_uuid(), "slug": "logistics", "name": "Logistics", "description": "Logistics"},
        {"id": make_uuid(), "slug": "customs", "name": "Customs", "description": "Customs"},
        {"id": make_uuid(), "slug": "quote_controller", "name": "Quote Controller", "description": "QC"},
        {"id": make_uuid(), "slug": "spec_controller", "name": "Spec Controller", "description": "SC"},
        {"id": make_uuid(), "slug": "finance", "name": "Finance", "description": "Finance"},
        {"id": make_uuid(), "slug": "top_manager", "name": "Top Manager", "description": "TM"},
        {"id": make_uuid(), "slug": "admin", "name": "Admin", "description": "Admin"},
    ]
    mock_supabase.set_table_data("roles", roles)
    return mock_supabase


# ============================================================================
# SESSION MOCK
# ============================================================================

@pytest.fixture
def mock_session():
    """Create a mock session with user data."""
    user = make_user()
    return {
        "user_id": user["id"],
        "email": user["email"],
        "organization_id": user["organization_id"],
        "roles": ["sales"]
    }


@pytest.fixture
def mock_admin_session():
    """Create a mock admin session."""
    user = make_user(email="admin@example.com", name="Admin User")
    return {
        "user_id": user["id"],
        "email": user["email"],
        "organization_id": user["organization_id"],
        "roles": ["admin"]
    }


# ============================================================================
# APP CLIENT (for integration tests)
# ============================================================================

@pytest.fixture
def app_client():
    """
    Create a test client for the FastHTML app.

    Note: This requires the app to be importable without errors.
    If import fails, tests using this fixture will be skipped.
    """
    try:
        from starlette.testclient import TestClient
        # We'll need to mock Supabase before importing the app
        with patch('services.database.get_supabase') as mock_get_sb:
            mock_get_sb.return_value = MockSupabaseClient()
            from main import app
            return TestClient(app)
    except Exception as e:
        pytest.skip(f"Cannot create app client: {e}")


# ============================================================================
# CALCULATION ENGINE FIXTURES (Read-only reference)
# ============================================================================

@pytest.fixture
def sample_product_info():
    """Sample product info for calculation tests."""
    return {
        "base_price_VAT": Decimal("1200.00"),
        "quantity": 10,
        "weight_in_kg": Decimal("25.0"),
        "currency_of_base_price": "RUB",
        "customs_code": "8708913509"
    }


@pytest.fixture
def sample_financial_params():
    """Sample financial params for calculation tests."""
    return {
        "currency_of_quote": "USD",
        "exchange_rate_base_price_to_quote": Decimal("0.0105"),
        "supplier_discount": Decimal("10"),
        "markup": Decimal("15"),
        "rate_forex_risk": Decimal("3"),
        "dm_fee_type": "FIXED",
        "dm_fee_value": Decimal("1000")
    }
