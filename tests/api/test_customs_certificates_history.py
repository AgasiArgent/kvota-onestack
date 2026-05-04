"""Tests for ``GET /api/customs/certificates/history`` — Phase B Req 5.

Covers ``history_certificate_handler`` from ``api/customs.py``. Mocks
``services.quote_certificates_history.find_match`` so the suite never
hits a real DB.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from services.quote_certificates_history import HistoryCertMatch  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    session_user: dict | None = None,
    query_params: dict | None = None,
):
    """Minimal Starlette-style request with optional JWT/session + query."""
    req = MagicMock()
    if api_user_id is not None:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata=user_metadata or {"org_id": "org-1"},
            )
        )
    else:
        req.state = SimpleNamespace(api_user=None)

    if session_user is not None:
        session = {"user": session_user}
        type(req).session = property(lambda self: session)
    else:
        type(req).session = property(
            lambda self: (_ for _ in ()).throw(AssertionError("no session"))
        )

    req.headers = {"content-type": "application/json"}
    req.query_params = query_params or {}
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


def _match_actual() -> HistoryCertMatch:
    return HistoryCertMatch(
        cert_id="cert-prev-1",
        type="ДС ТР ТС",
        number="TC-2025-007",
        issuer="ООО Орган",
        legal_doc="ТР ТС 010/2011",
        issued_at=date(2026, 1, 1),
        valid_until=date(2027, 1, 1),
        cost_rub=Decimal("12500.00"),
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        source_quote_id="quote-prev",
        source_item_id="item-prev",
        is_actual=True,
    )


def _match_expired() -> HistoryCertMatch:
    return HistoryCertMatch(
        cert_id="cert-old-1",
        type="ДС ТР ТС",
        number="TC-2024-099",
        issuer=None,
        legal_doc=None,
        issued_at=date(2024, 1, 1),
        valid_until=date(2025, 1, 1),  # expired (< today which is 2026-05-04)
        cost_rub=Decimal("8000.00"),
        created_at=datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc),
        source_quote_id="quote-old",
        source_item_id="item-old",
        is_actual=False,
    )


# ===========================================================================
# Auth + role gate
# ===========================================================================


def test_history_unauthenticated_returns_401():
    """No JWT and no session → 401 UNAUTHORIZED."""
    from api.customs import history_certificate_handler

    req = _make_request(api_user_id=None)
    resp = _run(history_certificate_handler(req))
    assert resp.status_code == 401
    body = _body(resp)
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


@patch("api.customs.get_user_role_codes")
def test_history_role_gate_allows_read_roles(mock_roles):
    """Read endpoint accepts the wide _CERT_READ_ROLES set, e.g. sales."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["sales"]
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008", "brand": "ABC",
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=None,
    ):
        resp = _run(history_certificate_handler(req))
    # 200 + null match — sales role is allowed for reads
    assert resp.status_code == 200
    assert _body(resp)["data"]["match"] is None


@patch("api.customs.get_user_role_codes")
def test_history_role_gate_rejects_unrelated_role(mock_roles):
    """Roles outside _CERT_READ_ROLES → 403."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["procurement"]  # not in _CERT_READ_ROLES
    req = _make_request(query_params={"current_quote_id": "q"})
    resp = _run(history_certificate_handler(req))
    assert resp.status_code == 403
    assert _body(resp)["error"]["code"] == "FORBIDDEN"


# ===========================================================================
# Validation
# ===========================================================================


@patch("api.customs.get_user_role_codes")
def test_history_missing_current_quote_id_returns_400(mock_roles):
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    req = _make_request(query_params={"hs_code": "8409910008"})
    resp = _run(history_certificate_handler(req))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "current_quote_id" in body["error"]["message"].lower()


# ===========================================================================
# Response shape — null match
# ===========================================================================


@patch("api.customs.get_user_role_codes")
def test_history_returns_null_match_when_none(mock_roles):
    """find_match → None → response.data.match is null (UI hides banner)."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008",
        "brand": "ABC",
        "supplier_id": "sup-1",
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=None,
    ) as mock_find:
        resp = _run(history_certificate_handler(req))

    assert resp.status_code == 200
    assert _body(resp) == {"success": True, "data": {"match": None}}
    mock_find.assert_called_once_with(
        organization_id="org-1",
        current_quote_id="quote-1",
        hs_code="8409910008",
        brand="ABC",
        supplier_id="sup-1",
    )


@patch("api.customs.get_user_role_codes")
def test_history_passes_none_for_blank_optional_params(mock_roles):
    """Blank query strings are coerced to None (only current_quote_id is required)."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008",
        "brand": "ABC",
        "supplier_id": "",  # blank → None
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=None,
    ) as mock_find:
        _run(history_certificate_handler(req))

    args, kwargs = mock_find.call_args
    assert kwargs["supplier_id"] is None


# ===========================================================================
# Response shape — match found
# ===========================================================================


@patch("api.customs.get_user_role_codes")
def test_history_returns_actual_match_with_full_shape(mock_roles):
    """is_actual=True match → all fields populated; cost_rub is float."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    match = _match_actual()
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008",
        "brand": "ABC",
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=match,
    ):
        resp = _run(history_certificate_handler(req))

    assert resp.status_code == 200
    body = _body(resp)
    assert body["success"] is True
    m = body["data"]["match"]
    assert m["cert_id"] == "cert-prev-1"
    assert m["type"] == "ДС ТР ТС"
    assert m["number"] == "TC-2025-007"
    assert m["issuer"] == "ООО Орган"
    assert m["legal_doc"] == "ТР ТС 010/2011"
    assert m["issued_at"] == "2026-01-01"
    assert m["valid_until"] == "2027-01-01"
    assert m["cost_rub"] == 12500.0
    assert m["created_at"].startswith("2026-03-01")
    assert m["source_quote_id"] == "quote-prev"
    assert m["source_item_id"] == "item-prev"
    assert m["is_actual"] is True


@patch("api.customs.get_user_role_codes")
def test_history_returns_expired_match_is_actual_false(mock_roles):
    """is_actual=False (expired cert) — UI must switch to 'Create new' variant."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    match = _match_expired()
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008",
        "brand": "ABC",
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=match,
    ):
        resp = _run(history_certificate_handler(req))

    assert resp.status_code == 200
    m = _body(resp)["data"]["match"]
    assert m["is_actual"] is False
    assert m["cert_id"] == "cert-old-1"


@patch("api.customs.get_user_role_codes")
def test_history_returns_match_with_null_dates(mock_roles):
    """Optional date fields handled — None should serialize to null in JSON."""
    from api.customs import history_certificate_handler

    mock_roles.return_value = ["customs"]
    match = HistoryCertMatch(
        cert_id="cert-x",
        type="СС",
        number=None,
        issuer=None,
        legal_doc=None,
        issued_at=None,
        valid_until=None,  # bessrochniy
        cost_rub=Decimal("0"),
        created_at=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
        source_quote_id="q",
        source_item_id="i",
        is_actual=True,
    )
    req = _make_request(query_params={
        "current_quote_id": "quote-1",
        "hs_code": "8409910008",
        "brand": "ABC",
    })
    with patch(
        "services.quote_certificates_history.find_match", return_value=match,
    ):
        resp = _run(history_certificate_handler(req))

    m = _body(resp)["data"]["match"]
    assert m["issued_at"] is None
    assert m["valid_until"] is None
    assert m["number"] is None
    assert m["is_actual"] is True
