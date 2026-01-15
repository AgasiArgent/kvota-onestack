"""
Tests for Deal Service - Deal lifecycle management

Tests for:
- DEAL-001: Deal creation from specification
- Deal CRUD operations
- Status transitions
- Utility functions
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date, timezone
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.deal_service import (
    # Data classes
    Deal,
    CreateDealFromSpecResult,
    # Constants
    DEAL_STATUSES,
    DEAL_STATUS_NAMES,
    DEAL_STATUS_COLORS,
    DEAL_TRANSITIONS,
    # Status helpers
    get_deal_status_name,
    get_deal_status_color,
    can_transition_deal,
    get_allowed_deal_transitions,
    is_deal_terminal,
    # Create operations
    create_deal,
    create_deal_from_specification,
    # Read operations
    get_deal,
    get_deal_by_specification,
    get_deal_by_quote,
    get_deals_by_status,
    get_all_deals,
    get_deals_with_details,
    count_deals_by_status,
    deal_exists_for_specification,
    deal_exists_for_quote,
    # Update operations
    update_deal,
    update_deal_status,
    complete_deal,
    cancel_deal,
    update_deal_amount,
    # Delete operations
    delete_deal,
    # Utility functions
    generate_deal_number,
    get_deal_stats,
    get_active_deals,
    get_recent_deals,
    get_deals_by_date_range,
    search_deals,
)


# =============================================================================
# DEAL DATA CLASS TESTS
# =============================================================================

class TestDealDataClass:
    """Tests for Deal dataclass."""

    def test_deal_creation(self):
        """Deal should be creatable with required fields."""
        deal = Deal(
            id="deal-uuid",
            specification_id="spec-uuid",
            quote_id="quote-uuid",
            organization_id="org-uuid",
            deal_number="DEAL-2026-0001",
            signed_at=date.today(),
            total_amount=Decimal("100000.00"),
            currency="RUB",
            status="active",
            created_by="user-uuid",
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        assert deal.id == "deal-uuid"
        assert deal.deal_number == "DEAL-2026-0001"
        assert deal.status == "active"
        assert deal.total_amount == Decimal("100000.00")

    def test_deal_from_dict(self):
        """Deal.from_dict should correctly parse database row."""
        data = {
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0002',
            'signed_at': '2026-01-15',
            'total_amount': '250000.50',
            'currency': 'USD',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:30:00Z',
            'updated_at': None,
        }

        deal = Deal.from_dict(data)

        assert deal.id == 'deal-123'
        assert deal.signed_at == date(2026, 1, 15)
        assert deal.total_amount == Decimal('250000.50')
        assert deal.currency == 'USD'

    def test_deal_to_dict(self):
        """Deal.to_dict should serialize for database operations."""
        deal = Deal(
            id="deal-uuid",
            specification_id="spec-uuid",
            quote_id="quote-uuid",
            organization_id="org-uuid",
            deal_number="DEAL-2026-0001",
            signed_at=date(2026, 1, 15),
            total_amount=Decimal("100000.00"),
            currency="RUB",
            status="active",
            created_by="user-uuid",
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        data = deal.to_dict()

        assert data['id'] == "deal-uuid"
        assert data['signed_at'] == "2026-01-15"
        assert data['total_amount'] == 100000.0  # Converted to float


# =============================================================================
# CONSTANTS AND STATUS HELPERS TESTS
# =============================================================================

class TestDealConstants:
    """Tests for deal constants."""

    def test_deal_statuses_defined(self):
        """All deal statuses should be defined."""
        assert 'active' in DEAL_STATUSES
        assert 'completed' in DEAL_STATUSES
        assert 'cancelled' in DEAL_STATUSES
        assert len(DEAL_STATUSES) == 3

    def test_all_statuses_have_names(self):
        """All statuses should have display names."""
        for status in DEAL_STATUSES:
            assert status in DEAL_STATUS_NAMES
            assert DEAL_STATUS_NAMES[status]  # Non-empty

    def test_all_statuses_have_colors(self):
        """All statuses should have colors."""
        for status in DEAL_STATUSES:
            assert status in DEAL_STATUS_COLORS
            assert DEAL_STATUS_COLORS[status].startswith('#')

    def test_transitions_defined(self):
        """Transition rules should be defined."""
        # Active can transition to completed or cancelled
        assert 'completed' in DEAL_TRANSITIONS['active']
        assert 'cancelled' in DEAL_TRANSITIONS['active']
        # Terminal statuses have no transitions
        assert DEAL_TRANSITIONS['completed'] == []
        assert DEAL_TRANSITIONS['cancelled'] == []


class TestStatusHelpers:
    """Tests for status helper functions."""

    def test_get_deal_status_name_valid(self):
        """Should return Russian name for valid status."""
        assert get_deal_status_name('active') == 'В работе'
        assert get_deal_status_name('completed') == 'Завершена'
        assert get_deal_status_name('cancelled') == 'Отменена'

    def test_get_deal_status_name_invalid(self):
        """Should return status itself for invalid status."""
        assert get_deal_status_name('unknown') == 'unknown'

    def test_get_deal_status_color(self):
        """Should return hex color for status."""
        assert get_deal_status_color('active').startswith('#')
        assert get_deal_status_color('completed').startswith('#')

    def test_get_deal_status_color_invalid(self):
        """Should return default gray for invalid status."""
        assert get_deal_status_color('unknown') == '#6b7280'

    def test_can_transition_deal_valid(self):
        """Should allow valid transitions."""
        assert can_transition_deal('active', 'completed') is True
        assert can_transition_deal('active', 'cancelled') is True

    def test_can_transition_deal_invalid(self):
        """Should block invalid transitions."""
        # Can't transition from terminal states
        assert can_transition_deal('completed', 'active') is False
        assert can_transition_deal('cancelled', 'active') is False
        # Can't transition to same status (not in list)
        assert can_transition_deal('active', 'active') is False

    def test_get_allowed_deal_transitions(self):
        """Should return list of allowed target statuses."""
        transitions = get_allowed_deal_transitions('active')
        assert 'completed' in transitions
        assert 'cancelled' in transitions

        # Terminal states have empty list
        assert get_allowed_deal_transitions('completed') == []

    def test_is_deal_terminal(self):
        """Should correctly identify terminal statuses."""
        assert is_deal_terminal('completed') is True
        assert is_deal_terminal('cancelled') is True
        assert is_deal_terminal('active') is False


# =============================================================================
# DEAL CREATION TESTS (WITH MOCKS)
# =============================================================================

class TestCreateDeal:
    """Tests for create_deal function."""

    @patch('services.deal_service.get_supabase')
    def test_create_deal_success(self, mock_get_supabase):
        """Should create deal with valid data."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 'new-deal-id',
            'specification_id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000.00',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        deal = create_deal(
            specification_id='spec-123',
            quote_id='quote-456',
            organization_id='org-789',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=100000.00,
            currency='RUB',
            created_by='user-111'
        )

        assert deal is not None
        assert deal.id == 'new-deal-id'
        assert deal.deal_number == 'DEAL-2026-0001'
        assert deal.status == 'active'

    @patch('services.deal_service.get_supabase')
    def test_create_deal_invalid_status(self, mock_get_supabase):
        """Should reject invalid status."""
        deal = create_deal(
            specification_id='spec-123',
            quote_id='quote-456',
            organization_id='org-789',
            deal_number='DEAL-2026-0001',
            signed_at=date.today(),
            total_amount=100000.00,
            status='invalid_status'  # Invalid
        )

        assert deal is None
        mock_get_supabase.assert_not_called()


# =============================================================================
# DEAL-001: CREATE DEAL FROM SPECIFICATION TESTS
# =============================================================================

class TestCreateDealFromSpecification:
    """Tests for DEAL-001: Deal creation from specification."""

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_from_spec_success(self, mock_get_supabase, mock_exists):
        """Should create deal from approved specification with signed scan."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock specification fetch
        spec_data = {
            'id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'specification_number': 'SPEC-2026-001',
            'status': 'approved',
            'signed_scan_url': 'https://storage/signed-scan.pdf',
            'sign_date': '2026-01-15',
            'specification_currency': 'USD',
            'quotes': {
                'id': 'quote-456',
                'idn_quote': 'CMT-1234567890-2026-1',
                'customer_name': 'Test Customer',
                'total_amount': '150000.00',
                'currency': 'USD',
                'organization_id': 'org-789',
                'customers': {
                    'name': 'Test Customer',
                    'company_name': 'Test Company LLC'
                }
            }
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        # Mock deal creation
        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 'deal-new',
            'specification_id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '150000.00',
            'currency': 'USD',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        # Mock spec status update
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id': 'spec-123'}]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is True
        assert result.deal is not None
        assert result.deal.id == 'deal-new'
        assert result.error is None
        assert result.extracted_data is not None
        assert result.extracted_data['quote_id'] == 'quote-456'

    @patch('services.deal_service.deal_exists_for_specification')
    def test_create_deal_already_exists(self, mock_exists):
        """Should fail if deal already exists for specification."""
        mock_exists.return_value = True

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is False
        assert result.error == "Deal already exists for this specification"
        assert result.deal is None

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_spec_not_found(self, mock_get_supabase, mock_exists):
        """Should fail if specification not found."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        result = create_deal_from_specification(
            specification_id='nonexistent-spec',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is False
        assert "not found" in result.error

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_spec_not_approved(self, mock_get_supabase, mock_exists):
        """Should fail if specification is not approved/signed."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'status': 'draft',  # Not approved!
            'signed_scan_url': None,
            'quotes': {}
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is False
        assert "must be approved or signed" in result.error

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_no_signed_scan(self, mock_get_supabase, mock_exists):
        """Should fail if signed scan not uploaded."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'status': 'approved',
            'signed_scan_url': None,  # No signed scan!
            'quotes': {}
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is False
        assert "Signed scan" in result.error

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_no_linked_quote(self, mock_get_supabase, mock_exists):
        """Should fail if specification has no linked quote."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'quote_id': None,  # No quote!
            'status': 'approved',
            'signed_scan_url': 'https://storage/scan.pdf',
            'quotes': None
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is False
        assert "no linked quote" in result.error

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_with_custom_signed_at(self, mock_get_supabase, mock_exists):
        """Should use provided signed_at date."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'status': 'approved',
            'signed_scan_url': 'https://storage/scan.pdf',
            'sign_date': '2026-01-10',
            'quotes': {
                'id': 'quote-456',
                'total_amount': '100000',
                'currency': 'RUB',
                'customers': {}
            }
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 'deal-new',
            'specification_id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-20',  # Custom date
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id': 'spec-123'}]

        custom_date = date(2026, 1, 20)
        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111',
            signed_at=custom_date
        )

        assert result.success is True
        # Check that extracted_data captured the signed_at
        assert result.extracted_data['signed_at'] == '2026-01-20'

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_without_status_update(self, mock_get_supabase, mock_exists):
        """Should skip spec status update when update_spec_status=False."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'status': 'approved',
            'signed_scan_url': 'https://storage/scan.pdf',
            'quotes': {
                'id': 'quote-456',
                'total_amount': '100000',
                'currency': 'RUB',
                'customers': {}
            }
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 'deal-new',
            'specification_id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111',
            update_spec_status=False
        )

        assert result.success is True
        assert result.specification_updated is False

    @patch('services.deal_service.deal_exists_for_specification')
    @patch('services.deal_service.get_supabase')
    def test_create_deal_already_signed_spec(self, mock_get_supabase, mock_exists):
        """Should accept already signed specification."""
        mock_exists.return_value = False
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        spec_data = {
            'id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'status': 'signed',  # Already signed
            'signed_scan_url': 'https://storage/scan.pdf',
            'quotes': {
                'id': 'quote-456',
                'total_amount': '100000',
                'currency': 'RUB',
                'customers': {}
            }
        }
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [spec_data]

        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            'id': 'deal-new',
            'specification_id': 'spec-123',
            'quote_id': 'quote-456',
            'organization_id': 'org-789',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        result = create_deal_from_specification(
            specification_id='spec-123',
            organization_id='org-789',
            created_by='user-111'
        )

        assert result.success is True
        # No spec update needed since already signed
        assert result.specification_updated is False


# =============================================================================
# READ OPERATIONS TESTS
# =============================================================================

class TestReadOperations:
    """Tests for deal read operations."""

    @patch('services.deal_service.get_supabase')
    def test_get_deal_success(self, mock_get_supabase):
        """Should fetch deal by ID."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        deal = get_deal('deal-123')

        assert deal is not None
        assert deal.id == 'deal-123'
        assert deal.deal_number == 'DEAL-2026-0001'

    @patch('services.deal_service.get_supabase')
    def test_get_deal_not_found(self, mock_get_supabase):
        """Should return None for non-existent deal."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        deal = get_deal('nonexistent')

        assert deal is None

    @patch('services.deal_service.get_supabase')
    def test_get_deal_by_specification(self, mock_get_supabase):
        """Should fetch deal by specification ID."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': None,
        }]

        deal = get_deal_by_specification('spec-456')

        assert deal is not None
        assert deal.specification_id == 'spec-456'

    @patch('services.deal_service.get_supabase')
    def test_deal_exists_for_specification_true(self, mock_get_supabase):
        """Should return True if deal exists for spec."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 1

        exists = deal_exists_for_specification('spec-123')

        assert exists is True

    @patch('services.deal_service.get_supabase')
    def test_deal_exists_for_specification_false(self, mock_get_supabase):
        """Should return False if no deal for spec."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 0

        exists = deal_exists_for_specification('spec-123')

        assert exists is False


# =============================================================================
# UPDATE OPERATIONS TESTS
# =============================================================================

class TestUpdateOperations:
    """Tests for deal update operations."""

    @patch('services.deal_service.get_supabase')
    def test_update_deal_success(self, mock_get_supabase):
        """Should update deal fields."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '200000',  # Updated
            'currency': 'USD',  # Updated
            'status': 'active',
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': '2026-01-16T10:00:00Z',
        }]

        deal = update_deal('deal-123', 'org-000', total_amount=200000, currency='USD')

        assert deal is not None
        assert deal.total_amount == Decimal('200000')
        assert deal.currency == 'USD'

    @patch('services.deal_service.get_deal')
    @patch('services.deal_service.get_supabase')
    def test_complete_deal_success(self, mock_get_supabase, mock_get_deal):
        """Should complete active deal."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock current deal
        mock_get_deal.return_value = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='active',
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'completed',  # Updated
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': '2026-01-16T10:00:00Z',
        }]

        deal = complete_deal('deal-123', 'org-000')

        assert deal is not None
        assert deal.status == 'completed'

    @patch('services.deal_service.get_deal')
    @patch('services.deal_service.get_supabase')
    def test_cancel_deal_success(self, mock_get_supabase, mock_get_deal):
        """Should cancel active deal."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_get_deal.return_value = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='active',
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{
            'id': 'deal-123',
            'specification_id': 'spec-456',
            'quote_id': 'quote-789',
            'organization_id': 'org-000',
            'deal_number': 'DEAL-2026-0001',
            'signed_at': '2026-01-15',
            'total_amount': '100000',
            'currency': 'RUB',
            'status': 'cancelled',  # Updated
            'created_by': 'user-111',
            'created_at': '2026-01-15T10:00:00Z',
            'updated_at': '2026-01-16T10:00:00Z',
        }]

        deal = cancel_deal('deal-123', 'org-000')

        assert deal is not None
        assert deal.status == 'cancelled'

    @patch('services.deal_service.get_deal')
    def test_update_deal_status_invalid_transition(self, mock_get_deal):
        """Should reject invalid status transition."""
        mock_get_deal.return_value = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='completed',  # Terminal!
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        deal = update_deal_status('deal-123', 'org-000', 'active')

        assert deal is None  # Transition blocked


# =============================================================================
# UTILITY FUNCTIONS TESTS
# =============================================================================

class TestUtilityFunctions:
    """Tests for deal utility functions."""

    @patch('services.deal_service.get_supabase')
    def test_generate_deal_number(self, mock_get_supabase):
        """Should generate sequential deal number."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 5

        deal_number = generate_deal_number('org-123')

        assert deal_number.startswith('DEAL-')
        assert '2026' in deal_number or '2025' in deal_number
        assert deal_number.endswith('-0006')  # 5 existing + 1

    @patch('services.deal_service.get_supabase')
    def test_generate_deal_number_with_custom_prefix(self, mock_get_supabase):
        """Should use custom prefix."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 0

        deal_number = generate_deal_number('org-123', prefix='CONTRACT')

        assert deal_number.startswith('CONTRACT-')

    @patch('services.deal_service.count_deals_by_status')
    @patch('services.deal_service.get_supabase')
    def test_get_deal_stats(self, mock_get_supabase, mock_count):
        """Should return deal statistics."""
        mock_count.return_value = {
            'active': 5,
            'completed': 10,
            'cancelled': 2,
            'total': 17
        }

        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock amount queries
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
            {'total_amount': '100000', 'currency': 'RUB'}
        ]

        stats = get_deal_stats('org-123')

        assert stats['total'] == 17
        assert stats['active'] == 5
        assert stats['completed'] == 10
        assert 'active_amount' in stats


# =============================================================================
# DELETE OPERATIONS TESTS
# =============================================================================

class TestDeleteOperations:
    """Tests for deal delete operations."""

    @patch('services.deal_service.get_deal')
    @patch('services.deal_service.get_supabase')
    def test_delete_deal_active_success(self, mock_get_supabase, mock_get_deal):
        """Should delete active deal with no plan-fact items."""
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        mock_get_deal.return_value = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='active',
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        # No plan_fact_items
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 0
        mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{'id': 'deal-123'}]

        result = delete_deal('deal-123', 'org-000')

        assert result is True

    @patch('services.deal_service.get_deal')
    def test_delete_deal_not_active(self, mock_get_deal):
        """Should not delete completed deal."""
        mock_get_deal.return_value = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='completed',  # Not active!
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        result = delete_deal('deal-123', 'org-000')

        assert result is False


# =============================================================================
# CREATEDEEALFROMSPECRESULT TESTS
# =============================================================================

class TestCreateDealFromSpecResult:
    """Tests for CreateDealFromSpecResult dataclass."""

    def test_success_result(self):
        """Should create success result."""
        deal = Deal(
            id='deal-123',
            specification_id='spec-456',
            quote_id='quote-789',
            organization_id='org-000',
            deal_number='DEAL-2026-0001',
            signed_at=date(2026, 1, 15),
            total_amount=Decimal('100000'),
            currency='RUB',
            status='active',
            created_by='user-111',
            created_at=datetime.now(),
            updated_at=None,
        )

        result = CreateDealFromSpecResult(
            success=True,
            deal=deal,
            specification_updated=True,
            extracted_data={'quote_id': 'quote-789'}
        )

        assert result.success is True
        assert result.deal is not None
        assert result.error is None
        assert result.specification_updated is True

    def test_failure_result(self):
        """Should create failure result."""
        result = CreateDealFromSpecResult(
            success=False,
            error="Specification not found"
        )

        assert result.success is False
        assert result.deal is None
        assert result.error == "Specification not found"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
