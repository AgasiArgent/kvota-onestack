"""Auth + role enforcement tests for the certificates API — Phase B Task 5.

Cross-cuts all 6 endpoints. Verifies REQ-2 AC#8/9/10:
  * 401 UNAUTHORIZED when no auth (JWT or session) present.
  * 403 FORBIDDEN when authenticated user has no matching role.
  * Read endpoints accept the wide _CERT_READ_ROLES set.
  * Write endpoints reject all non-_CUSTOMS_ROLES roles (including the
    cert-read-only roles like sales/finance — they can READ but not WRITE).

Mocks ``api.customs.get_supabase`` and ``services.quote_certificates_history.find_match``
so this file never hits a real DB.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_request(
    *,
    api_user_id: str | None = "user-1",
    user_metadata: dict | None = None,
    body: dict | None = None,
    query_params: dict | None = None,
):
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

    type(req).session = property(
        lambda self: (_ for _ in ()).throw(AssertionError("no session"))
    )
    req.headers = {"content-type": "application/json"}
    req.query_params = query_params or {}

    async def _json():
        return body or {}
    req.json = _json
    return req


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _body(response) -> dict:
    return json.loads(response.body)


# Each (handler_factory, args, body, query_params, kind="write"|"read")
def _create(body=None):
    from api.customs import create_certificate_handler

    async def call():
        req = _make_request(body=body or {
            "quote_id": "q", "type": "x", "cost_rub": 0, "item_ids": [],
        })
        return await create_certificate_handler(req)
    return call, "write"


def _list(query_params=None):
    from api.customs import list_certificates_handler

    async def call():
        req = _make_request(
            query_params=query_params or {"quote_id": "quote-1"}
        )
        return await list_certificates_handler(req)
    return call, "read"


def _attach(body=None):
    from api.customs import attach_item_handler

    async def call():
        req = _make_request(body=body or {"item_id": "item-1"})
        return await attach_item_handler(req, "cert-1")
    return call, "write"


def _detach():
    from api.customs import detach_item_handler

    async def call():
        req = _make_request()
        return await detach_item_handler(req, "cert-1", "item-1")
    return call, "write"


def _delete():
    from api.customs import delete_certificate_handler

    async def call():
        req = _make_request()
        return await delete_certificate_handler(req, "cert-1")
    return call, "write"


def _history(query_params=None):
    from api.customs import history_certificate_handler

    async def call():
        req = _make_request(query_params=query_params or {
            "current_quote_id": "q",
            "hs_code": "1", "brand": "B",
        })
        return await history_certificate_handler(req)
    return call, "read"


_ALL_ENDPOINTS = [
    ("POST /certificates", _create),
    ("GET /certificates", _list),
    ("POST /certificates/{cert_id}/items", _attach),
    ("DELETE /certificates/{cert_id}/items/{item_id}", _detach),
    ("DELETE /certificates/{cert_id}", _delete),
    ("GET /certificates/history", _history),
]


# ===========================================================================
# 401 UNAUTHORIZED — no JWT / no session
# ===========================================================================


@pytest.mark.parametrize(
    "label,factory",
    _ALL_ENDPOINTS,
    ids=[label for label, _ in _ALL_ENDPOINTS],
)
def test_unauthenticated_returns_401(label, factory):
    """Every certificates endpoint returns 401 when no auth is present."""

    # Override _make_request to drop api_user — apply via patch
    def make_req(**kw):
        req = MagicMock()
        req.state = SimpleNamespace(api_user=None)
        type(req).session = property(
            lambda self: (_ for _ in ()).throw(AssertionError("no session"))
        )
        req.headers = {"content-type": "application/json"}
        req.query_params = kw.get("query_params") or {}

        async def _json():
            return kw.get("body") or {}
        req.json = _json
        return req

    with patch(
        "tests.api.test_customs_certificates_auth._make_request", make_req,
    ):
        call, _kind = factory()
        resp = _run(call())

    assert resp.status_code == 401, label
    assert _body(resp)["error"]["code"] == "UNAUTHORIZED", label


# ===========================================================================
# 403 FORBIDDEN — write endpoints reject read-only roles
# ===========================================================================


@pytest.mark.parametrize(
    "label,factory",
    [(label, factory) for label, factory in _ALL_ENDPOINTS],
    ids=[label for label, _ in _ALL_ENDPOINTS],
)
def test_role_gate_rejects_unrelated_role(label, factory):
    """An authenticated user with no matching role gets 403."""
    from api.customs import _resolve_dual_auth  # noqa: F401

    with patch("api.customs.get_user_role_codes", return_value=["procurement"]):
        call, _kind = factory()
        resp = _run(call())

    assert resp.status_code == 403, label
    assert _body(resp)["error"]["code"] == "FORBIDDEN", label


def test_write_endpoint_rejects_sales_role():
    """REQ-2 AC#10 — sales role is in _CERT_READ_ROLES but NOT
    _CUSTOMS_ROLES, so writes (POST/DELETE) MUST reject it.

    This is the key invariant separating read and write role lists.
    """
    from api.customs import (
        attach_item_handler,
        create_certificate_handler,
        delete_certificate_handler,
        detach_item_handler,
    )

    with patch("api.customs.get_user_role_codes", return_value=["sales"]):
        # POST /certificates
        req = _make_request(body={
            "quote_id": "q", "type": "x", "cost_rub": 0, "item_ids": [],
        })
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

        # POST /items
        req = _make_request(body={"item_id": "item-1"})
        resp = _run(attach_item_handler(req, "cert-1"))
        assert resp.status_code == 403

        # DELETE /items
        req = _make_request()
        resp = _run(detach_item_handler(req, "cert-1", "item-1"))
        assert resp.status_code == 403

        # DELETE /certificates
        req = _make_request()
        resp = _run(delete_certificate_handler(req, "cert-1"))
        assert resp.status_code == 403


def test_read_endpoint_accepts_wide_role_list():
    """GET /certificates and GET /history accept the wide _CERT_READ_ROLES set."""
    from api.customs import (
        history_certificate_handler,
        list_certificates_handler,
    )

    # Use a quote-not-found response so we don't need to fully stub Supabase.
    class _Stub:
        def table(self, _name):
            return self

        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def is_(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def order(self, *_a, **_kw):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    for role in (
        "sales", "quote_controller", "spec_controller",
        "finance", "top_manager",
    ):
        with patch("api.customs.get_user_role_codes", return_value=[role]):
            # list_certificates_handler returns 404 NOT_FOUND but with role 200 path.
            with patch("api.customs.get_supabase", return_value=_Stub()):
                req = _make_request(query_params={"quote_id": "quote-1"})
                resp = _run(list_certificates_handler(req))
            assert resp.status_code != 403, f"role={role} should bypass 403 (got {resp.status_code})"

            with patch(
                "services.quote_certificates_history.find_match",
                return_value=None,
            ):
                req = _make_request(query_params={
                    "current_quote_id": "q",
                    "hs_code": "1", "brand": "B",
                })
                resp = _run(history_certificate_handler(req))
            assert resp.status_code == 200, f"history should 200 for {role}"


# ===========================================================================
# 422 NOT_IN_QUOTE — cross-quote isolation guard
# ===========================================================================


def test_not_in_quote_422_on_create():
    """REQ-2 AC#11 — POST /certificates rejects an item from a different quote."""
    from api.customs import create_certificate_handler

    class _Stub:
        def __init__(self):
            self._stage = 0

        def table(self, _name):
            return self

        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def in_(self, *_a, **_kw):
            return self

        def is_(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def order(self, *_a, **_kw):
            return self

        def execute(self):
            self._stage += 1
            if self._stage == 1:
                # quote scope check
                return SimpleNamespace(data=[{
                    "id": "quote-1", "organization_id": "org-1",
                    "currency_of_quote": "RUB", "currency": "RUB",
                }])
            # items lookup → returns item belonging to OTHER quote
            return SimpleNamespace(data=[{
                "id": "item-foreign", "quote_id": "quote-OTHER",
            }])

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        with patch("api.customs.get_supabase", return_value=_Stub()):
            req = _make_request(body={
                "quote_id": "quote-1", "type": "x", "cost_rub": 0,
                "item_ids": ["item-foreign"],
            })
            resp = _run(create_certificate_handler(req))

    assert resp.status_code == 422
    assert _body(resp)["error"]["code"] == "NOT_IN_QUOTE"


def test_not_in_quote_422_on_attach():
    """REQ-2 AC#11 — POST /items rejects an item from a different quote."""
    from api.customs import attach_item_handler

    class _Stub:
        def __init__(self):
            self._stage = 0

        def table(self, _name):
            return self

        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def in_(self, *_a, **_kw):
            return self

        def is_(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def order(self, *_a, **_kw):
            return self

        def execute(self):
            self._stage += 1
            if self._stage == 1:
                # cert select
                return SimpleNamespace(data=[{
                    "id": "cert-1", "quote_id": "quote-1",
                    "type": "x", "number": None, "issuer": None,
                    "legal_doc": None, "issued_at": None, "valid_until": None,
                    "cost_rub": 0, "notes": None, "display_name": None,
                    "is_custom_expense": False,
                    "created_at": "2026-04-01T00:00:00+00:00",
                    "updated_at": "2026-04-01T00:00:00+00:00",
                    "created_by": "u",
                    "quotes": {"organization_id": "org-1"},
                }])
            # items lookup
            return SimpleNamespace(data=[{
                "id": "item-foreign", "quote_id": "quote-OTHER",
            }])

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        with patch("api.customs.get_supabase", return_value=_Stub()):
            req = _make_request(body={"item_id": "item-foreign"})
            resp = _run(attach_item_handler(req, "cert-1"))

    assert resp.status_code == 422
    assert _body(resp)["error"]["code"] == "NOT_IN_QUOTE"


# ===========================================================================
# 400 VALIDATION_ERROR
# ===========================================================================


def test_create_validation_missing_type():
    """type field is required for POST /certificates."""
    from api.customs import create_certificate_handler

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        req = _make_request(body={
            "quote_id": "q", "cost_rub": 0, "item_ids": [],
        })
        resp = _run(create_certificate_handler(req))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_create_validation_item_ids_not_a_list():
    """item_ids must be a list — string is rejected."""
    from api.customs import create_certificate_handler

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        req = _make_request(body={
            "quote_id": "q", "type": "x", "cost_rub": 0,
            "item_ids": "not-a-list",
        })
        resp = _run(create_certificate_handler(req))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_attach_validation_missing_item_id():
    """item_id is required in POST /items body."""
    from api.customs import attach_item_handler

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        req = _make_request(body={})
        resp = _run(attach_item_handler(req, "cert-1"))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


def test_history_validation_missing_current_quote_id():
    """current_quote_id is required in GET /history."""
    from api.customs import history_certificate_handler

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        req = _make_request(query_params={"hs_code": "1", "brand": "B"})
        resp = _run(history_certificate_handler(req))
    assert resp.status_code == 400
    assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# 404 NOT_FOUND
# ===========================================================================


def test_attach_404_when_cert_missing():
    from api.customs import attach_item_handler

    class _Stub:
        def table(self, _name):
            return self

        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        with patch("api.customs.get_supabase", return_value=_Stub()):
            req = _make_request(body={"item_id": "item-1"})
            resp = _run(attach_item_handler(req, "missing-cert"))
    assert resp.status_code == 404
    assert _body(resp)["error"]["code"] == "NOT_FOUND"


def test_delete_cert_404_when_missing():
    from api.customs import delete_certificate_handler

    class _Stub:
        def table(self, _name):
            return self

        def select(self, *_a, **_kw):
            return self

        def eq(self, *_a, **_kw):
            return self

        def limit(self, *_a, **_kw):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    with patch("api.customs.get_user_role_codes", return_value=["customs"]):
        with patch("api.customs.get_supabase", return_value=_Stub()):
            req = _make_request()
            resp = _run(delete_certificate_handler(req, "missing"))
    assert resp.status_code == 404
    assert _body(resp)["error"]["code"] == "NOT_FOUND"
