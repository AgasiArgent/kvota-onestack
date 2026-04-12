"""
Tests for VAT Rate Service — lookup, default fallback, list, and upsert.

Phase 4a Task 1.2: services/vat_service.py

Tests cover:
- Module imports (vat_service exists and exports expected symbols)
- get_vat_rate() returns correct rate for seeded country (EAEU at 0%)
- get_vat_rate() returns correct rate for import country (20%)
- get_vat_rate() returns 20.00 default for unknown country
- list_all_rates() returns list of all rows
- upsert_rate() creates new rate
- upsert_rate() updates existing rate

TDD: Tests written BEFORE implementation.
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime
from uuid import uuid4

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def user_id():
    """Admin user ID for upsert tests."""
    return str(uuid4())


@pytest.fixture
def eaeu_rate_row():
    """Sample EAEU country rate row (0% VAT)."""
    return {
        "country_code": "KZ",
        "rate": "0.00",
        "notes": "ЕАЭС — косвенный НДС через декларацию",
        "updated_at": "2026-04-10T12:00:00Z",
        "updated_by": None,
    }


@pytest.fixture
def import_rate_row():
    """Sample import country rate row (20% VAT)."""
    return {
        "country_code": "CN",
        "rate": "20.00",
        "notes": "Китай — стандартная ставка",
        "updated_at": "2026-04-10T12:00:00Z",
        "updated_by": None,
    }


@pytest.fixture
def all_rate_rows():
    """Multiple rate rows for list_all_rates tests."""
    return [
        {"country_code": "RU", "rate": "0.00", "notes": "Россия", "updated_at": "2026-04-10T12:00:00Z", "updated_by": None},
        {"country_code": "KZ", "rate": "0.00", "notes": "ЕАЭС", "updated_at": "2026-04-10T12:00:00Z", "updated_by": None},
        {"country_code": "CN", "rate": "20.00", "notes": "Китай", "updated_at": "2026-04-10T12:00:00Z", "updated_by": None},
        {"country_code": "DE", "rate": "20.00", "notes": "Германия", "updated_at": "2026-04-10T12:00:00Z", "updated_by": None},
    ]


# =============================================================================
# IMPORT TESTS
# =============================================================================

class TestModuleImports:
    """Verify vat_service module exists and exports expected symbols."""

    def test_import_vat_service_module(self):
        from services import vat_service
        assert vat_service is not None

    def test_import_get_vat_rate(self):
        from services.vat_service import get_vat_rate
        assert get_vat_rate is not None

    def test_import_list_all_rates(self):
        from services.vat_service import list_all_rates
        assert list_all_rates is not None

    def test_import_upsert_rate(self):
        from services.vat_service import upsert_rate
        assert upsert_rate is not None


# =============================================================================
# get_vat_rate TESTS
# =============================================================================

class TestGetVatRate:
    """Test VAT rate lookup by country code."""

    @patch('services.vat_service._get_supabase')
    def test_returns_rate_for_eaeu_country(self, mock_get_supabase, eaeu_rate_row):
        """EAEU country (KZ) should return 0% rate."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=eaeu_rate_row
        )

        result = get_vat_rate("KZ")
        assert result == Decimal("0.00")

    @patch('services.vat_service._get_supabase')
    def test_returns_rate_for_import_country(self, mock_get_supabase, import_rate_row):
        """Import country (CN) should return 20% rate."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=import_rate_row
        )

        result = get_vat_rate("CN")
        assert result == Decimal("20.00")

    @patch('services.vat_service._get_supabase')
    def test_returns_default_for_unknown_country(self, mock_get_supabase):
        """Unknown country code should return default 20.00."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        # Supabase .single() raises an exception when no row is found
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception(
            "No rows found"
        )

        result = get_vat_rate("XX")
        assert result == Decimal("20.00")

    @patch('services.vat_service._get_supabase')
    def test_queries_vat_rates_by_country_table(self, mock_get_supabase, eaeu_rate_row):
        """Should query the vat_rates_by_country table."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=eaeu_rate_row
        )

        get_vat_rate("KZ")
        mock_client.table.assert_called_with("vat_rates_by_country")

    @patch('services.vat_service._get_supabase')
    def test_filters_by_country_code(self, mock_get_supabase, eaeu_rate_row):
        """Should filter by country_code column."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=eaeu_rate_row
        )

        get_vat_rate("KZ")
        mock_client.table.return_value.select.return_value.eq.assert_called_with("country_code", "KZ")

    @patch('services.vat_service._get_supabase')
    def test_uppercases_country_code(self, mock_get_supabase, eaeu_rate_row):
        """Should uppercase the country code before querying."""
        from services.vat_service import get_vat_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data=eaeu_rate_row
        )

        get_vat_rate("kz")
        mock_client.table.return_value.select.return_value.eq.assert_called_with("country_code", "KZ")


# =============================================================================
# list_all_rates TESTS
# =============================================================================

class TestListAllRates:
    """Test listing all VAT rates for admin display."""

    @patch('services.vat_service._get_supabase')
    def test_returns_list(self, mock_get_supabase, all_rate_rows):
        """list_all_rates returns a list of dicts."""
        from services.vat_service import list_all_rates

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=all_rate_rows
        )

        result = list_all_rates()
        assert isinstance(result, list)
        assert len(result) == 4

    @patch('services.vat_service._get_supabase')
    def test_returns_all_rows(self, mock_get_supabase, all_rate_rows):
        """Should return every row from vat_rates_by_country."""
        from services.vat_service import list_all_rates

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=all_rate_rows
        )

        result = list_all_rates()
        codes = [r["country_code"] for r in result]
        assert "RU" in codes
        assert "CN" in codes

    @patch('services.vat_service._get_supabase')
    def test_queries_correct_table(self, mock_get_supabase, all_rate_rows):
        """Should query vat_rates_by_country table."""
        from services.vat_service import list_all_rates

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=all_rate_rows
        )

        list_all_rates()
        mock_client.table.assert_called_with("vat_rates_by_country")

    @patch('services.vat_service._get_supabase')
    def test_returns_empty_list_when_no_rates(self, mock_get_supabase):
        """Returns empty list when table has no rows."""
        from services.vat_service import list_all_rates

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = list_all_rates()
        assert result == []


# =============================================================================
# upsert_rate TESTS
# =============================================================================

class TestUpsertRate:
    """Test creating and updating VAT rates."""

    @patch('services.vat_service._get_supabase')
    def test_upsert_creates_new_rate(self, mock_get_supabase, user_id):
        """upsert_rate should insert a new rate for unknown country."""
        from services.vat_service import upsert_rate

        upserted_row = {
            "country_code": "BR",
            "rate": "15.00",
            "notes": "Бразилия",
            "updated_at": "2026-04-10T14:00:00Z",
            "updated_by": user_id,
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[upserted_row]
        )

        result = upsert_rate("BR", Decimal("15.00"), "Бразилия", user_id)
        assert result["country_code"] == "BR"
        assert result["rate"] == "15.00"

    @patch('services.vat_service._get_supabase')
    def test_upsert_updates_existing_rate(self, mock_get_supabase, user_id):
        """upsert_rate should update an existing rate."""
        from services.vat_service import upsert_rate

        updated_row = {
            "country_code": "CN",
            "rate": "25.00",
            "notes": "Китай — повышенная ставка",
            "updated_at": "2026-04-10T14:00:00Z",
            "updated_by": user_id,
        }

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[updated_row]
        )

        result = upsert_rate("CN", Decimal("25.00"), "Китай — повышенная ставка", user_id)
        assert result["country_code"] == "CN"
        assert result["rate"] == "25.00"

    @patch('services.vat_service._get_supabase')
    def test_upsert_uses_vat_rates_table(self, mock_get_supabase, user_id):
        """Should upsert into vat_rates_by_country table."""
        from services.vat_service import upsert_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"country_code": "BR", "rate": "15.00", "notes": None, "updated_at": "2026-04-10T14:00:00Z", "updated_by": user_id}]
        )

        upsert_rate("BR", Decimal("15.00"), None, user_id)
        mock_client.table.assert_called_with("vat_rates_by_country")

    @patch('services.vat_service._get_supabase')
    def test_upsert_passes_correct_data(self, mock_get_supabase, user_id):
        """Upsert data should contain country_code, rate, notes, and updated_by."""
        from services.vat_service import upsert_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"country_code": "BR", "rate": "15.00", "notes": "Test", "updated_at": "2026-04-10T14:00:00Z", "updated_by": user_id}]
        )

        upsert_rate("BR", Decimal("15.00"), "Test", user_id)

        call_args = mock_client.table.return_value.upsert.call_args[0][0]
        assert call_args["country_code"] == "BR"
        assert float(call_args["rate"]) == 15.00
        assert call_args["notes"] == "Test"
        assert call_args["updated_by"] == user_id

    @patch('services.vat_service._get_supabase')
    def test_upsert_with_none_notes(self, mock_get_supabase, user_id):
        """upsert_rate should accept None for notes."""
        from services.vat_service import upsert_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"country_code": "BR", "rate": "15.00", "notes": None, "updated_at": "2026-04-10T14:00:00Z", "updated_by": user_id}]
        )

        result = upsert_rate("BR", Decimal("15.00"), None, user_id)
        assert result is not None

    @patch('services.vat_service._get_supabase')
    def test_upsert_uppercases_country_code(self, mock_get_supabase, user_id):
        """Should uppercase the country code before upserting."""
        from services.vat_service import upsert_rate

        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
            data=[{"country_code": "BR", "rate": "15.00", "notes": None, "updated_at": "2026-04-10T14:00:00Z", "updated_by": user_id}]
        )

        upsert_rate("br", Decimal("15.00"), None, user_id)

        call_args = mock_client.table.return_value.upsert.call_args[0][0]
        assert call_args["country_code"] == "BR"
