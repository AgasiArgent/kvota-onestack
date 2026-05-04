"""Tests for certificate CRUD endpoints — Phase B (customs-shared-certificates) Task 5.

Covers ``create_certificate_handler``, ``list_certificates_handler``,
``attach_item_handler``, ``detach_item_handler``, ``delete_certificate_handler``
from ``api/customs.py`` plus the route registrations in
``api/routers/customs.py``. Mocks ``services.database.get_supabase`` so the
suite never hits a real DB.

Atomicity tests: cross-quote isolation triggers 422 NOT_IN_QUOTE rollback;
attachment INSERT failure triggers DELETE-cert rollback.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
    session_user: dict | None = None,
    body: dict | None = None,
    raw_body_error: bool = False,
    query_params: dict | None = None,
):
    """Build a minimal Starlette-style request with optional JWT/session/body."""
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

    async def _json():
        if raw_body_error:
            raise ValueError("bad json")
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


# ---------------------------------------------------------------------------
# Supabase mock builder — accumulates a fluent chain of .table().select()...
# ---------------------------------------------------------------------------


class _Stub:
    """Tiny dispatch helper: stage a sequence of (table_name, response.data) pairs.

    The first ``table('foo')`` call pops the next stage; chained ``.select()``,
    ``.eq()``, ``.in_()``, ``.is_()``, ``.limit()``, ``.order()`` calls all
    return ``self``; ``.execute()`` returns a SimpleNamespace with the staged
    ``.data`` payload. ``.insert()`` and ``.delete()`` accept any args and
    track the last payload via ``insert_payload``/``delete_called``.
    """

    def __init__(self):
        self._queue: list[tuple[str, list]] = []
        self.insert_calls: list[tuple[str, list | dict]] = []
        self.delete_calls: list[tuple[str, list]] = []
        self._current_table: str | None = None
        self._mode: str | None = None

    def stage(self, table_name: str, data):
        self._queue.append((table_name, data))

    def table(self, name: str):
        self._current_table = name
        self._mode = None
        return self

    def select(self, *_a, **_kw):
        return self

    def insert(self, payload):
        self._mode = "insert"
        self.insert_calls.append((self._current_table, payload))
        return self

    def update(self, payload):
        self._mode = "update"
        return self

    def delete(self):
        self._mode = "delete"
        return self

    def eq(self, *_a, **_kw):
        return self

    def neq(self, *_a, **_kw):
        return self

    def gte(self, *_a, **_kw):
        return self

    def is_(self, *_a, **_kw):
        return self

    def in_(self, *_a, **_kw):
        return self

    def limit(self, *_a, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def single(self):
        return self

    def execute(self):
        if self._mode == "delete":
            popped = self._queue.pop(0) if self._queue else (None, [])
            self.delete_calls.append((self._current_table, popped[1]))
            return SimpleNamespace(data=popped[1])
        if self._queue:
            _expected, data = self._queue.pop(0)
            return SimpleNamespace(data=data)
        return SimpleNamespace(data=[])


def _quote_row(quote_id: str = "quote-1", currency: str = "RUB") -> dict:
    return {
        "id": quote_id,
        "organization_id": "org-1",
        "currency_of_quote": currency,
        "currency": currency,
    }


def _cert_row(
    cert_id: str = "cert-1",
    quote_id: str = "quote-1",
    cost_rub: float = 12500.0,
    is_custom_expense: bool = False,
    cert_type: str = "ДС ТР ТС",
) -> dict:
    return {
        "id": cert_id,
        "quote_id": quote_id,
        "type": cert_type,
        "number": "TC-2026-001",
        "issuer": "ООО Орган",
        "legal_doc": "ТР ТС 010/2011",
        "issued_at": "2026-01-15",
        "valid_until": "2027-01-14",
        "cost_rub": cost_rub,
        "notes": None,
        "display_name": None,
        "is_custom_expense": is_custom_expense,
        "created_at": "2026-04-01T10:00:00+00:00",
        "updated_at": "2026-04-01T10:00:00+00:00",
        "created_by": "user-1",
    }


def _quote_item(item_id: str, quote_id: str = "quote-1",
                price: float = 1000.0, qty: int = 10) -> dict:
    """RUB-priced quote_item — short-circuits the currency conversion path so
    tests don't need to mock convert_amount/rate fetcher.
    """
    return {
        "id": item_id,
        "quote_id": quote_id,
        "purchase_price_original": price,
        "purchase_currency": "RUB",
        "currency_of_base_price": "RUB",
        "quantity": qty,
        "base_price_vat": price,
        "created_at": "2026-04-01T09:00:00+00:00",
    }


# ===========================================================================
# POST /certificates — create_certificate_handler
# ===========================================================================


class TestCreateCertificateHandler:
    """POST /api/customs/certificates."""

    @patch("api.customs.get_user_role_codes")
    def test_happy_path_creates_cert_with_attachments(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        # 1. _verify_quote_in_org → quotes select
        stub.stage("quotes", [_quote_row()])
        # 2. _verify_items_in_quote → quote_items select
        stub.stage(
            "quote_items",
            [{"id": "item-1", "quote_id": "quote-1"},
             {"id": "item-2", "quote_id": "quote-1"}],
        )
        # 3. cert insert
        stub.stage(
            "quote_certificates",
            [_cert_row(cert_id="cert-new", cost_rub=12500.0)],
        )
        # 4. attachment insert (returns junk; we don't use the rows)
        stub.stage("quote_certificate_items", [
            {"id": "att-1"}, {"id": "att-2"},
        ])
        # 5. _compute_attached_items_payload: quote currency lookup
        stub.stage("quotes", [{"currency_of_quote": "RUB", "currency": "RUB"}])
        # 6. _compute_attached_items_payload: quote_items lookup
        stub.stage("quote_items", [
            _quote_item("item-1", price=100.0, qty=10),
            _quote_item("item-2", price=200.0, qty=5),
        ])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(
                body={
                    "quote_id": "quote-1",
                    "type": "ДС ТР ТС",
                    "number": "TC-2026-001",
                    "cost_rub": 12500.0,
                    "item_ids": ["item-1", "item-2"],
                }
            )
            resp = _run(create_certificate_handler(req))

        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        cert = body["data"]
        assert cert["id"] == "cert-new"
        assert cert["cost_rub"] == 12500.0
        # attached_items shape
        items = cert["attached_items"]
        assert len(items) == 2
        assert {it["item_id"] for it in items} == {"item-1", "item-2"}
        for it in items:
            assert "share_rub" in it
            assert "share_percent" in it
        # Insert calls happened on the right tables
        insert_tables = [t for t, _ in stub.insert_calls]
        assert "quote_certificates" in insert_tables
        assert "quote_certificate_items" in insert_tables

    @patch("api.customs.get_user_role_codes")
    def test_unauthenticated_returns_401(self, mock_roles):
        from api.customs import create_certificate_handler

        req = _make_request(api_user_id=None)
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 401
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @patch("api.customs.get_user_role_codes")
    def test_non_customs_role_returns_403(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["sales"]
        req = _make_request(body={"quote_id": "q", "type": "t",
                                  "cost_rub": 0, "item_ids": []})
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.customs.get_user_role_codes")
    def test_missing_quote_id_returns_400(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(body={"type": "x", "cost_rub": 0, "item_ids": []})
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_negative_cost_rub_returns_400(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(body={
            "quote_id": "q", "type": "x", "cost_rub": -5, "item_ids": [],
        })
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_quote_not_found_returns_404(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quotes", [])  # quote not found
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "quote_id": "missing", "type": "x", "cost_rub": 0,
                "item_ids": [],
            })
            resp = _run(create_certificate_handler(req))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.customs.get_user_role_codes")
    def test_cross_quote_item_returns_422_no_inserts(self, mock_roles):
        """REQ-2 AC#11 — cross-quote isolation guard runs BEFORE any INSERT."""
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quotes", [_quote_row()])
        # Item belongs to a different quote → 422 NOT_IN_QUOTE
        stub.stage(
            "quote_items",
            [{"id": "item-foreign", "quote_id": "quote-OTHER"}],
        )
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "quote_id": "quote-1",
                "type": "x", "cost_rub": 0,
                "item_ids": ["item-foreign"],
            })
            resp = _run(create_certificate_handler(req))

        assert resp.status_code == 422
        assert _body(resp)["error"]["code"] == "NOT_IN_QUOTE"
        # No cert insert happened (rollback effective)
        assert not any(
            t == "quote_certificates" for t, _ in stub.insert_calls
        )

    @patch("api.customs.get_user_role_codes")
    def test_missing_item_returns_404(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quotes", [_quote_row()])
        # Asked for item-1 but DB returns nothing
        stub.stage("quote_items", [])
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "quote_id": "quote-1",
                "type": "x", "cost_rub": 0,
                "item_ids": ["item-missing"],
            })
            resp = _run(create_certificate_handler(req))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.customs.get_user_role_codes")
    def test_atomicity_rollback_on_attachment_insert_failure(self, mock_roles):
        """If attachment INSERT raises, the just-created cert is DELETEd."""
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]

        # Build a Supabase stub where the second `insert()` call (on
        # quote_certificate_items) raises.
        stub = _Stub()
        stub.stage("quotes", [_quote_row()])
        stub.stage("quote_items", [
            {"id": "item-1", "quote_id": "quote-1"},
        ])
        stub.stage("quote_certificates", [_cert_row(cert_id="cert-new")])

        original_insert = stub.insert
        attachment_insert_attempted = {"yes": False}

        def insert_with_failure(payload):
            if stub._current_table == "quote_certificate_items":
                attachment_insert_attempted["yes"] = True
                raise RuntimeError("simulated DB error")
            return original_insert(payload)

        stub.insert = insert_with_failure

        # Track DELETE calls — rollback DELETEs the cert by id.
        delete_calls = {"quote_certificates": False}
        original_table = stub.table

        def table_proxy(name):
            chain = original_table(name)
            if name == "quote_certificates":
                _orig_delete = chain.delete

                def delete_recorded():
                    delete_calls["quote_certificates"] = True
                    return _orig_delete()
                chain.delete = delete_recorded
            return chain

        stub.table = table_proxy

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "quote_id": "quote-1",
                "type": "x", "cost_rub": 100,
                "item_ids": ["item-1"],
            })
            resp = _run(create_certificate_handler(req))

        assert resp.status_code == 500
        assert _body(resp)["error"]["code"] == "INTERNAL"
        assert attachment_insert_attempted["yes"] is True
        # The cert MUST be rolled back
        assert delete_calls["quote_certificates"] is True

    @patch("api.customs.get_user_role_codes")
    def test_invalid_json_returns_400(self, mock_roles):
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(raw_body_error=True)
        resp = _run(create_certificate_handler(req))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_empty_item_ids_creates_cert_without_attachments(self, mock_roles):
        """Custom-expense flow — cost-only entry without item bindings is valid."""
        from api.customs import create_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quotes", [_quote_row()])
        stub.stage(
            "quote_certificates",
            [_cert_row(cert_id="cert-x", is_custom_expense=True)],
        )

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "quote_id": "quote-1",
                "type": "custom_expense",
                "display_name": "Доп. расход",
                "cost_rub": 5000.0,
                "is_custom_expense": True,
                "item_ids": [],
            })
            resp = _run(create_certificate_handler(req))

        assert resp.status_code == 200
        body = _body(resp)
        assert body["data"]["attached_items"] == []
        # Only the cert was inserted, no attachments
        assert all(
            t == "quote_certificates" for t, _ in stub.insert_calls
        )


# ===========================================================================
# GET /certificates — list_certificates_handler
# ===========================================================================


class TestListCertificatesHandler:
    """GET /api/customs/certificates?quote_id=..."""

    @patch("api.customs.get_user_role_codes")
    def test_returns_certificates_with_shares(self, mock_roles):
        from api.customs import list_certificates_handler

        mock_roles.return_value = ["sales"]  # read-only role allowed
        stub = _Stub()
        stub.stage("quotes", [_quote_row()])
        # Two certs in the quote
        stub.stage(
            "quote_certificates",
            [
                _cert_row(cert_id="cert-A", cost_rub=10000.0),
                _cert_row(cert_id="cert-B", cost_rub=5000.0,
                          is_custom_expense=True),
            ],
        )
        # Cert A: attached_item_ids fetch
        stub.stage(
            "quote_certificate_items",
            [{"item_id": "item-1", "created_at": "2026-04-01T09:00:00+00:00"}],
        )
        # Cert A: attached items payload — quote currency
        stub.stage("quotes", [{"currency_of_quote": "RUB",
                              "currency": "RUB"}])
        # Cert A: attached items payload — items
        stub.stage("quote_items",
                   [_quote_item("item-1", price=100.0, qty=10)])
        # Cert B: no attachments
        stub.stage("quote_certificate_items", [])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(query_params={"quote_id": "quote-1"})
            resp = _run(list_certificates_handler(req))

        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        certs = body["data"]["certificates"]
        assert len(certs) == 2
        assert certs[0]["id"] == "cert-A"
        assert certs[1]["id"] == "cert-B"
        # Cert A has 1 attachment
        assert len(certs[0]["attached_items"]) == 1
        # Cert B has none
        assert certs[1]["attached_items"] == []

    @patch("api.customs.get_user_role_codes")
    def test_missing_quote_id_returns_400(self, mock_roles):
        from api.customs import list_certificates_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(query_params={})
        resp = _run(list_certificates_handler(req))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_quote_in_other_org_returns_404(self, mock_roles):
        from api.customs import list_certificates_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quotes", [])  # Empty (other org filtered out)
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(query_params={"quote_id": "quote-other-org"})
            resp = _run(list_certificates_handler(req))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"


# ===========================================================================
# POST /certificates/{cert_id}/items — attach_item_handler
# ===========================================================================


class TestAttachItemHandler:
    """POST /api/customs/certificates/{cert_id}/items."""

    @patch("api.customs.get_user_role_codes")
    def test_happy_path_attaches_and_recomputes(self, mock_roles):
        from api.customs import attach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        # _fetch_cert_in_org → cert select
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # _verify_items_in_quote
        stub.stage("quote_items",
                   [{"id": "item-2", "quote_id": "quote-1"}])
        # attachment insert
        stub.stage("quote_certificate_items", [{"id": "att-new"}])
        # _fetch_attached_item_ids_ordered
        stub.stage(
            "quote_certificate_items",
            [
                {"item_id": "item-1",
                 "created_at": "2026-04-01T09:00:00+00:00"},
                {"item_id": "item-2",
                 "created_at": "2026-04-01T10:00:00+00:00"},
            ],
        )
        # _compute_attached_items_payload — quote currency
        stub.stage("quotes",
                   [{"currency_of_quote": "RUB", "currency": "RUB"}])
        # quote_items lookup
        stub.stage("quote_items", [
            _quote_item("item-1", price=100.0, qty=10),
            _quote_item("item-2", price=200.0, qty=5),
        ])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"item_id": "item-2"})
            resp = _run(attach_item_handler(req, "cert-1"))

        assert resp.status_code == 200
        cert = _body(resp)["data"]
        assert cert["id"] == "cert-1"
        assert len(cert["attached_items"]) == 2

    @patch("api.customs.get_user_role_codes")
    def test_cert_not_found_returns_404(self, mock_roles):
        from api.customs import attach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quote_certificates", [])  # cert missing
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"item_id": "item-1"})
            resp = _run(attach_item_handler(req, "missing-cert"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.customs.get_user_role_codes")
    def test_cross_quote_item_returns_422(self, mock_roles):
        from api.customs import attach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # Item belongs to a different quote
        stub.stage("quote_items",
                   [{"id": "item-X", "quote_id": "quote-OTHER"}])
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"item_id": "item-X"})
            resp = _run(attach_item_handler(req, "cert-1"))
        assert resp.status_code == 422
        assert _body(resp)["error"]["code"] == "NOT_IN_QUOTE"

    @patch("api.customs.get_user_role_codes")
    def test_missing_item_id_returns_400(self, mock_roles):
        from api.customs import attach_item_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(body={})
        resp = _run(attach_item_handler(req, "cert-1"))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


# ===========================================================================
# DELETE /certificates/{cert_id}/items/{item_id} — detach_item_handler
# ===========================================================================


class TestDetachItemHandler:
    """DELETE /api/customs/certificates/{cert_id}/items/{item_id}."""

    @patch("api.customs.get_user_role_codes")
    def test_happy_path_detaches_and_recomputes(self, mock_roles):
        from api.customs import detach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # delete returns 1 row
        stub.stage("quote_certificate_items", [{"id": "att-1"}])
        # _fetch_attached_item_ids_ordered → 1 remaining
        stub.stage(
            "quote_certificate_items",
            [{"item_id": "item-2",
              "created_at": "2026-04-01T10:00:00+00:00"}],
        )
        # _compute_attached_items_payload
        stub.stage("quotes",
                   [{"currency_of_quote": "RUB", "currency": "RUB"}])
        stub.stage("quote_items",
                   [_quote_item("item-2", price=200.0, qty=5)])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request()
            resp = _run(detach_item_handler(req, "cert-1", "item-1"))
        assert resp.status_code == 200
        assert len(_body(resp)["data"]["attached_items"]) == 1

    @patch("api.customs.get_user_role_codes")
    def test_attachment_not_found_returns_404(self, mock_roles):
        from api.customs import detach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # Delete returns 0 rows — attachment didn't exist
        stub.stage("quote_certificate_items", [])
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request()
            resp = _run(detach_item_handler(req, "cert-1", "ghost-item"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.customs.get_user_role_codes")
    def test_cert_not_found_returns_404(self, mock_roles):
        from api.customs import detach_item_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quote_certificates", [])
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request()
            resp = _run(detach_item_handler(req, "missing", "x"))
        assert resp.status_code == 404


# ===========================================================================
# DELETE /certificates/{cert_id} — delete_certificate_handler
# ===========================================================================


class TestDeleteCertificateHandler:
    """DELETE /api/customs/certificates/{cert_id}."""

    @patch("api.customs.get_user_role_codes")
    def test_happy_path_deletes_cert(self, mock_roles):
        from api.customs import delete_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # delete returns the deleted row
        stub.stage("quote_certificates", [{"id": "cert-1"}])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request()
            resp = _run(delete_certificate_handler(req, "cert-1"))
        assert resp.status_code == 200
        body = _body(resp)
        assert body["data"]["deleted_id"] == "cert-1"

    @patch("api.customs.get_user_role_codes")
    def test_cert_not_found_returns_404(self, mock_roles):
        from api.customs import delete_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quote_certificates", [])
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request()
            resp = _run(delete_certificate_handler(req, "missing"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"
