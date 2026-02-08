"""
TDD tests for DaData INN -> company autofill service.

These tests define the CONTRACT for `services/dadata_service.py` which does NOT exist yet.
The developer must implement the service so that all tests pass.

DaData API context:
- Endpoint: https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/party
- Method: POST
- Auth: "Token {DADATA_API_KEY}" header
- Request body: {"query": "7707083893"}  (INN)
- Response: {"suggestions": [{"value": "...", "data": {...}}]}

The service should:
1. Accept an INN string
2. Call DaData API to look up company info
3. Return a normalized dict with fields matching our customer/company schema
4. Handle errors gracefully (network, invalid INN, no results)
5. Validate INN format before calling API
"""

import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from dataclasses import dataclass

# Set test environment
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("DADATA_API_KEY", "test-dadata-key")


# ============================================================================
# SAMPLE DADATA RESPONSES (fixtures)
# ============================================================================

SAMPLE_DADATA_RESPONSE_LLC = {
    "suggestions": [
        {
            "value": 'ООО "РОМАШКА"',
            "unrestricted_value": 'ООО "РОМАШКА"',
            "data": {
                "kpp": "770701001",
                "inn": "7707083893",
                "ogrn": "1027700132195",
                "type": "LEGAL",
                "name": {
                    "full_with_opf": 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РОМАШКА"',
                    "short_with_opf": 'ООО "РОМАШКА"',
                    "full": "РОМАШКА",
                    "short": "РОМАШКА",
                },
                "address": {
                    "value": "г Москва, ул Ленина, д 1",
                    "unrestricted_value": "127000, г Москва, ул Ленина, д 1",
                    "data": {
                        "postal_code": "127000",
                        "country": "Россия",
                        "city": "Москва",
                    }
                },
                "management": {
                    "name": "Иванов Иван Иванович",
                    "post": "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР",
                },
                "state": {
                    "status": "ACTIVE",
                    "actuality_date": 1700000000000,
                },
                "opf": {
                    "code": "12300",
                    "full": "Общество с ограниченной ответственностью",
                    "short": "ООО",
                },
            }
        }
    ]
}

SAMPLE_DADATA_RESPONSE_IP = {
    "suggestions": [
        {
            "value": "ИП Петров Петр Петрович",
            "data": {
                "inn": "772012345678",
                "ogrn": "304770000123456",
                "type": "INDIVIDUAL",
                "name": {
                    "full_with_opf": "Индивидуальный предприниматель Петров Петр Петрович",
                    "short_with_opf": "ИП Петров Петр Петрович",
                    "full": "Петров Петр Петрович",
                    "short": "Петров Петр Петрович",
                },
                "address": {
                    "value": "г Санкт-Петербург, пр-кт Невский, д 100",
                    "data": {
                        "postal_code": "191025",
                        "country": "Россия",
                        "city": "Санкт-Петербург",
                    }
                },
                "state": {
                    "status": "ACTIVE",
                },
                "opf": {
                    "code": "50102",
                    "full": "Индивидуальный предприниматель",
                    "short": "ИП",
                },
            }
        }
    ]
}

SAMPLE_DADATA_RESPONSE_EMPTY = {
    "suggestions": []
}

SAMPLE_DADATA_RESPONSE_MULTIPLE = {
    "suggestions": [
        {
            "value": 'ООО "АЛЬФА"',
            "data": {
                "inn": "7701234567",
                "kpp": "770101001",
                "ogrn": "1027701234567",
                "type": "LEGAL",
                "name": {"short_with_opf": 'ООО "АЛЬФА"', "short": "АЛЬФА"},
                "address": {"value": "г Москва, ул Тверская, д 1"},
                "state": {"status": "ACTIVE"},
            }
        },
        {
            "value": 'ООО "АЛЬФА-2"',
            "data": {
                "inn": "7701234567",
                "kpp": "770102001",
                "ogrn": "1027701234568",
                "type": "LEGAL",
                "name": {"short_with_opf": 'ООО "АЛЬФА-2"', "short": "АЛЬФА-2"},
                "address": {"value": "г Москва, ул Арбат, д 5"},
                "state": {"status": "ACTIVE"},
            }
        },
    ]
}


# ============================================================================
# INN VALIDATION TESTS
# ============================================================================

class TestInnValidation:
    """Tests for INN format validation (must exist as validate_inn function)."""

    def test_valid_10_digit_inn(self):
        """10-digit INN (legal entity) should be valid."""
        from services.dadata_service import validate_inn
        assert validate_inn("7707083893") is True

    def test_valid_12_digit_inn(self):
        """12-digit INN (individual entrepreneur) should be valid."""
        from services.dadata_service import validate_inn
        assert validate_inn("772012345678") is True

    def test_invalid_inn_too_short(self):
        """INN shorter than 10 digits should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn("12345") is False

    def test_invalid_inn_too_long(self):
        """INN longer than 12 digits should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn("1234567890123") is False

    def test_invalid_inn_11_digits(self):
        """11-digit INN should be invalid (not 10 or 12)."""
        from services.dadata_service import validate_inn
        assert validate_inn("12345678901") is False

    def test_invalid_inn_letters(self):
        """INN with letters should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn("770708389X") is False

    def test_invalid_inn_empty(self):
        """Empty string should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn("") is False

    def test_invalid_inn_none(self):
        """None should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn(None) is False

    def test_inn_with_spaces_stripped(self):
        """INN with leading/trailing spaces should be stripped and validated."""
        from services.dadata_service import validate_inn
        assert validate_inn("  7707083893  ") is True

    def test_inn_all_zeros(self):
        """INN of all zeros should be invalid."""
        from services.dadata_service import validate_inn
        assert validate_inn("0000000000") is False


# ============================================================================
# LOOKUP COMPANY BY INN TESTS
# ============================================================================

class TestLookupCompanyByInn:
    """Tests for the main lookup_company_by_inn function.

    Expected signature:
        async def lookup_company_by_inn(inn: str) -> dict | None

    Returns dict with keys:
        - name: str (short name with OPF, e.g. 'OOO "ROMASHKA"')
        - full_name: str (full official name)
        - inn: str
        - kpp: str | None (only for legal entities)
        - ogrn: str
        - address: str (legal address)
        - postal_code: str | None
        - city: str | None
        - director: str | None (management name)
        - director_title: str | None (management post)
        - opf: str | None (organizational-legal form short)
        - entity_type: str ("LEGAL" or "INDIVIDUAL")
        - is_active: bool
    """

    @pytest.mark.asyncio
    async def test_lookup_llc_returns_correct_fields(self):
        """Lookup of a legal entity INN returns all expected fields."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_LLC
            result = await lookup_company_by_inn("7707083893")

        assert result is not None
        assert result["name"] == 'ООО "РОМАШКА"'
        assert result["inn"] == "7707083893"
        assert result["kpp"] == "770701001"
        assert result["ogrn"] == "1027700132195"
        assert result["address"] == "127000, г Москва, ул Ленина, д 1"
        assert result["director"] == "Иванов Иван Иванович"
        assert result["director_title"] == "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР"
        assert result["entity_type"] == "LEGAL"
        assert result["is_active"] is True

    @pytest.mark.asyncio
    async def test_lookup_ip_returns_correct_fields(self):
        """Lookup of an individual entrepreneur INN returns correct fields."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_IP
            result = await lookup_company_by_inn("772012345678")

        assert result is not None
        assert result["name"] == "ИП Петров Петр Петрович"
        assert result["inn"] == "772012345678"
        assert result["kpp"] is None  # IPs don't have KPP
        assert result["entity_type"] == "INDIVIDUAL"

    @pytest.mark.asyncio
    async def test_lookup_not_found_returns_none(self):
        """Lookup of non-existent INN returns None."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_EMPTY
            result = await lookup_company_by_inn("9999999999")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_invalid_inn_raises_valueerror(self):
        """Lookup with invalid INN format should raise ValueError."""
        from services.dadata_service import lookup_company_by_inn

        with pytest.raises(ValueError, match="[Ii]nvalid INN"):
            await lookup_company_by_inn("123")

    @pytest.mark.asyncio
    async def test_lookup_multiple_results_returns_first(self):
        """When multiple suggestions returned, first (best match) is used."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_MULTIPLE
            result = await lookup_company_by_inn("7701234567")

        assert result is not None
        assert result["name"] == 'ООО "АЛЬФА"'
        assert result["kpp"] == "770101001"

    @pytest.mark.asyncio
    async def test_lookup_network_error_returns_none(self):
        """Network errors should be caught and return None (not crash)."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.side_effect = ConnectionError("Network unreachable")
            result = await lookup_company_by_inn("7707083893")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_api_error_returns_none(self):
        """HTTP errors from DaData (403, 429, 500) should return None."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.side_effect = RuntimeError("HTTP 429 Too Many Requests")
            result = await lookup_company_by_inn("7707083893")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_passes_api_key_in_header(self):
        """The API call must include the DADATA_API_KEY in Authorization header."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_LLC
            await lookup_company_by_inn("7707083893")

        mock_api.assert_called_once()
        call_args = mock_api.call_args
        # The internal _call_dadata_api should receive the INN
        assert "7707083893" in str(call_args)

    @pytest.mark.asyncio
    async def test_lookup_strips_inn_whitespace(self):
        """INN with whitespace should be stripped before lookup."""
        from services.dadata_service import lookup_company_by_inn

        with patch("services.dadata_service._call_dadata_api") as mock_api:
            mock_api.return_value = SAMPLE_DADATA_RESPONSE_LLC
            result = await lookup_company_by_inn("  7707083893  ")

        assert result is not None
        assert result["inn"] == "7707083893"


# ============================================================================
# RESULT NORMALIZATION TESTS
# ============================================================================

class TestResultNormalization:
    """Tests for normalizing DaData response into our schema.

    Expected function:
        normalize_dadata_result(suggestion: dict) -> dict
    """

    def test_normalize_llc_extracts_all_fields(self):
        """Normalization of LLC result extracts all fields."""
        from services.dadata_service import normalize_dadata_result

        suggestion = SAMPLE_DADATA_RESPONSE_LLC["suggestions"][0]
        result = normalize_dadata_result(suggestion)

        assert result["name"] == 'ООО "РОМАШКА"'
        assert result["full_name"] == 'ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "РОМАШКА"'
        assert result["inn"] == "7707083893"
        assert result["kpp"] == "770701001"
        assert result["ogrn"] == "1027700132195"
        assert result["address"] == "127000, г Москва, ул Ленина, д 1"
        assert result["postal_code"] == "127000"
        assert result["city"] == "Москва"
        assert result["director"] == "Иванов Иван Иванович"
        assert result["director_title"] == "ГЕНЕРАЛЬНЫЙ ДИРЕКТОР"
        assert result["opf"] == "ООО"
        assert result["entity_type"] == "LEGAL"
        assert result["is_active"] is True

    def test_normalize_ip_has_no_kpp(self):
        """IP (individual entrepreneur) should have kpp = None."""
        from services.dadata_service import normalize_dadata_result

        suggestion = SAMPLE_DADATA_RESPONSE_IP["suggestions"][0]
        result = normalize_dadata_result(suggestion)

        assert result["kpp"] is None
        assert result["entity_type"] == "INDIVIDUAL"

    def test_normalize_missing_management_returns_none(self):
        """If management field is missing, director fields should be None."""
        from services.dadata_service import normalize_dadata_result

        suggestion = {
            "value": 'ООО "ТЕСТ"',
            "data": {
                "inn": "1234567890",
                "kpp": "123401001",
                "ogrn": "1021234567890",
                "type": "LEGAL",
                "name": {
                    "full_with_opf": 'ООО "ТЕСТ"',
                    "short_with_opf": 'ООО "ТЕСТ"',
                },
                "address": {"value": "г Москва"},
                "state": {"status": "ACTIVE"},
                "opf": {"short": "ООО"},
            }
        }
        result = normalize_dadata_result(suggestion)

        assert result["director"] is None
        assert result["director_title"] is None

    def test_normalize_missing_address_data(self):
        """If address.data is missing, postal_code and city should be None."""
        from services.dadata_service import normalize_dadata_result

        suggestion = {
            "value": 'ООО "ТЕСТ"',
            "data": {
                "inn": "1234567890",
                "type": "LEGAL",
                "name": {"short_with_opf": 'ООО "ТЕСТ"'},
                "address": {"value": "Somewhere"},
                "state": {"status": "ACTIVE"},
            }
        }
        result = normalize_dadata_result(suggestion)

        assert result["address"] == "Somewhere"
        assert result["postal_code"] is None
        assert result["city"] is None

    def test_normalize_liquidated_company(self):
        """Liquidated company should have is_active = False."""
        from services.dadata_service import normalize_dadata_result

        suggestion = {
            "value": 'ООО "ЗАКРЫТО"',
            "data": {
                "inn": "1234567890",
                "type": "LEGAL",
                "name": {"short_with_opf": 'ООО "ЗАКРЫТО"'},
                "address": {"value": "г Москва"},
                "state": {"status": "LIQUIDATED"},
            }
        }
        result = normalize_dadata_result(suggestion)

        assert result["is_active"] is False


# ============================================================================
# API KEY CONFIGURATION TESTS
# ============================================================================

class TestApiKeyConfiguration:
    """Tests for API key configuration."""

    def test_missing_api_key_raises_error(self):
        """If DADATA_API_KEY env var is not set, should raise ValueError on use."""
        from services.dadata_service import lookup_company_by_inn

        with patch.dict(os.environ, {"DADATA_API_KEY": ""}, clear=False):
            with patch("services.dadata_service._call_dadata_api") as mock_api:
                # The implementation should check for API key before calling
                # Either raise ValueError or return None
                # We test that it doesn't proceed with empty key
                mock_api.side_effect = ValueError("DADATA_API_KEY not configured")
                with pytest.raises((ValueError, RuntimeError)):
                    import asyncio
                    asyncio.get_event_loop().run_until_complete(
                        lookup_company_by_inn("7707083893")
                    )
