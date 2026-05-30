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


def _qi_compute_row(item_id: str, quote_id: str = "quote-1",
                    qty: int = 10,
                    composition_selected_invoice_id: str | None = "inv-1") -> dict:
    """Row shape returned by ``_compute_attached_items_payload`` Query 1
    (``quote_items.select('id, composition_selected_invoice_id, quantity')``).
    Post-Phase 5d the price columns moved off ``quote_items`` — those are
    fetched via the embedded ``invoice_item_coverage`` join (see
    ``_coverage_row`` below). Helper kept distinct from the upstream
    ``_verify_items_in_quote`` row (which only returns ``{id, quote_id}``).
    """
    return {
        "id": item_id,
        "quote_id": quote_id,
        "composition_selected_invoice_id": composition_selected_invoice_id,
        "quantity": qty,
    }


def _coverage_row(quote_item_id: str, *,
                  invoice_item_id: str = "inv-item-1",
                  ratio: float = 1.0,
                  purchase_price_original: float = 1000.0,
                  purchase_currency: str = "RUB",
                  invoice_quantity: int = 10) -> dict:
    """Row shape returned by ``_compute_attached_items_payload`` Query 2
    (``invoice_item_coverage`` joined with ``invoice_items!inner(...)``).
    Default values yield a single 1.0-ratio coverage row in RUB so tests
    short-circuit the currency conversion path.
    """
    return {
        "quote_item_id": quote_item_id,
        "ratio": ratio,
        "invoice_items": {
            "id": invoice_item_id,
            "purchase_price_original": purchase_price_original,
            "purchase_currency": purchase_currency,
            "quantity": invoice_quantity,
        },
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
        # 5. _compute_attached_items_payload Query 1: quote_items IDs
        stub.stage("quote_items", [
            _qi_compute_row("item-1", qty=10),
            _qi_compute_row("item-2", qty=5),
        ])
        # 6. _compute_attached_items_payload Query 2: invoice_item_coverage
        #    JOIN invoice_items. Each quote_item gets one 1.0-ratio coverage
        #    row in RUB → basis = price × invoice_qty (item-1 = 1000,
        #    item-2 = 1000 → equal split path).
        stub.stage("invoice_item_coverage", [
            _coverage_row("item-1", purchase_price_original=100.0,
                          invoice_quantity=10),
            _coverage_row("item-2", purchase_price_original=200.0,
                          invoice_quantity=5),
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
        # Cert A: _compute_attached_items_payload Query 1 — quote_items IDs
        stub.stage("quote_items", [_qi_compute_row("item-1", qty=10)])
        # Cert A: _compute_attached_items_payload Query 2 — coverage join
        stub.stage("invoice_item_coverage",
                   [_coverage_row("item-1", purchase_price_original=100.0,
                                  invoice_quantity=10)])
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
        # _compute_attached_items_payload Query 1 — quote_items IDs
        stub.stage("quote_items", [
            _qi_compute_row("item-1", qty=10),
            _qi_compute_row("item-2", qty=5),
        ])
        # _compute_attached_items_payload Query 2 — coverage join
        stub.stage("invoice_item_coverage", [
            _coverage_row("item-1", purchase_price_original=100.0,
                          invoice_quantity=10),
            _coverage_row("item-2", purchase_price_original=200.0,
                          invoice_quantity=5),
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
        # _compute_attached_items_payload Query 1 — quote_items IDs
        stub.stage("quote_items", [_qi_compute_row("item-2", qty=5)])
        # _compute_attached_items_payload Query 2 — coverage join
        stub.stage("invoice_item_coverage",
                   [_coverage_row("item-2", purchase_price_original=200.0,
                                  invoice_quantity=5)])

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
# PATCH /certificates/{cert_id} — update_certificate_handler (REQ-9 AC#7)
# ===========================================================================


class TestUpdateCertificateHandler:
    """PATCH /api/customs/certificates/{cert_id} — fields-only edit."""

    @patch("api.customs.get_user_role_codes")
    def test_happy_path_updates_fields(self, mock_roles):
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        # _fetch_cert_in_org → cert select (org-scoped, joined quotes payload)
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        # Capture the update() payload so we can assert which columns are written.
        update_payloads: list[dict] = []
        original_update = stub.update

        def update_capture(payload):
            update_payloads.append(payload)
            return original_update(payload)

        stub.update = update_capture
        # The UPDATE .execute() pops this — the post-update cert row.
        stub.stage(
            "quote_certificates",
            [_cert_row(cost_rub=20000.0, cert_type="СС")],
        )
        # No attachments — _fetch_attached_item_ids_ordered returns [].
        stub.stage("quote_certificate_items", [])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={
                "type": "СС",
                "number": "NEW-2026-999",
                "issuer": "Новый орган",
                "legal_doc": "ТР ТС 004/2011",
                "issued_at": "2026-02-01",
                "valid_until": "2028-02-01",
                "cost_original": 20000.0,
                "cost_currency": "RUB",
                "notes": "обновлено",
            })
            resp = _run(update_certificate_handler(req, "cert-1"))

        assert resp.status_code == 200
        body = _body(resp)
        assert body["success"] is True
        cert = body["data"]
        # Response is the projected envelope (same shape as create/list).
        assert cert["id"] == "cert-1"
        assert cert["type"] == "СС"
        assert "attached_items" in cert
        # Only editable columns were written — never quote_id / item_ids.
        assert len(update_payloads) == 1
        written = update_payloads[0]
        assert written["type"] == "СС"
        assert written["number"] == "NEW-2026-999"
        assert written["issuer"] == "Новый орган"
        assert written["legal_doc"] == "ТР ТС 004/2011"
        assert written["issued_at"] == "2026-02-01"
        assert written["valid_until"] == "2028-02-01"
        assert written["cost_original"] == 20000.0
        assert written["cost_currency"] == "RUB"
        assert written["notes"] == "обновлено"
        assert "quote_id" not in written
        assert "item_ids" not in written

    @patch("api.customs.get_user_role_codes")
    def test_partial_update_only_writes_provided_keys(self, mock_roles):
        """Only keys present in the body are written (cost untouched here)."""
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["admin"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        update_payloads: list[dict] = []
        original_update = stub.update

        def update_capture(payload):
            update_payloads.append(payload)
            return original_update(payload)

        stub.update = update_capture
        stub.stage("quote_certificates", [_cert_row()])
        stub.stage("quote_certificate_items", [])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"number": "ONLY-NUMBER"})
            resp = _run(update_certificate_handler(req, "cert-1"))

        assert resp.status_code == 200
        written = update_payloads[0]
        assert written == {"number": "ONLY-NUMBER"}
        assert "cost_original" not in written
        assert "type" not in written

    @patch("api.customs.get_user_role_codes")
    def test_empty_string_clears_optional_field(self, mock_roles):
        """An explicit empty string for an optional field NULLs the column."""
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        update_payloads: list[dict] = []
        original_update = stub.update

        def update_capture(payload):
            update_payloads.append(payload)
            return original_update(payload)

        stub.update = update_capture
        stub.stage("quote_certificates", [_cert_row()])
        stub.stage("quote_certificate_items", [])

        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"notes": ""})
            resp = _run(update_certificate_handler(req, "cert-1"))

        assert resp.status_code == 200
        assert update_payloads[0] == {"notes": None}

    @patch("api.customs.get_user_role_codes")
    def test_unauthenticated_returns_401(self, mock_roles):
        from api.customs import update_certificate_handler

        req = _make_request(api_user_id=None)
        resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 401
        assert _body(resp)["error"]["code"] == "UNAUTHORIZED"

    @patch("api.customs.get_user_role_codes")
    def test_read_only_role_returns_403(self, mock_roles):
        """Writes are gated by _CUSTOMS_ROLES — a read-only role is forbidden."""
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["sales"]
        req = _make_request(body={"type": "СС"})
        resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 403
        assert _body(resp)["error"]["code"] == "FORBIDDEN"

    @patch("api.customs.get_user_role_codes")
    def test_cert_not_found_returns_404(self, mock_roles):
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage("quote_certificates", [])  # cert missing / wrong org
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"type": "СС"})
            resp = _run(update_certificate_handler(req, "missing-cert"))
        assert resp.status_code == 404
        assert _body(resp)["error"]["code"] == "NOT_FOUND"

    @patch("api.customs.get_user_role_codes")
    def test_invalid_json_returns_400(self, mock_roles):
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        req = _make_request(raw_body_error=True)
        resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_empty_type_returns_400(self, mock_roles):
        """type may be omitted, but if provided it must be non-empty."""
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"type": "   "})
            resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_negative_cost_returns_400(self, mock_roles):
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"cost_original": -1})
            resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"

    @patch("api.customs.get_user_role_codes")
    def test_no_editable_fields_returns_400(self, mock_roles):
        """A body with no recognised editable key is rejected."""
        from api.customs import update_certificate_handler

        mock_roles.return_value = ["customs"]
        stub = _Stub()
        stub.stage(
            "quote_certificates",
            [{**_cert_row(), "quotes": {"organization_id": "org-1"}}],
        )
        with patch("api.customs.get_supabase", return_value=stub):
            req = _make_request(body={"item_ids": ["x"]})  # not editable here
            resp = _run(update_certificate_handler(req, "cert-1"))
        assert resp.status_code == 400
        assert _body(resp)["error"]["code"] == "VALIDATION_ERROR"


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


# ===========================================================================
# _compute_attached_items_payload — direct helper tests for the
# invoice_item_coverage JOIN rewrite (Phase 2b of customs Phase B hotfix).
# ===========================================================================


class TestComputeAttachedItemsPayload:
    """Direct tests for the helper that derives per-item RUB shares.

    Post-Phase 5d migration: pricing columns moved off ``quote_items`` to
    ``invoice_items``. The helper now joins through ``invoice_item_coverage``
    instead of selecting prices directly. These tests exercise the helper's
    DB shape contract independently of HTTP handlers.
    """

    def test_single_item_share_matches_manual_computation(self):
        """1 attached item, 1 coverage row, ratio=1.0 → cert_cost lands on
        that item entirely (single-item path in ``split_cost_batch``)."""
        from decimal import Decimal

        from api.customs import _compute_attached_items_payload

        stub = _Stub()
        # Query 1
        stub.stage("quote_items", [_qi_compute_row("item-1", qty=10)])
        # Query 2 — basis = 250.0 × 4 × 1.0 = 1000 RUB
        stub.stage("invoice_item_coverage", [
            _coverage_row("item-1",
                          purchase_price_original=250.0,
                          purchase_currency="RUB",
                          invoice_quantity=4,
                          ratio=1.0),
        ])

        cert_row = {"cost_rub": 12500.0, "quote_id": "quote-1"}
        payload = _compute_attached_items_payload(
            stub, cert_row, ["item-1"]
        )

        # Single attached item → cert_cost lands on that item entirely
        # (``split_cost_batch`` n=1 short-circuit, no rounding).
        assert len(payload) == 1
        assert payload[0]["item_id"] == "item-1"
        assert Decimal(str(payload[0]["share_rub"])) == Decimal("12500")
        assert payload[0]["share_percent"] == 100.0

    def test_multi_items_shares_sum_to_cert_cost(self):
        """3 attached items, different bases → kopek-exact sum to cert_cost."""
        from decimal import Decimal

        from api.customs import _compute_attached_items_payload

        stub = _Stub()
        stub.stage("quote_items", [
            _qi_compute_row("item-1"),
            _qi_compute_row("item-2"),
            _qi_compute_row("item-3"),
        ])
        # Basis: item-1 = 1000, item-2 = 2000, item-3 = 3000 (RUB).
        # cert_cost = 12345.67 → proportional split, residual on last.
        stub.stage("invoice_item_coverage", [
            _coverage_row("item-1",
                          purchase_price_original=100.0,
                          invoice_quantity=10),
            _coverage_row("item-2",
                          purchase_price_original=200.0,
                          invoice_quantity=10),
            _coverage_row("item-3",
                          purchase_price_original=300.0,
                          invoice_quantity=10),
        ])

        cert_cost = Decimal("12345.67")
        cert_row = {"cost_rub": float(cert_cost), "quote_id": "quote-1"}
        payload = _compute_attached_items_payload(
            stub, cert_row, ["item-1", "item-2", "item-3"]
        )

        # Sum-to-cert_cost invariant (REQ-3 AC#7 — last absorbs residual).
        total = sum((Decimal(str(it["share_rub"])) for it in payload),
                    Decimal("0"))
        assert total == cert_cost
        assert len(payload) == 3
        # Order preserved
        assert [it["item_id"] for it in payload] == [
            "item-1", "item-2", "item-3",
        ]

    def test_mixed_currencies_convert_amount_called_per_non_rub_item(self):
        """Items in EUR + USD trigger ``convert_amount`` once per non-RUB
        item (one round per currency × item, not per coverage row)."""
        from decimal import Decimal

        from api.customs import _compute_attached_items_payload

        stub = _Stub()
        stub.stage("quote_items", [
            _qi_compute_row("item-eur"),
            _qi_compute_row("item-usd"),
            _qi_compute_row("item-rub"),
        ])
        stub.stage("invoice_item_coverage", [
            _coverage_row("item-eur",
                          purchase_currency="EUR",
                          purchase_price_original=10.0,
                          invoice_quantity=2),  # 20 EUR
            _coverage_row("item-usd",
                          purchase_currency="USD",
                          purchase_price_original=15.0,
                          invoice_quantity=4),  # 60 USD
            _coverage_row("item-rub",
                          purchase_currency="RUB",
                          purchase_price_original=500.0,
                          invoice_quantity=2),  # 1000 RUB — short-circuit
        ])

        # Mock convert_amount to (a) prove RUB short-circuits (no call) and
        # (b) deterministically return EUR→100 RUB / USD per unit currency.
        from unittest.mock import MagicMock as _MM
        mock_convert = _MM(
            side_effect=lambda amt, src, dst: (
                amt * Decimal("100") if src == "EUR" else
                amt * Decimal("80") if src == "USD" else
                amt
            )
        )
        with patch(
            "services.currency_service.convert_amount", mock_convert
        ):
            cert_row = {"cost_rub": 10000.0, "quote_id": "quote-1"}
            payload = _compute_attached_items_payload(
                stub, cert_row, ["item-eur", "item-usd", "item-rub"]
            )

        # convert_amount called exactly twice (EUR + USD; RUB short-circuits).
        assert mock_convert.call_count == 2
        called_currencies = {call.args[1] for call in mock_convert.call_args_list}
        assert called_currencies == {"EUR", "USD"}
        # cert_cost preserved exactly across the 3-way split.
        total = sum(
            (Decimal(str(it["share_rub"])) for it in payload), Decimal("0")
        )
        assert total == Decimal("10000")
        assert len(payload) == 3

    def test_empty_attached_item_ids_returns_empty_no_db_calls(self):
        """Early-return preserved: zero items → no DB execute() invoked."""
        from api.customs import _compute_attached_items_payload

        stub = MagicMock()
        cert_row = {"cost_rub": 5000.0, "quote_id": "quote-1"}
        payload = _compute_attached_items_payload(stub, cert_row, [])

        assert payload == []
        # No table()/select()/execute() chain ever touched the stub.
        stub.table.assert_not_called()
