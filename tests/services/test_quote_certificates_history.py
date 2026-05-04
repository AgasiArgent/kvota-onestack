"""Tests for services/quote_certificates_history.py — Phase B Req 5.

Mirror of ``tests/services/test_customs_user_choices.py`` (Phase A blueprint,
mock Supabase client + driven query chain). Covers:

  * 2-of-3 loose match (hs_code+brand, brand+supplier, hs_code+supplier).
  * 1-of-3 → no match.
  * 12-month cutoff (server filter relayed via ``.gte`` call assertion).
  * Org isolation (filter relayed via ``.eq("quotes.organization_id", ...)``).
  * Excludes the current quote (filter relayed via ``.neq("quote_id", ...)``).
  * Excludes ``is_custom_expense=TRUE`` (filter relayed via
    ``.eq("is_custom_expense", False)``).
  * ``is_actual`` derived from ``valid_until`` (NULL/future → True; past → False).
  * Returns the latest of multiple matches (DESC ordering relayed via ``.order``).
  * Swallows DB errors with logger.warning + None.
  * Skips round-trip when fewer than 2 non-null inputs are supplied.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from services.quote_certificates_history import (
    HistoryCertMatch,
    find_match,
)


# ---------------------------------------------------------------------------
# Mock-Supabase helpers
# ---------------------------------------------------------------------------


def _make_select_sb(rows: list[dict]):
    """Mock supabase whose SELECT chain returns ``rows``.

    The chain mirrors the production call order:
        .select(...).eq(...).eq(...).neq(...).gte(...).order(...).execute()
    """
    sb = MagicMock()
    chain = MagicMock()
    (
        chain.select.return_value
             .eq.return_value
             .eq.return_value
             .neq.return_value
             .gte.return_value
             .order.return_value
             .execute.return_value
    ) = MagicMock(data=rows)
    sb.table.return_value = chain
    return sb


def _make_cert_row(
    *,
    cert_id: str = "cert-uuid-1",
    type_: str = "ДС ТР ТС",
    number: str | None = "TC-RU-12345",
    issuer: str | None = "ABC Cert Center",
    legal_doc: str | None = "ТР ТС 010/2011",
    issued_at: str | None = "2025-04-01",
    valid_until: str | None = "2027-04-01",
    cost_rub: float | str = 12500.00,
    created_at: str = "2026-04-22T10:30:00+00:00",
    quote_id: str = "src-quote-uuid",
    attachments: list[dict] | None = None,
) -> dict:
    """Build a PostgREST-shaped certificate row payload."""
    if attachments is None:
        attachments = [
            {
                "item_id": "src-item-uuid",
                "quote_items": {
                    "id": "src-item-uuid",
                    "hs_code": "8504408200",
                    "brand": "Acme",
                    "supplier_id": "supplier-uuid-1",
                },
            }
        ]
    return {
        "id": cert_id,
        "type": type_,
        "number": number,
        "issuer": issuer,
        "legal_doc": legal_doc,
        "issued_at": issued_at,
        "valid_until": valid_until,
        "cost_rub": cost_rub,
        "created_at": created_at,
        "quote_id": quote_id,
        "quotes": {"organization_id": "org-uuid-1"},
        "quote_certificate_items": attachments,
    }


# ---------------------------------------------------------------------------
# Loose-match behaviour
# ---------------------------------------------------------------------------


def test_find_match_2_of_3_hs_code_and_brand():
    """hs_code+brand match (supplier mismatch) → cert returned."""
    row = _make_cert_row(
        attachments=[
            {
                "item_id": "src-item",
                "quote_items": {
                    "id": "src-item",
                    "hs_code": "8504408200",
                    "brand": "Acme",
                    "supplier_id": "different-supplier",
                },
            }
        ]
    )
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert isinstance(match, HistoryCertMatch)
    assert match.cert_id == "cert-uuid-1"
    assert match.type == "ДС ТР ТС"
    assert match.cost_rub == Decimal("12500.00")
    assert match.source_quote_id == "src-quote-uuid"
    assert match.source_item_id == "src-item"


def test_find_match_2_of_3_brand_and_supplier():
    """brand+supplier match (hs_code mismatch) → cert returned."""
    row = _make_cert_row(
        attachments=[
            {
                "item_id": "src-item",
                "quote_items": {
                    "id": "src-item",
                    "hs_code": "9999999999",
                    "brand": "Acme",
                    "supplier_id": "supplier-uuid-1",
                },
            }
        ]
    )
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.cert_id == "cert-uuid-1"


def test_find_match_1_of_3_returns_none():
    """Only 1 criterion matches (loose-match requires ≥2) → None."""
    row = _make_cert_row(
        attachments=[
            {
                "item_id": "src-item",
                "quote_items": {
                    "id": "src-item",
                    "hs_code": "8504408200",
                    "brand": "Different",
                    "supplier_id": "different-supplier",
                },
            }
        ]
    )
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is None


def test_find_match_returns_none_when_no_rows():
    """Empty result → None."""
    sb = _make_select_sb([])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is None


# ---------------------------------------------------------------------------
# Server-side filters (verified through the mock chain)
# ---------------------------------------------------------------------------


def test_find_match_server_filters_relayed_correctly():
    """The PostgREST chain receives all four server-side filters + order DESC."""
    sb = _make_select_sb([])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        find_match(
            organization_id="org-uuid-1",
            current_quote_id="this-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    chain = sb.table.return_value
    chain.select.assert_called_once()

    # .eq("is_custom_expense", False)
    eq_custom = chain.select.return_value.eq
    eq_custom.assert_called_once_with("is_custom_expense", False)

    # .eq("quotes.organization_id", organization_id)
    eq_org = eq_custom.return_value.eq
    eq_org.assert_called_once_with("quotes.organization_id", "org-uuid-1")

    # .neq("quote_id", current_quote_id)
    neq_quote = eq_org.return_value.neq
    neq_quote.assert_called_once_with("quote_id", "this-quote")

    # .gte("created_at", cutoff_iso) — cutoff ≈ 365 days back; we just
    # assert the column name.
    gte_call = neq_quote.return_value.gte
    gte_call.assert_called_once()
    args, _ = gte_call.call_args
    assert args[0] == "created_at"
    cutoff_iso = args[1]
    cutoff = datetime.fromisoformat(cutoff_iso)
    expected = datetime.now(timezone.utc) - timedelta(days=365)
    # within 30 seconds
    assert abs((cutoff - expected).total_seconds()) < 30

    # .order("created_at", desc=True)
    order_call = gte_call.return_value.order
    order_call.assert_called_once_with("created_at", desc=True)


def test_find_match_skips_when_fewer_than_two_non_null_inputs():
    """All criteria null OR only one non-null → no DB round-trip, return None."""
    sb = _make_select_sb([])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        # 1 non-null
        match_one = find_match(
            organization_id="org-uuid-1",
            current_quote_id="this-quote",
            hs_code="8504408200",
            brand=None,
            supplier_id=None,
        )
        # 0 non-null
        match_none = find_match(
            organization_id="org-uuid-1",
            current_quote_id="this-quote",
            hs_code=None,
            brand=None,
            supplier_id=None,
        )

    assert match_one is None
    assert match_none is None
    # No table call at all — fast path.
    sb.table.assert_not_called()


# ---------------------------------------------------------------------------
# is_actual computation (NULL / future / past)
# ---------------------------------------------------------------------------


def test_is_actual_true_when_valid_until_in_future():
    future = (date.today() + timedelta(days=30)).isoformat()
    row = _make_cert_row(valid_until=future)
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.is_actual is True
    assert match.valid_until == date.fromisoformat(future)


def test_is_actual_false_when_valid_until_in_past():
    past = (date.today() - timedelta(days=30)).isoformat()
    row = _make_cert_row(valid_until=past)
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.is_actual is False
    assert match.valid_until == date.fromisoformat(past)


def test_is_actual_true_when_valid_until_is_null():
    """No expiry date → cert is treated as actual."""
    row = _make_cert_row(valid_until=None)
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.is_actual is True
    assert match.valid_until is None


# ---------------------------------------------------------------------------
# Latest-of-multiple ordering
# ---------------------------------------------------------------------------


def test_find_match_returns_first_row_when_multiple_match():
    """The chain is DESC-ordered server-side; we return the first hit."""
    older = _make_cert_row(
        cert_id="older-cert",
        created_at="2026-01-01T10:00:00+00:00",
    )
    newer = _make_cert_row(
        cert_id="newer-cert",
        created_at="2026-04-22T10:00:00+00:00",
    )
    # PostgREST returns DESC; mock the same.
    sb = _make_select_sb([newer, older])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.cert_id == "newer-cert"


def test_find_match_skips_first_row_when_attachments_dont_match():
    """First DESC row has 1-of-3 only; second matches 2-of-3 → returns second."""
    no_match = _make_cert_row(
        cert_id="newer-no-match",
        created_at="2026-04-22T10:00:00+00:00",
        attachments=[
            {
                "item_id": "no-match-item",
                "quote_items": {
                    "id": "no-match-item",
                    "hs_code": "8504408200",
                    "brand": "Different",
                    "supplier_id": "different-supplier",
                },
            }
        ],
    )
    match_row = _make_cert_row(
        cert_id="older-with-match",
        created_at="2026-01-01T10:00:00+00:00",
    )
    sb = _make_select_sb([no_match, match_row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.cert_id == "older-with-match"


# ---------------------------------------------------------------------------
# Error swallowing (best-effort history, never raise)
# ---------------------------------------------------------------------------


def test_find_match_swallows_db_errors(caplog):
    """DB connection errors must NOT raise — return None and log warning."""
    sb = MagicMock()
    sb.table.return_value.select.side_effect = ConnectionError("db down")

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        with caplog.at_level(
            "WARNING", logger="services.quote_certificates_history"
        ):
            match = find_match(
                organization_id="org-uuid-1",
                current_quote_id="other-quote",
                hs_code="8504408200",
                brand="Acme",
                supplier_id="supplier-uuid-1",
            )

    assert match is None
    assert any(
        "find_match failed" in rec.message
        and "org=org-uuid-1" in rec.message
        for rec in caplog.records
    )


# ---------------------------------------------------------------------------
# All-fields decoding
# ---------------------------------------------------------------------------


def test_find_match_parses_all_optional_fields():
    """All cert columns are mapped onto the dataclass; nulls round-trip."""
    row = _make_cert_row(
        type_="СС",
        number=None,
        issuer=None,
        legal_doc=None,
        issued_at=None,
        valid_until=None,
        cost_rub="999999.99",
    )
    sb = _make_select_sb([row])

    with patch(
        "services.quote_certificates_history.get_supabase",
        return_value=sb,
    ):
        match = find_match(
            organization_id="org-uuid-1",
            current_quote_id="other-quote",
            hs_code="8504408200",
            brand="Acme",
            supplier_id="supplier-uuid-1",
        )

    assert match is not None
    assert match.type == "СС"
    assert match.number is None
    assert match.issuer is None
    assert match.legal_doc is None
    assert match.issued_at is None
    assert match.valid_until is None
    assert match.cost_rub == Decimal("999999.99")
    assert match.is_actual is True
