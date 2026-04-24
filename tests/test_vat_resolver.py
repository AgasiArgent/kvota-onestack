"""
Tests for the VAT resolver — services.vat_service.resolve_vat_for_invoice.

Procurement bugs fix (April 2026) — Requirement 3.

Rule:
  rate = domestic VAT rate for country if supplier.country_code == buyer.country_code
       = 0 ("export_zero_rated") if codes differ
       = 0 ("unknown") if either code is NULL or missing

The service uses kvota.vat_rates_by_country as the source of truth for domestic
rates (per Migration 296 seed). Tests mock Supabase so we never touch a real DB.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# HELPERS
# =============================================================================


def _buyer_chain(country_code: str | None):
    """Build a Supabase mock chain that returns a buyer row with given country_code.

    Mirrors the chain used in resolve_vat_for_invoice:
        client.table("buyer_companies").select("country_code")
              .eq("id", ...).maybe_single().execute() -> MagicMock(data={"country_code": ...})
    """
    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.maybe_single.return_value = chain
    chain.execute.return_value = MagicMock(data={"country_code": country_code})
    return chain


def _buyer_not_found_chain():
    """Supabase mock where the buyer row is missing (data=None)."""
    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.maybe_single.return_value = chain
    chain.execute.return_value = MagicMock(data=None)
    return chain


# =============================================================================
# Country match — domestic rate lookup
# =============================================================================


class TestDomesticMatch:
    @patch("services.vat_service._get_supabase")
    def test_ru_buyer_and_ru_supplier_returns_22(self, mock_get_sb):
        """RU buyer + RU supplier → rate 22 per Migration 296."""
        from services.vat_service import resolve_vat_for_invoice

        # Mock for resolver's buyer fetch
        supabase_client = _buyer_chain("RU")

        # Mock for inner get_vat_rate() lookup against vat_rates_by_country
        inner = MagicMock()
        inner.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"rate": "22.00"}
        )
        mock_get_sb.return_value = inner

        result = resolve_vat_for_invoice(
            supplier_country_code="RU",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result == {"rate": Decimal("22.00"), "reason": "domestic"}

    @patch("services.vat_service._get_supabase")
    def test_ch_buyer_and_ch_supplier_returns_seven_seven(self, mock_get_sb):
        """CH buyer + CH supplier → rate 7.7 per Migration 296."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("CH")

        inner = MagicMock()
        inner.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"rate": "7.7"}
        )
        mock_get_sb.return_value = inner

        result = resolve_vat_for_invoice(
            supplier_country_code="CH",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result["rate"] == Decimal("7.7")
        assert result["reason"] == "domestic"

    @patch("services.vat_service._get_supabase")
    def test_case_insensitive_country_match(self, mock_get_sb):
        """Lowercase supplier code normalizes to match uppercase buyer code."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        inner = MagicMock()
        inner.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"rate": "19.00"}
        )
        mock_get_sb.return_value = inner

        result = resolve_vat_for_invoice(
            supplier_country_code="de",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result["reason"] == "domestic"
        assert result["rate"] == Decimal("19.00")


# =============================================================================
# Country mismatch — export zero-rated
# =============================================================================


class TestExportZeroRated:
    def test_de_buyer_and_cn_supplier_returns_zero(self):
        """DE buyer + CN supplier → rate=0, reason=export_zero_rated."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        result = resolve_vat_for_invoice(
            supplier_country_code="CN",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result == {"rate": Decimal("0"), "reason": "export_zero_rated"}

    def test_ru_buyer_and_tr_supplier_returns_zero(self):
        """RU buyer + TR supplier → 0% export."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("RU")

        result = resolve_vat_for_invoice(
            supplier_country_code="TR",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result["rate"] == Decimal("0")
        assert result["reason"] == "export_zero_rated"


# =============================================================================
# Missing codes — fail-closed to 0% unknown
# =============================================================================


class TestUnknownFailClosed:
    def test_supplier_code_none_returns_unknown(self):
        """supplier_country_code=None with valid buyer → unknown."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        result = resolve_vat_for_invoice(
            supplier_country_code=None,
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result == {"rate": Decimal("0"), "reason": "unknown"}

    def test_buyer_country_code_none_returns_unknown(self):
        """buyer.country_code is None in DB → unknown even with valid supplier code."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain(None)

        result = resolve_vat_for_invoice(
            supplier_country_code="DE",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result == {"rate": Decimal("0"), "reason": "unknown"}

    def test_both_codes_none_returns_unknown(self):
        """Both codes None → unknown."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain(None)

        result = resolve_vat_for_invoice(
            supplier_country_code=None,
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result == {"rate": Decimal("0"), "reason": "unknown"}

    def test_empty_supplier_code_returns_unknown(self):
        """Empty-string supplier code normalizes to unknown (not a validation error)."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        result = resolve_vat_for_invoice(
            supplier_country_code="",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result["reason"] == "unknown"
        assert result["rate"] == Decimal("0")

    def test_whitespace_only_supplier_code_returns_unknown(self):
        """Whitespace-only supplier code normalizes to unknown."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        result = resolve_vat_for_invoice(
            supplier_country_code="   ",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert result["reason"] == "unknown"


# =============================================================================
# Error cases — LookupError & ValueError
# =============================================================================


class TestErrors:
    def test_unknown_buyer_company_id_raises_lookup_error(self):
        """Missing buyer row → LookupError (handler maps to 404)."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_not_found_chain()

        with pytest.raises(LookupError):
            resolve_vat_for_invoice(
                supplier_country_code="DE",
                buyer_company_id=str(uuid4()),
                supabase_client=supabase_client,
            )

    def test_malformed_supplier_country_code_raises_value_error(self):
        """Non-2-letter supplier code → ValueError (handler maps to 400)."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        with pytest.raises(ValueError):
            resolve_vat_for_invoice(
                supplier_country_code="123",
                buyer_company_id=str(uuid4()),
                supabase_client=supabase_client,
            )

    def test_numeric_supplier_country_code_raises_value_error(self):
        """Digits in supplier code → ValueError."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        with pytest.raises(ValueError):
            resolve_vat_for_invoice(
                supplier_country_code="D1",
                buyer_company_id=str(uuid4()),
                supabase_client=supabase_client,
            )

    def test_too_long_supplier_country_code_raises_value_error(self):
        """3+ character supplier code → ValueError."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        with pytest.raises(ValueError):
            resolve_vat_for_invoice(
                supplier_country_code="DEU",
                buyer_company_id=str(uuid4()),
                supabase_client=supabase_client,
            )


# =============================================================================
# Return-type contract
# =============================================================================


class TestReturnContract:
    def test_return_value_has_rate_and_reason_keys(self):
        """Return dict always has exactly 'rate' and 'reason' keys."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("CN")

        result = resolve_vat_for_invoice(
            supplier_country_code="DE",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert set(result.keys()) == {"rate", "reason"}

    def test_rate_is_decimal_type(self):
        """Rate is always a Decimal (not float) for precision."""
        from services.vat_service import resolve_vat_for_invoice

        supabase_client = _buyer_chain("DE")

        result = resolve_vat_for_invoice(
            supplier_country_code="CN",
            buyer_company_id=str(uuid4()),
            supabase_client=supabase_client,
        )

        assert isinstance(result["rate"], Decimal)
