"""Tests for ``GET /api/customs/items/history`` — Phase A Req 10.

Covers ``history_lookup_handler`` from ``api/customs.py`` plus the route
registration in ``api/routers/customs.py``. Mocks
``services.customs_user_choices.find_recent`` so the suite never hits a
real DB.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from services.alta_client import Rate  # noqa: E402
from services.customs_user_choices import HistoryMatch  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    session_user: dict | None = None,
):
    """Build a minimal Starlette-style request with optional JWT/session.

    History endpoint is GET — no JSON body. Auth lives on ``request.state``
    or ``request.session`` exactly like the other customs handlers.
    """
    req = MagicMock()
    if api_user_id is not None:
        req.state = SimpleNamespace(
            api_user=SimpleNamespace(
                id=api_user_id,
                email="u@x.com",
                user_metadata=user_metadata or {"org_id": "o-1"},
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
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


def _rate(
    *,
    payment_type: str = "IMP",
    category_code: str | None = "imp_default",
    value_1_number: float | None = 10.0,
    description: str | None = None,
    tnved_code: str = "8504408200",
) -> Rate:
    """Build a minimal Rate fixture matching the find_recent return shape."""
    return Rate(
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_or_areal="C:156",
        valid_from=date(2025, 1, 1),
        value_1_number=value_1_number,
        value_1_unit="percent",
        category_code=category_code,
        description=description,
    )


def _history_match(
    *,
    user_id: str = "user-recent",
    user_email: str | None = "customs@example.com",
    chosen_variants: dict[str, Rate] | None = None,
    manual_override: bool = False,
    manual_rate_payload: dict | None = None,
    created_at: datetime | None = None,
    is_actual: bool = True,
) -> HistoryMatch:
    return HistoryMatch(
        user_id=user_id,
        user_email=user_email,
        chosen_variants=chosen_variants if chosen_variants is not None else {
            "IMP": _rate(payment_type="IMP", category_code="imp_default", value_1_number=10.0),
        },
        manual_override=manual_override,
        manual_rate_payload=manual_rate_payload,
        created_at=created_at or datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc),
        is_actual=is_actual,
    )


# ===========================================================================
# Auth + role gate
# ===========================================================================


def test_history_lookup_unauthenticated_401():
    """No JWT and no session → 401 UNAUTHORIZED."""
    from api.customs import history_lookup_handler

    req = _make_request(api_user_id=None)
    resp = _run(history_lookup_handler(req, "8504408200", 156))
    assert resp.status_code == 401
    body = _body(resp)
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


@patch("api.customs.get_user_role_codes")
def test_history_lookup_non_customs_role_403(mock_roles):
    """Non-customs role (e.g. sales) → 403 FORBIDDEN."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["sales"]
    req = _make_request()
    resp = _run(history_lookup_handler(req, "8504408200", 156))
    assert resp.status_code == 403
    body = _body(resp)
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


# ===========================================================================
# Query-param validation
# ===========================================================================


@patch("api.customs.get_user_role_codes")
def test_history_lookup_validates_tnved_code(mock_roles):
    """Non-10-digit tnved_code → 400 BAD_REQUEST."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    req = _make_request()
    resp = _run(history_lookup_handler(req, "12345", 156))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["success"] is False
    assert body["error"]["code"] == "BAD_REQUEST"
    assert "tnved_code" in body["error"]["message"].lower()


@patch("api.customs.get_user_role_codes")
def test_history_lookup_validates_country_oksm(mock_roles):
    """country_oksm <= 0 → 400 BAD_REQUEST."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    req = _make_request()
    resp = _run(history_lookup_handler(req, "8504408200", 0))
    assert resp.status_code == 400
    body = _body(resp)
    assert body["success"] is False
    assert body["error"]["code"] == "BAD_REQUEST"
    assert "country_oksm" in body["error"]["message"].lower()


# ===========================================================================
# Response shape
# ===========================================================================


@patch("api.customs.get_user_role_codes")
def test_history_lookup_returns_null_when_no_history(mock_roles):
    """find_recent → None → response.data is null (UI hides banner)."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    req = _make_request()
    with patch(
        "services.customs_user_choices.find_recent", return_value=None
    ) as mock_find:
        resp = _run(history_lookup_handler(req, "8504408200", 156))

    assert resp.status_code == 200
    body = _body(resp)
    assert body == {"success": True, "data": None}
    # find_recent called with the (org, code, country) triple
    mock_find.assert_called_once_with(
        organization_id="o-1",
        tnved_code="8504408200",
        country_oksm=156,
    )


@patch("api.customs.get_user_role_codes")
def test_history_lookup_returns_match_with_correct_shape(mock_roles):
    """Match found → response.data carries every field per design.md."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    chosen = {
        "IMP": _rate(payment_type="IMP", category_code="imp_default", value_1_number=10.0),
        "NDS": _rate(payment_type="NDS", category_code="nds_med", value_1_number=22.0),
    }
    match = _history_match(
        user_id="user-recent",
        user_email="customs@example.com",
        chosen_variants=chosen,
        manual_override=False,
        manual_rate_payload=None,
        created_at=datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc),
        is_actual=True,
    )

    req = _make_request()
    with patch(
        "services.customs_user_choices.find_recent", return_value=match
    ):
        resp = _run(history_lookup_handler(req, "8504408200", 156))

    assert resp.status_code == 200
    body = _body(resp)
    assert body["success"] is True
    data = body["data"]
    # All required fields present per spec
    assert data["user_id"] == "user-recent"
    assert data["user_email"] == "customs@example.com"
    assert data["created_at"] == "2026-04-22T10:30:00+00:00"
    assert data["manual_override"] is False
    assert data["manual_rate_payload"] is None
    assert data["is_actual"] is True
    # chosen_variants is a dict keyed by payment_type, each value a serialized Rate
    assert set(data["chosen_variants"].keys()) == {"IMP", "NDS"}
    imp = data["chosen_variants"]["IMP"]
    assert imp["payment_type"] == "IMP"
    assert imp["category_code"] == "imp_default"
    assert imp["value_1_number"] == 10.0
    nds = data["chosen_variants"]["NDS"]
    assert nds["category_code"] == "nds_med"
    assert nds["value_1_number"] == 22.0


@patch("api.customs.get_user_role_codes")
def test_history_lookup_is_actual_passed_through(mock_roles):
    """When find_recent returns is_actual=False, response surfaces the flag.

    UI uses this to render the «Alta изменила варианты» warning above the
    history banner — without it the user could re-apply a stale choice.
    """
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    match = _history_match(is_actual=False)

    req = _make_request()
    with patch(
        "services.customs_user_choices.find_recent", return_value=match
    ):
        resp = _run(history_lookup_handler(req, "8504408200", 156))

    assert resp.status_code == 200
    body = _body(resp)
    assert body["success"] is True
    assert body["data"]["is_actual"] is False


@patch("api.customs.get_user_role_codes")
def test_history_lookup_serializes_manual_override_payload(mock_roles):
    """When manual_override=True, manual_rate_payload round-trips into JSON."""
    from api.customs import history_lookup_handler

    mock_roles.return_value = ["customs"]
    payload = {"value_1_number": 7.5, "value_1_unit": "percent"}
    match = _history_match(
        manual_override=True,
        manual_rate_payload=payload,
    )

    req = _make_request()
    with patch(
        "services.customs_user_choices.find_recent", return_value=match
    ):
        resp = _run(history_lookup_handler(req, "8504408200", 156))

    assert resp.status_code == 200
    body = _body(resp)
    assert body["data"]["manual_override"] is True
    assert body["data"]["manual_rate_payload"] == payload
