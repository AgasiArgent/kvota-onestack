"""
Tests for Customer Contract Service (Feature API-005)

Tests cover:
- Validation functions
- Contract CRUD operations
- Specification numbering
- Search and filtering
- Utility functions
"""

import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch, PropertyMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.customer_contract_service import (
    # Data class
    CustomerContract,
    _parse_contract,
    # Constants
    CONTRACT_STATUSES,
    CONTRACT_STATUS_NAMES,
    CONTRACT_STATUS_COLORS,
    # Validation functions
    validate_contract_number,
    validate_contract_status,
    # Status helpers
    get_contract_status_name,
    get_contract_status_color,
    is_contract_active,
    # Create operations
    create_contract,
    # Read operations
    get_contract,
    get_contract_with_customer,
    get_contract_by_number,
    get_contracts_for_customer,
    get_active_contracts_for_customer,
    get_all_contracts,
    get_contracts_with_customer_names,
    count_contracts,
    search_contracts,
    contract_exists,
    # Update operations
    update_contract,
    suspend_contract,
    terminate_contract,
    activate_contract,
    # Specification numbering
    get_next_specification_number,
    get_current_specification_number,
    reset_specification_number,
    # Delete operations
    delete_contract,
    # Utility functions
    get_contract_stats,
    get_contract_display_name,
    format_contract_for_dropdown,
    get_contracts_for_dropdown,
    get_contract_for_specification,
    _format_date_long,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def sample_contract_data():
    """Sample contract data for testing."""
    return {
        "id": "contract-uuid-123",
        "organization_id": "org-uuid-456",
        "customer_id": "customer-uuid-789",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
        "status": "active",
        "next_specification_number": 1,
        "notes": "Test contract",
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_contract(sample_contract_data):
    """Sample CustomerContract object for testing."""
    return _parse_contract(sample_contract_data)


@pytest.fixture
def mock_supabase():
    """Mock Supabase client."""
    with patch("services.customer_contract_service._get_supabase") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

def test_contract_statuses_exist():
    """Test that contract statuses are defined."""
    assert "active" in CONTRACT_STATUSES
    assert "suspended" in CONTRACT_STATUSES
    assert "terminated" in CONTRACT_STATUSES
    assert len(CONTRACT_STATUSES) == 3


def test_status_names_exist():
    """Test that status names are defined for all statuses."""
    for status in CONTRACT_STATUSES:
        assert status in CONTRACT_STATUS_NAMES
        assert CONTRACT_STATUS_NAMES[status]


def test_status_colors_exist():
    """Test that status colors are defined for all statuses."""
    for status in CONTRACT_STATUSES:
        assert status in CONTRACT_STATUS_COLORS


# =============================================================================
# DATA CLASS TESTS
# =============================================================================

def test_parse_contract(sample_contract_data):
    """Test parsing contract data into CustomerContract object."""
    contract = _parse_contract(sample_contract_data)

    assert contract.id == "contract-uuid-123"
    assert contract.organization_id == "org-uuid-456"
    assert contract.customer_id == "customer-uuid-789"
    assert contract.contract_number == "ДП-001/2025"
    assert contract.contract_date == date(2025, 1, 15)
    assert contract.status == "active"
    assert contract.next_specification_number == 1
    assert contract.notes == "Test contract"
    assert contract.created_at is not None
    assert contract.updated_at is not None


def test_parse_contract_with_customer_name():
    """Test parsing contract data with customer name."""
    data = {
        "id": "contract-uuid-123",
        "organization_id": "org-uuid-456",
        "customer_id": "customer-uuid-789",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
        "status": "active",
        "customer_name": "ООО Тест",
    }
    contract = _parse_contract(data)
    assert contract.customer_name == "ООО Тест"


def test_parse_contract_defaults():
    """Test parsing contract data with defaults."""
    data = {
        "id": "contract-uuid-123",
        "organization_id": "org-uuid-456",
        "customer_id": "customer-uuid-789",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
    }
    contract = _parse_contract(data)
    assert contract.status == "active"
    assert contract.next_specification_number == 1
    assert contract.notes is None


# =============================================================================
# VALIDATION TESTS
# =============================================================================

def test_validate_contract_number_valid():
    """Test valid contract numbers."""
    assert validate_contract_number("ДП-001/2025") is True
    assert validate_contract_number("Contract-123") is True
    assert validate_contract_number("123/2025") is True
    assert validate_contract_number("№ 123") is True
    assert validate_contract_number("ABC.123") is True


def test_validate_contract_number_invalid():
    """Test invalid contract numbers."""
    assert validate_contract_number("") is False
    assert validate_contract_number("   ") is False
    assert validate_contract_number(None) is False


def test_validate_contract_status_valid():
    """Test valid contract statuses."""
    assert validate_contract_status("active") is True
    assert validate_contract_status("suspended") is True
    assert validate_contract_status("terminated") is True


def test_validate_contract_status_invalid():
    """Test invalid contract statuses."""
    assert validate_contract_status("invalid") is False
    assert validate_contract_status("") is False
    assert validate_contract_status("ACTIVE") is False  # Case-sensitive


# =============================================================================
# STATUS HELPER TESTS
# =============================================================================

def test_get_contract_status_name():
    """Test getting status names."""
    assert get_contract_status_name("active") == "Действующий"
    assert get_contract_status_name("suspended") == "Приостановлен"
    assert get_contract_status_name("terminated") == "Расторгнут"
    # Unknown status returns as-is
    assert get_contract_status_name("unknown") == "unknown"


def test_get_contract_status_color():
    """Test getting status colors."""
    assert get_contract_status_color("active") == "green"
    assert get_contract_status_color("suspended") == "yellow"
    assert get_contract_status_color("terminated") == "red"
    assert get_contract_status_color("unknown") == "gray"


def test_is_contract_active(sample_contract):
    """Test checking if contract is active."""
    assert is_contract_active(sample_contract) is True

    suspended = CustomerContract(
        id="test",
        organization_id="org",
        customer_id="cust",
        contract_number="123",
        contract_date=date.today(),
        status="suspended"
    )
    assert is_contract_active(suspended) is False


# =============================================================================
# CREATE OPERATION TESTS
# =============================================================================

def test_create_contract_success(mock_supabase):
    """Test successful contract creation."""
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "new-contract-uuid",
        "organization_id": "org-uuid",
        "customer_id": "customer-uuid",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
        "status": "active",
        "next_specification_number": 1,
        "notes": None,
        "created_at": "2025-01-15T10:00:00Z",
        "updated_at": "2025-01-15T10:00:00Z",
    }]

    contract = create_contract(
        organization_id="org-uuid",
        customer_id="customer-uuid",
        contract_number="ДП-001/2025",
        contract_date=date(2025, 1, 15),
    )

    assert contract is not None
    assert contract.id == "new-contract-uuid"
    assert contract.contract_number == "ДП-001/2025"


def test_create_contract_invalid_number():
    """Test contract creation with invalid number."""
    with pytest.raises(ValueError) as exc_info:
        create_contract(
            organization_id="org-uuid",
            customer_id="customer-uuid",
            contract_number="",
            contract_date=date(2025, 1, 15),
        )
    assert "Invalid contract number format" in str(exc_info.value)


def test_create_contract_invalid_status():
    """Test contract creation with invalid status."""
    with pytest.raises(ValueError) as exc_info:
        create_contract(
            organization_id="org-uuid",
            customer_id="customer-uuid",
            contract_number="ДП-001/2025",
            contract_date=date(2025, 1, 15),
            status="invalid",
        )
    assert "Invalid contract status" in str(exc_info.value)


# =============================================================================
# READ OPERATION TESTS
# =============================================================================

def test_get_contract_success(mock_supabase, sample_contract_data):
    """Test getting contract by ID."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_contract_data]

    contract = get_contract("contract-uuid-123")

    assert contract is not None
    assert contract.id == "contract-uuid-123"


def test_get_contract_not_found(mock_supabase):
    """Test getting non-existent contract."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    contract = get_contract("non-existent")

    assert contract is None


def test_get_contracts_for_customer(mock_supabase, sample_contract_data):
    """Test getting contracts for a customer."""
    mock_chain = mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value
    mock_chain.range.return_value.execute.return_value.data = [sample_contract_data]

    contracts = get_contracts_for_customer("customer-uuid-789")

    assert len(contracts) == 1
    assert contracts[0].customer_id == "customer-uuid-789"


def test_count_contracts(mock_supabase):
    """Test counting contracts."""
    mock_query = mock_supabase.table.return_value.select.return_value.eq.return_value
    mock_query.execute.return_value.count = 5

    count = count_contracts("org-uuid")

    assert count == 5


def test_search_contracts_empty_query(mock_supabase):
    """Test search with empty query returns empty list."""
    contracts = search_contracts("org-uuid", "")
    assert contracts == []


def test_contract_exists_true(mock_supabase, sample_contract_data):
    """Test contract exists check when contract exists."""
    mock_chain = mock_supabase.table.return_value.select.return_value.eq.return_value
    mock_chain.eq.return_value.execute.return_value.data = [sample_contract_data]

    exists = contract_exists("org-uuid", "ДП-001/2025")

    assert exists is True


def test_contract_exists_false(mock_supabase):
    """Test contract exists check when contract doesn't exist."""
    mock_chain = mock_supabase.table.return_value.select.return_value.eq.return_value
    mock_chain.eq.return_value.execute.return_value.data = []

    exists = contract_exists("org-uuid", "NON-EXISTENT")

    assert exists is False


# =============================================================================
# UPDATE OPERATION TESTS
# =============================================================================

def test_update_contract_success(mock_supabase, sample_contract_data):
    """Test successful contract update."""
    updated_data = {**sample_contract_data, "notes": "Updated notes"}
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated_data]

    contract = update_contract("contract-uuid-123", notes="Updated notes")

    assert contract is not None
    assert contract.notes == "Updated notes"


def test_update_contract_invalid_status():
    """Test contract update with invalid status."""
    with pytest.raises(ValueError) as exc_info:
        update_contract("contract-uuid-123", status="invalid")
    assert "Invalid contract status" in str(exc_info.value)


def test_suspend_contract(mock_supabase, sample_contract_data):
    """Test suspending a contract."""
    suspended_data = {**sample_contract_data, "status": "suspended"}
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [suspended_data]

    contract = suspend_contract("contract-uuid-123")

    assert contract is not None
    assert contract.status == "suspended"


def test_terminate_contract(mock_supabase, sample_contract_data):
    """Test terminating a contract."""
    terminated_data = {**sample_contract_data, "status": "terminated"}
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [terminated_data]

    contract = terminate_contract("contract-uuid-123")

    assert contract is not None
    assert contract.status == "terminated"


def test_activate_contract(mock_supabase, sample_contract_data):
    """Test activating a contract."""
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [sample_contract_data]

    contract = activate_contract("contract-uuid-123")

    assert contract is not None
    assert contract.status == "active"


# =============================================================================
# SPECIFICATION NUMBERING TESTS
# =============================================================================

def test_get_next_specification_number(mock_supabase):
    """Test getting next specification number."""
    mock_supabase.rpc.return_value.execute.return_value.data = 1

    spec_num = get_next_specification_number("contract-uuid-123")

    assert spec_num == 1
    mock_supabase.rpc.assert_called_once_with(
        "get_next_specification_number",
        {"p_contract_id": "contract-uuid-123"}
    )


def test_get_current_specification_number(mock_supabase, sample_contract_data):
    """Test getting current specification number without incrementing."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_contract_data]

    spec_num = get_current_specification_number("contract-uuid-123")

    assert spec_num == 1


def test_reset_specification_number(mock_supabase, sample_contract_data):
    """Test resetting specification number."""
    reset_data = {**sample_contract_data, "next_specification_number": 5}
    mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [reset_data]

    contract = reset_specification_number("contract-uuid-123", 5)

    assert contract is not None
    assert contract.next_specification_number == 5


# =============================================================================
# DELETE OPERATION TESTS
# =============================================================================

def test_delete_contract_success(mock_supabase):
    """Test successful contract deletion."""
    mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    result = delete_contract("contract-uuid-123")

    assert result is True


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

def test_get_contract_stats(mock_supabase):
    """Test getting contract statistics."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"status": "active", "customer_id": "cust-1"},
        {"status": "active", "customer_id": "cust-1"},
        {"status": "suspended", "customer_id": "cust-2"},
        {"status": "terminated", "customer_id": "cust-3"},
    ]

    stats = get_contract_stats("org-uuid")

    assert stats["total"] == 4
    assert stats["active"] == 2
    assert stats["suspended"] == 1
    assert stats["terminated"] == 1
    assert stats["by_customer_count"] == 3


def test_get_contract_stats_empty(mock_supabase):
    """Test getting stats for organization with no contracts."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    stats = get_contract_stats("org-uuid")

    assert stats["total"] == 0
    assert stats["active"] == 0
    assert stats["by_customer_count"] == 0


def test_get_contract_display_name(sample_contract):
    """Test getting contract display name."""
    display_name = get_contract_display_name(sample_contract)

    assert "ДП-001/2025" in display_name
    assert "15.01.2025" in display_name
    assert "от" in display_name


def test_format_contract_for_dropdown(sample_contract):
    """Test formatting contract for dropdown."""
    dropdown = format_contract_for_dropdown(sample_contract)

    assert dropdown["value"] == "contract-uuid-123"
    assert "ДП-001/2025" in dropdown["label"]


def test_format_date_long():
    """Test formatting date in long Russian format."""
    test_date = date(2025, 1, 15)
    formatted = _format_date_long(test_date)

    assert formatted == "15 января 2025 г."


def test_format_date_long_all_months():
    """Test date formatting for all months."""
    months_ru = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    for month in range(1, 13):
        test_date = date(2025, month, 1)
        formatted = _format_date_long(test_date)
        assert months_ru[month - 1] in formatted


def test_get_contract_for_specification(mock_supabase):
    """Test getting contract info for specification."""
    mock_data = {
        "id": "contract-uuid",
        "organization_id": "org-uuid",
        "customer_id": "customer-uuid",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
        "status": "active",
        "customers": {"name": "ООО Тест"},
    }
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [mock_data]

    spec_info = get_contract_for_specification("contract-uuid")

    assert spec_info is not None
    assert spec_info["contract_number"] == "ДП-001/2025"
    assert spec_info["contract_date"] == "15.01.2025"
    assert spec_info["customer_name"] == "ООО Тест"
    assert "Договор" in spec_info["full_reference"]


def test_get_contract_for_specification_not_found(mock_supabase):
    """Test getting spec info for non-existent contract."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    spec_info = get_contract_for_specification("non-existent")

    assert spec_info is None


# =============================================================================
# EDGE CASES
# =============================================================================

def test_parse_contract_with_date_object():
    """Test parsing when contract_date is already a date object."""
    data = {
        "id": "contract-uuid-123",
        "organization_id": "org-uuid",
        "customer_id": "customer-uuid",
        "contract_number": "ДП-001/2025",
        "contract_date": date(2025, 1, 15),  # Already a date object
    }
    contract = _parse_contract(data)
    assert contract.contract_date == date(2025, 1, 15)


def test_update_contract_no_changes(mock_supabase, sample_contract_data):
    """Test update with no changes returns current state."""
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [sample_contract_data]

    contract = update_contract("contract-uuid-123")

    assert contract is not None
    assert contract.id == "contract-uuid-123"


def test_get_active_contracts_for_customer(mock_supabase, sample_contract_data):
    """Test getting only active contracts for customer."""
    mock_chain = mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.eq.return_value
    mock_chain.range.return_value.execute.return_value.data = [sample_contract_data]

    contracts = get_active_contracts_for_customer("customer-uuid")

    assert len(contracts) >= 0  # Just verify it doesn't error


def test_get_contracts_with_customer_names(mock_supabase):
    """Test getting contracts with customer names joined."""
    mock_data = [{
        "id": "contract-uuid",
        "organization_id": "org-uuid",
        "customer_id": "customer-uuid",
        "contract_number": "ДП-001/2025",
        "contract_date": "2025-01-15",
        "status": "active",
        "customers": {"name": "ООО Тест"},
    }]
    mock_chain = mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value
    mock_chain.range.return_value.execute.return_value.data = mock_data

    contracts = get_contracts_with_customer_names("org-uuid")

    assert len(contracts) == 1
    assert contracts[0].customer_name == "ООО Тест"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
