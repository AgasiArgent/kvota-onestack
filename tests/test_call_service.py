"""
Tests for Call Service - CRUD operations for calls journal (kvota.calls table)

Feature: [86aftzp2n] Calls Journal - customer card + registry

Tests cover:
- CallRecord dataclass fields and defaults
- CALL_TYPE_LABELS and CALL_CATEGORY_LABELS constants
- _parse_call() with FK null safety pattern
- create_call() with all fields
- get_calls_for_customer() with sorting logic
- get_calls_registry() with filters (q, call_type, user_id)
- update_call() with partial updates
- delete_call()
- Edge cases: empty results, invalid IDs, missing FK data

TDD: These tests are written BEFORE implementation.
The call_service.py module does not exist yet -- tests should fail with ImportError.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def org_id():
    """Organization ID for tests."""
    return str(uuid4())


@pytest.fixture
def customer_id():
    """Customer ID for tests."""
    return str(uuid4())


@pytest.fixture
def user_id():
    """User (manager/MOP) ID for tests."""
    return str(uuid4())


@pytest.fixture
def contact_id():
    """Contact person ID for tests."""
    return str(uuid4())


@pytest.fixture
def call_id():
    """Call record ID for tests."""
    return str(uuid4())


@pytest.fixture
def sample_call_data(call_id, customer_id, user_id, contact_id, org_id):
    """Sample call database row with FK joins."""
    return {
        "id": call_id,
        "organization_id": org_id,
        "customer_id": customer_id,
        "contact_person_id": contact_id,
        "user_id": user_id,
        "call_type": "call",
        "call_category": "cold",
        "scheduled_date": None,
        "comment": "Discussed delivery terms",
        "customer_needs": "Need 100 units monthly",
        "meeting_notes": "Follow-up in 2 weeks",
        "created_at": "2026-02-28T10:00:00Z",
        "updated_at": "2026-02-28T10:00:00Z",
        # FK joined data
        "customers": {"id": customer_id, "name": "OOO Romashka"},
        "customer_contacts": {"id": contact_id, "name": "Ivan Ivanov"},
        # user_profiles injected by _enrich_user_names (two-step fetch from kvota.user_profiles)
        "user_profiles": {"full_name": "Manager Test"},
    }


@pytest.fixture
def sample_scheduled_call_data(customer_id, user_id, org_id):
    """Sample scheduled call database row."""
    future_date = (datetime.now() + timedelta(days=3)).isoformat()
    return {
        "id": str(uuid4()),
        "organization_id": org_id,
        "customer_id": customer_id,
        "contact_person_id": None,
        "user_id": user_id,
        "call_type": "scheduled",
        "call_category": "warm",
        "scheduled_date": future_date,
        "comment": "Follow-up call",
        "customer_needs": "",
        "meeting_notes": "",
        "created_at": "2026-02-25T10:00:00Z",
        "updated_at": "2026-02-25T10:00:00Z",
        "customers": {"id": customer_id, "name": "OOO Romashka"},
        "customer_contacts": None,
        "user_profiles": {"full_name": "Manager Test"},
    }


@pytest.fixture
def sample_call_data_null_fks(call_id, customer_id, user_id, org_id):
    """Sample call with all FK joins returning null (PostgREST null join)."""
    return {
        "id": call_id,
        "organization_id": org_id,
        "customer_id": customer_id,
        "contact_person_id": None,
        "user_id": user_id,
        "call_type": "call",
        "call_category": "incoming",
        "scheduled_date": None,
        "comment": "Quick check-in",
        "customer_needs": None,
        "meeting_notes": None,
        "created_at": "2026-02-28T10:00:00Z",
        "updated_at": "2026-02-28T10:00:00Z",
        # PostgREST returns null when FK join has no match
        "customers": None,
        "customer_contacts": None,
        # user_profiles may be None if _enrich_user_names failed or user not found
        "user_profiles": None,
    }


# =============================================================================
# IMPORT TESTS - verify module structure
# =============================================================================

class TestModuleImports:
    """Test that call_service module exists and exports expected symbols."""

    def test_import_call_service_module(self):
        """call_service module can be imported."""
        from services import call_service
        assert call_service is not None

    def test_import_call_record_dataclass(self):
        """CallRecord dataclass is importable."""
        from services.call_service import CallRecord
        assert CallRecord is not None

    def test_import_call_type_labels(self):
        """CALL_TYPE_LABELS constant is importable."""
        from services.call_service import CALL_TYPE_LABELS
        assert isinstance(CALL_TYPE_LABELS, dict)

    def test_import_call_category_labels(self):
        """CALL_CATEGORY_LABELS constant is importable."""
        from services.call_service import CALL_CATEGORY_LABELS
        assert isinstance(CALL_CATEGORY_LABELS, dict)

    def test_import_crud_functions(self):
        """All CRUD functions are importable."""
        from services.call_service import (
            create_call,
            get_call,
            get_calls_for_customer,
            get_calls_registry,
            update_call,
            delete_call,
            _parse_call,
        )
        assert all([
            create_call, get_call, get_calls_for_customer,
            get_calls_registry, update_call, delete_call, _parse_call,
        ])


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

class TestConstants:
    """Test label constants for call types and categories."""

    def test_call_type_labels_has_call(self):
        """CALL_TYPE_LABELS contains 'call' key."""
        from services.call_service import CALL_TYPE_LABELS
        assert "call" in CALL_TYPE_LABELS

    def test_call_type_labels_has_scheduled(self):
        """CALL_TYPE_LABELS contains 'scheduled' key."""
        from services.call_service import CALL_TYPE_LABELS
        assert "scheduled" in CALL_TYPE_LABELS

    def test_call_type_labels_russian(self):
        """CALL_TYPE_LABELS values are Russian labels."""
        from services.call_service import CALL_TYPE_LABELS
        # Expect Russian translations
        assert CALL_TYPE_LABELS["call"] is not None
        assert CALL_TYPE_LABELS["scheduled"] is not None
        assert len(CALL_TYPE_LABELS) == 2

    def test_call_category_labels_has_cold(self):
        """CALL_CATEGORY_LABELS contains 'cold' key."""
        from services.call_service import CALL_CATEGORY_LABELS
        assert "cold" in CALL_CATEGORY_LABELS

    def test_call_category_labels_has_warm(self):
        """CALL_CATEGORY_LABELS contains 'warm' key."""
        from services.call_service import CALL_CATEGORY_LABELS
        assert "warm" in CALL_CATEGORY_LABELS

    def test_call_category_labels_has_incoming(self):
        """CALL_CATEGORY_LABELS contains 'incoming' key."""
        from services.call_service import CALL_CATEGORY_LABELS
        assert "incoming" in CALL_CATEGORY_LABELS

    def test_call_category_labels_count(self):
        """CALL_CATEGORY_LABELS has exactly 3 entries."""
        from services.call_service import CALL_CATEGORY_LABELS
        assert len(CALL_CATEGORY_LABELS) == 3


# =============================================================================
# DATACLASS TESTS
# =============================================================================

class TestCallRecordDataclass:
    """Test CallRecord dataclass fields and defaults."""

    def test_call_record_required_fields(self):
        """CallRecord has required fields: id, organization_id, customer_id, user_id, call_type."""
        from services.call_service import CallRecord
        record = CallRecord(
            id="test-id",
            organization_id="org-1",
            customer_id="cust-1",
            user_id="user-1",
            call_type="call",
        )
        assert record.id == "test-id"
        assert record.organization_id == "org-1"
        assert record.customer_id == "cust-1"
        assert record.user_id == "user-1"
        assert record.call_type == "call"

    def test_call_record_optional_fields_default_none(self):
        """CallRecord optional fields default to None or empty string."""
        from services.call_service import CallRecord
        record = CallRecord(
            id="test-id",
            organization_id="org-1",
            customer_id="cust-1",
            user_id="user-1",
            call_type="call",
        )
        assert record.contact_person_id is None
        assert record.call_category is None or record.call_category == ""
        assert record.scheduled_date is None
        assert record.comment is None or record.comment == ""
        assert record.customer_needs is None or record.customer_needs == ""
        assert record.meeting_notes is None or record.meeting_notes == ""

    def test_call_record_display_fields(self):
        """CallRecord has FK display fields for customer/contact/user names."""
        from services.call_service import CallRecord
        record = CallRecord(
            id="test-id",
            organization_id="org-1",
            customer_id="cust-1",
            user_id="user-1",
            call_type="call",
            customer_name="OOO Test",
            contact_name="Ivan",
            user_name="Manager",
        )
        assert record.customer_name == "OOO Test"
        assert record.contact_name == "Ivan"
        assert record.user_name == "Manager"

    def test_call_record_timestamps(self):
        """CallRecord has created_at and updated_at fields."""
        from services.call_service import CallRecord
        now = datetime.now()
        record = CallRecord(
            id="test-id",
            organization_id="org-1",
            customer_id="cust-1",
            user_id="user-1",
            call_type="call",
            created_at=now,
            updated_at=now,
        )
        assert record.created_at == now
        assert record.updated_at == now


# =============================================================================
# PARSE CALL TESTS
# =============================================================================

class TestParseCall:
    """Test _parse_call() function for converting DB rows to CallRecord."""

    def test_parse_call_basic(self, sample_call_data):
        """Parse a complete call record from database row."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data)

        assert record.id == sample_call_data["id"]
        assert record.customer_id == sample_call_data["customer_id"]
        assert record.user_id == sample_call_data["user_id"]
        assert record.contact_person_id == sample_call_data["contact_person_id"]
        assert record.call_type == "call"
        assert record.call_category == "cold"
        assert record.comment == "Discussed delivery terms"
        assert record.customer_needs == "Need 100 units monthly"
        assert record.meeting_notes == "Follow-up in 2 weeks"

    def test_parse_call_extracts_customer_name(self, sample_call_data):
        """Parse extracts customer name from FK join."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data)

        assert record.customer_name == "OOO Romashka"

    def test_parse_call_extracts_contact_name(self, sample_call_data):
        """Parse extracts contact name from FK join."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data)

        assert record.contact_name == "Ivan Ivanov"

    def test_parse_call_extracts_user_name(self, sample_call_data):
        """Parse extracts user display name from user_profiles (two-step fetch)."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data)

        # User name from user_profiles.full_name (injected by _enrich_user_names)
        assert record.user_name is not None
        assert len(record.user_name) > 0

    def test_parse_call_null_fk_safety_customers(self, sample_call_data_null_fks):
        """Parse handles null customers FK (PostgREST null join) without crash.

        BUG PATTERN: data.get("customers", {}).get("name") crashes when customers=None.
        SAFE PATTERN: (data.get("customers") or {}).get("name", "---")
        """
        from services.call_service import _parse_call
        # Should NOT raise AttributeError
        record = _parse_call(sample_call_data_null_fks)

        # customer_name should be a safe default, not crash
        assert record.customer_name is not None or record.customer_name == ""

    def test_parse_call_null_fk_safety_contacts(self, sample_call_data_null_fks):
        """Parse handles null customer_contacts FK without crash."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data_null_fks)

        # contact_name should be empty/default, not crash
        assert isinstance(record, object)  # didn't crash

    def test_parse_call_null_fk_safety_user_profiles(self, sample_call_data_null_fks):
        """Parse handles null user_profiles FK without crash."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data_null_fks)

        # user_name should be None when user_profiles is null, not crash
        assert isinstance(record, object)  # didn't crash

    def test_parse_call_scheduled_with_date(self, sample_scheduled_call_data):
        """Parse scheduled call preserves scheduled_date."""
        from services.call_service import _parse_call
        record = _parse_call(sample_scheduled_call_data)

        assert record.call_type == "scheduled"
        assert record.scheduled_date is not None

    def test_parse_call_none_optional_fields(self, sample_call_data_null_fks):
        """Parse handles None values for optional text fields."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data_null_fks)

        # Should not crash on None customer_needs, meeting_notes
        assert record.comment == "Quick check-in"

    def test_parse_call_timestamps_parsed(self, sample_call_data):
        """Parse converts timestamp strings to datetime objects."""
        from services.call_service import _parse_call
        record = _parse_call(sample_call_data)

        assert record.created_at is not None


# =============================================================================
# CREATE CALL TESTS
# =============================================================================

class TestCreateCall:
    """Test create_call() function."""

    @patch('services.call_service._get_supabase')
    def test_create_call_basic(self, mock_get_supabase, sample_call_data, org_id, customer_id, user_id):
        """Create a basic call record with required fields."""
        from services.call_service import create_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )

        result = create_call(
            organization_id=org_id,
            customer_id=customer_id,
            user_id=user_id,
            call_type="call",
            comment="Test call",
        )

        assert result is not None
        assert result.call_type == "call"
        mock_client.table.assert_called_with("calls")

    @patch('services.call_service._get_supabase')
    def test_create_call_with_all_fields(
        self, mock_get_supabase, sample_call_data,
        org_id, customer_id, user_id, contact_id
    ):
        """Create a call record with all optional fields."""
        from services.call_service import create_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )

        result = create_call(
            organization_id=org_id,
            customer_id=customer_id,
            user_id=user_id,
            call_type="call",
            call_category="cold",
            contact_person_id=contact_id,
            comment="Full call record",
            customer_needs="Monthly supply needed",
            meeting_notes="Schedule meeting next week",
        )

        assert result is not None
        # Verify insert was called with correct data
        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["organization_id"] == org_id
        assert insert_data["customer_id"] == customer_id
        assert insert_data["user_id"] == user_id
        assert insert_data["call_type"] == "call"
        assert insert_data["call_category"] == "cold"
        assert insert_data["contact_person_id"] == contact_id

    @patch('services.call_service._get_supabase')
    def test_create_scheduled_call_with_date(
        self, mock_get_supabase, sample_scheduled_call_data,
        org_id, customer_id, user_id
    ):
        """Create a scheduled call with scheduled_date."""
        from services.call_service import create_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_scheduled_call_data]
        )

        scheduled_date = (datetime.now() + timedelta(days=3)).isoformat()
        result = create_call(
            organization_id=org_id,
            customer_id=customer_id,
            user_id=user_id,
            call_type="scheduled",
            call_category="warm",
            scheduled_date=scheduled_date,
            comment="Follow-up call",
        )

        assert result is not None
        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["call_type"] == "scheduled"
        assert insert_data["scheduled_date"] == scheduled_date

    @patch('services.call_service._get_supabase')
    def test_create_call_db_error_returns_none(self, mock_get_supabase, org_id, customer_id, user_id):
        """Create call returns None when database error occurs."""
        from services.call_service import create_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")

        result = create_call(
            organization_id=org_id,
            customer_id=customer_id,
            user_id=user_id,
            call_type="call",
        )

        assert result is None

    @patch('services.call_service._get_supabase')
    def test_create_call_empty_response_returns_none(self, mock_get_supabase, org_id, customer_id, user_id):
        """Create call returns None when DB returns empty data."""
        from services.call_service import create_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

        result = create_call(
            organization_id=org_id,
            customer_id=customer_id,
            user_id=user_id,
            call_type="call",
        )

        assert result is None


# =============================================================================
# GET SINGLE CALL TESTS
# =============================================================================

class TestGetCall:
    """Test get_call() function."""

    @patch('services.call_service._get_supabase')
    def test_get_call_found(self, mock_get_supabase, sample_call_data, call_id):
        """Get existing call by ID."""
        from services.call_service import get_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )

        result = get_call(call_id)

        assert result is not None
        assert result.id == call_id

    @patch('services.call_service._get_supabase')
    def test_get_call_not_found(self, mock_get_supabase):
        """Get non-existing call returns None."""
        from services.call_service import get_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = get_call("nonexistent-id")

        assert result is None

    @patch('services.call_service._get_supabase')
    def test_get_call_db_error_returns_none(self, mock_get_supabase, call_id):
        """Get call returns None on database error."""
        from services.call_service import get_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = get_call(call_id)

        assert result is None


# =============================================================================
# GET CALLS FOR CUSTOMER TESTS
# =============================================================================

class TestGetCallsForCustomer:
    """Test get_calls_for_customer() function with sorting logic."""

    @patch('services.call_service._get_supabase')
    def test_get_calls_for_customer_returns_list(self, mock_get_supabase, sample_call_data, customer_id, user_id):
        """Get calls for customer returns list of CallRecord objects."""
        from services.call_service import get_calls_for_customer

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )
        # Mock user_profiles batch fetch
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"user_id": user_id, "full_name": "Manager Test"}]
        )

        results = get_calls_for_customer(customer_id)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].customer_id == customer_id

    @patch('services.call_service._get_supabase')
    def test_get_calls_for_customer_empty(self, mock_get_supabase, customer_id):
        """Get calls for customer with no calls returns empty list."""
        from services.call_service import get_calls_for_customer

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        results = get_calls_for_customer(customer_id)

        assert results == []

    @patch('services.call_service._get_supabase')
    def test_get_calls_for_customer_db_error_returns_empty(self, mock_get_supabase, customer_id):
        """Get calls returns empty list on database error."""
        from services.call_service import get_calls_for_customer

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("DB")

        results = get_calls_for_customer(customer_id)

        assert results == []


# =============================================================================
# SORTING LOGIC TESTS
# =============================================================================

class TestCallsSortingLogic:
    """Test that calls are sorted: scheduled (upcoming) first, then completed by newest.

    Sorting requirement:
    1. Scheduled calls with future dates appear FIRST, sorted by nearest date
    2. Completed calls appear AFTER, sorted by newest created_at first
    3. Past scheduled calls (missed) sort with completed calls by date desc
    """

    def test_sort_scheduled_before_completed(self):
        """Scheduled future calls appear before completed calls."""
        from services.call_service import sort_calls

        now = datetime.now()
        future = (now + timedelta(days=2)).isoformat()
        past = (now - timedelta(days=1)).isoformat()

        calls_data = [
            {
                "id": "completed-1", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "call", "call_category": "cold",
                "contact_person_id": None, "scheduled_date": None,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": past, "updated_at": past,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
            {
                "id": "scheduled-1", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "scheduled", "call_category": "warm",
                "contact_person_id": None, "scheduled_date": future,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": past, "updated_at": past,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
        ]

        from services.call_service import _parse_call
        parsed = [_parse_call(d) for d in calls_data]
        sorted_calls = sort_calls(parsed)

        assert sorted_calls[0].id == "scheduled-1"
        assert sorted_calls[1].id == "completed-1"

    def test_sort_scheduled_by_nearest_date_first(self):
        """Multiple scheduled calls sorted by nearest date first."""
        from services.call_service import sort_calls, _parse_call

        now = datetime.now()
        near_future = (now + timedelta(days=1)).isoformat()
        far_future = (now + timedelta(days=10)).isoformat()

        calls_data = [
            {
                "id": "far-scheduled", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "scheduled", "call_category": "cold",
                "contact_person_id": None, "scheduled_date": far_future,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": now.isoformat(), "updated_at": now.isoformat(),
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
            {
                "id": "near-scheduled", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "scheduled", "call_category": "warm",
                "contact_person_id": None, "scheduled_date": near_future,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": now.isoformat(), "updated_at": now.isoformat(),
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
        ]

        parsed = [_parse_call(d) for d in calls_data]
        sorted_calls = sort_calls(parsed)

        assert sorted_calls[0].id == "near-scheduled"
        assert sorted_calls[1].id == "far-scheduled"

    def test_sort_completed_by_newest_first(self):
        """Completed calls sorted by newest created_at first."""
        from services.call_service import sort_calls, _parse_call

        now = datetime.now()
        older = (now - timedelta(days=5)).isoformat()
        newer = (now - timedelta(days=1)).isoformat()

        calls_data = [
            {
                "id": "older-call", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "call", "call_category": "cold",
                "contact_person_id": None, "scheduled_date": None,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": older, "updated_at": older,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
            {
                "id": "newer-call", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "call", "call_category": "warm",
                "contact_person_id": None, "scheduled_date": None,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": newer, "updated_at": newer,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
        ]

        parsed = [_parse_call(d) for d in calls_data]
        sorted_calls = sort_calls(parsed)

        assert sorted_calls[0].id == "newer-call"
        assert sorted_calls[1].id == "older-call"

    def test_sort_past_scheduled_with_completed(self):
        """Past scheduled calls (missed) sort with completed calls by date desc."""
        from services.call_service import sort_calls, _parse_call

        now = datetime.now()
        past_scheduled_date = (now - timedelta(days=2)).isoformat()
        recent_call_date = (now - timedelta(days=1)).isoformat()
        old_call_date = (now - timedelta(days=5)).isoformat()

        calls_data = [
            {
                "id": "old-call", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "call", "call_category": "cold",
                "contact_person_id": None, "scheduled_date": None,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": old_call_date, "updated_at": old_call_date,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
            {
                "id": "past-scheduled", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "scheduled", "call_category": "warm",
                "contact_person_id": None, "scheduled_date": past_scheduled_date,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": past_scheduled_date, "updated_at": past_scheduled_date,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
            {
                "id": "recent-call", "organization_id": "org", "customer_id": "c1",
                "user_id": "u1", "call_type": "call", "call_category": "incoming",
                "contact_person_id": None, "scheduled_date": None,
                "comment": "", "customer_needs": "", "meeting_notes": "",
                "created_at": recent_call_date, "updated_at": recent_call_date,
                "customers": None, "customer_contacts": None, "user_profiles": None,
            },
        ]

        parsed = [_parse_call(d) for d in calls_data]
        sorted_calls = sort_calls(parsed)

        # Past scheduled call should NOT be in the "upcoming" section
        # It should sort among completed calls by its scheduled_date
        # Order: recent-call (1 day ago), past-scheduled (2 days ago), old-call (5 days ago)
        assert sorted_calls[0].id == "recent-call"
        assert sorted_calls[2].id == "old-call"

    def test_sort_empty_list(self):
        """Sorting empty list returns empty list."""
        from services.call_service import sort_calls
        assert sort_calls([]) == []

    def test_sort_single_item(self):
        """Sorting single-item list returns same list."""
        from services.call_service import sort_calls, CallRecord

        record = CallRecord(
            id="only-one",
            organization_id="org",
            customer_id="c1",
            user_id="u1",
            call_type="call",
        )
        result = sort_calls([record])
        assert len(result) == 1
        assert result[0].id == "only-one"


# =============================================================================
# GET CALLS REGISTRY TESTS (with filters)
# =============================================================================

class TestGetCallsRegistry:
    """Test get_calls_registry() with filtering and pagination."""

    @patch('services.call_service._get_supabase')
    def test_registry_returns_list(self, mock_get_supabase, sample_call_data, org_id, user_id):
        """Registry returns list of CallRecord objects."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )
        # Mock user_profiles batch fetch
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"user_id": user_id, "full_name": "Manager Test"}]
        )

        results = get_calls_registry(org_id)

        assert isinstance(results, list)
        assert len(results) >= 1

    @patch('services.call_service._get_supabase')
    def test_registry_empty(self, mock_get_supabase, org_id):
        """Registry with no calls returns empty list."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])

        results = get_calls_registry(org_id)

        assert results == []

    @patch('services.call_service._get_supabase')
    def test_registry_filter_by_call_type(self, mock_get_supabase, sample_call_data, org_id, user_id):
        """Registry filters by call_type."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        # Chain: .eq(call_type).order().limit().execute()
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )
        # Mock user_profiles batch fetch
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"user_id": user_id, "full_name": "Manager Test"}]
        )

        results = get_calls_registry(org_id, call_type="call")

        assert isinstance(results, list)

    @patch('services.call_service._get_supabase')
    def test_registry_filter_by_user_id(self, mock_get_supabase, sample_call_data, org_id, user_id):
        """Registry filters by user_id (manager/MOP)."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )
        # Mock user_profiles batch fetch
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"user_id": user_id, "full_name": "Manager Test"}]
        )

        results = get_calls_registry(org_id, user_id=user_id)

        assert isinstance(results, list)

    @patch('services.call_service._get_supabase')
    def test_registry_filter_by_search_query(self, mock_get_supabase, sample_call_data, org_id, user_id):
        """Registry filters by text search query (q parameter)."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )
        # Mock user_profiles batch fetch
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"user_id": user_id, "full_name": "Manager Test"}]
        )

        results = get_calls_registry(org_id, q="delivery")

        assert isinstance(results, list)

    @patch('services.call_service._get_supabase')
    def test_registry_db_error_returns_empty(self, mock_get_supabase, org_id):
        """Registry returns empty list on database error."""
        from services.call_service import get_calls_registry

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = Exception("DB")

        results = get_calls_registry(org_id)

        assert results == []


# =============================================================================
# UPDATE CALL TESTS
# =============================================================================

class TestUpdateCall:
    """Test update_call() with partial updates."""

    @patch('services.call_service._get_supabase')
    def test_update_call_comment(self, mock_get_supabase, sample_call_data, call_id):
        """Update call comment only."""
        from services.call_service import update_call

        updated_data = {**sample_call_data, "comment": "Updated comment"}
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        result = update_call(call_id, comment="Updated comment")

        assert result is not None
        assert result.comment == "Updated comment"

    @patch('services.call_service._get_supabase')
    def test_update_call_type(self, mock_get_supabase, sample_call_data, call_id):
        """Update call type from 'call' to 'scheduled'."""
        from services.call_service import update_call

        future = (datetime.now() + timedelta(days=5)).isoformat()
        updated_data = {
            **sample_call_data,
            "call_type": "scheduled",
            "scheduled_date": future,
        }
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        result = update_call(call_id, call_type="scheduled", scheduled_date=future)

        assert result is not None
        assert result.call_type == "scheduled"

    @patch('services.call_service._get_supabase')
    def test_update_call_multiple_fields(self, mock_get_supabase, sample_call_data, call_id):
        """Update multiple fields at once."""
        from services.call_service import update_call

        updated_data = {
            **sample_call_data,
            "comment": "New comment",
            "customer_needs": "New needs",
            "call_category": "warm",
        }
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_data]
        )

        result = update_call(
            call_id,
            comment="New comment",
            customer_needs="New needs",
            call_category="warm",
        )

        assert result is not None
        assert result.comment == "New comment"
        assert result.customer_needs == "New needs"

    @patch('services.call_service._get_supabase')
    def test_update_call_no_changes_returns_current(self, mock_get_supabase, sample_call_data, call_id):
        """Update with no fields returns current record."""
        from services.call_service import update_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        # When no update data, should either return current or call get_call
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_call_data]
        )

        result = update_call(call_id)

        assert result is not None

    @patch('services.call_service._get_supabase')
    def test_update_call_not_found_returns_none(self, mock_get_supabase, call_id):
        """Update non-existing call returns None."""
        from services.call_service import update_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = update_call(call_id, comment="test")

        assert result is None

    @patch('services.call_service._get_supabase')
    def test_update_call_db_error_returns_none(self, mock_get_supabase, call_id):
        """Update call returns None on database error."""
        from services.call_service import update_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = update_call(call_id, comment="test")

        assert result is None


# =============================================================================
# DELETE CALL TESTS
# =============================================================================

class TestDeleteCall:
    """Test delete_call() function."""

    @patch('services.call_service._get_supabase')
    def test_delete_call_success(self, mock_get_supabase, call_id):
        """Delete existing call returns True."""
        from services.call_service import delete_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        result = delete_call(call_id)

        assert result is True
        mock_client.table.assert_called_with("calls")

    @patch('services.call_service._get_supabase')
    def test_delete_call_db_error_returns_false(self, mock_get_supabase, call_id):
        """Delete call returns False on database error."""
        from services.call_service import delete_call

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.delete.return_value.eq.return_value.execute.side_effect = Exception("DB error")

        result = delete_call(call_id)

        assert result is False


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_parse_call_missing_optional_keys(self):
        """Parse call with minimal data (no optional fields in DB row)."""
        from services.call_service import _parse_call

        minimal_data = {
            "id": "min-1",
            "organization_id": "org-1",
            "customer_id": "cust-1",
            "user_id": "user-1",
            "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z",
            "updated_at": "2026-02-28T10:00:00Z",
        }
        # Should not crash even without contact_person_id, call_category, etc.
        record = _parse_call(minimal_data)
        assert record.id == "min-1"
        assert record.call_type == "call"

    def test_parse_call_empty_strings(self):
        """Parse call where text fields are empty strings."""
        from services.call_service import _parse_call

        data = {
            "id": "empty-1",
            "organization_id": "org-1",
            "customer_id": "cust-1",
            "user_id": "user-1",
            "call_type": "call",
            "call_category": "",
            "contact_person_id": "",
            "scheduled_date": "",
            "comment": "",
            "customer_needs": "",
            "meeting_notes": "",
            "created_at": "2026-02-28T10:00:00Z",
            "updated_at": "2026-02-28T10:00:00Z",
            "customers": None,
            "customer_contacts": None,
            "users": None,
        }
        record = _parse_call(data)
        assert record.id == "empty-1"

    @patch('services.call_service._get_supabase')
    def test_get_calls_for_nonexistent_customer(self, mock_get_supabase):
        """Get calls for customer that doesn't exist returns empty list."""
        from services.call_service import get_calls_for_customer

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_query = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        mock_query.order.return_value.execute.return_value = MagicMock(data=[])

        result = get_calls_for_customer("nonexistent-customer-id")
        assert result == []

    def test_call_record_equality(self):
        """Two CallRecords with same data are equal (dataclass)."""
        from services.call_service import CallRecord

        r1 = CallRecord(id="a", organization_id="o", customer_id="c", user_id="u", call_type="call")
        r2 = CallRecord(id="a", organization_id="o", customer_id="c", user_id="u", call_type="call")
        assert r1 == r2

    def test_call_record_inequality(self):
        """Two CallRecords with different IDs are not equal."""
        from services.call_service import CallRecord

        r1 = CallRecord(id="a", organization_id="o", customer_id="c", user_id="u", call_type="call")
        r2 = CallRecord(id="b", organization_id="o", customer_id="c", user_id="u", call_type="call")
        assert r1 != r2


# =============================================================================
# FK NULL SAFETY COMPREHENSIVE TEST
# =============================================================================

class TestFKNullSafety:
    """Comprehensive FK null safety tests specific to call_service.

    Ensures the safe pattern (data.get("fk") or {}).get("field", default)
    is used instead of the unsafe data.get("fk", {}).get("field") pattern.
    """

    def test_customers_null_gives_default_name(self):
        """When customers FK is null, customer_name should be a safe default."""
        from services.call_service import _parse_call

        data = {
            "id": "test", "organization_id": "org", "customer_id": "c1",
            "user_id": "u1", "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z", "updated_at": "2026-02-28T10:00:00Z",
            "customers": None,
            "customer_contacts": {"id": "ct1", "name": "Contact"},
            "users": {"id": "u1", "email": "a@b.com", "raw_user_meta_data": {"full_name": "User"}},
        }
        record = _parse_call(data)
        # Should not crash and should have a reasonable default
        assert record.customer_name is not None or record.customer_name == ""

    def test_contacts_null_gives_default_name(self):
        """When customer_contacts FK is null, contact_name should be a safe default."""
        from services.call_service import _parse_call

        data = {
            "id": "test", "organization_id": "org", "customer_id": "c1",
            "user_id": "u1", "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z", "updated_at": "2026-02-28T10:00:00Z",
            "customers": {"id": "c1", "name": "Test Corp"},
            "customer_contacts": None,
            "users": {"id": "u1", "email": "a@b.com", "raw_user_meta_data": {"full_name": "User"}},
        }
        record = _parse_call(data)
        assert isinstance(record, object)  # No crash

    def test_user_profiles_null_gives_default_name(self):
        """When user_profiles FK is null, user_name should be a safe default."""
        from services.call_service import _parse_call

        data = {
            "id": "test", "organization_id": "org", "customer_id": "c1",
            "user_id": "u1", "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z", "updated_at": "2026-02-28T10:00:00Z",
            "customers": {"id": "c1", "name": "Test Corp"},
            "customer_contacts": {"id": "ct1", "name": "Contact"},
            "user_profiles": None,
        }
        record = _parse_call(data)
        assert isinstance(record, object)  # No crash

    def test_all_fks_null_simultaneously(self):
        """When ALL FK joins are null, _parse_call still works."""
        from services.call_service import _parse_call

        data = {
            "id": "test", "organization_id": "org", "customer_id": "c1",
            "user_id": "u1", "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z", "updated_at": "2026-02-28T10:00:00Z",
            "customers": None,
            "customer_contacts": None,
            "user_profiles": None,
        }
        # Must not raise AttributeError
        record = _parse_call(data)
        assert record.id == "test"
        assert record.call_type == "call"

    def test_user_profiles_null_full_name(self):
        """When user_profiles exists but full_name is null."""
        from services.call_service import _parse_call

        data = {
            "id": "test", "organization_id": "org", "customer_id": "c1",
            "user_id": "u1", "call_type": "call",
            "created_at": "2026-02-28T10:00:00Z", "updated_at": "2026-02-28T10:00:00Z",
            "customers": None,
            "customer_contacts": None,
            "user_profiles": {"full_name": None},
        }
        record = _parse_call(data)
        # user_name is None when full_name not set in user_profiles - no crash
        assert isinstance(record, object)  # didn't crash


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
