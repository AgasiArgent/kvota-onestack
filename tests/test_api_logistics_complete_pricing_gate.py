"""Pricing-gate regression test for /api/logistics/complete (Testing 2 row 80).

Product decision (locked): «Логистика не завершается пока не проценятся все КПП».
The endpoint refuses with HTTP 409 when ANY ``kvota.invoice_items`` row of any
invoice belonging to the same quote has ``purchase_price_original IS NULL`` or
``<= 0``. The error payload carries an ``unpriced_count`` detail field so the UI
can mirror the count in the disabled-button tooltip.

These tests stub Supabase: the table-level helpers in ``api.logistics`` are
small enough to mock end-to-end without a real DB.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

from starlette.requests import Request

from api.logistics import complete


# ---------------------------------------------------------------------------
# Minimal fake supabase: only handles the invoice_items + siblings queries
# the pricing gate performs.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.error = None


class _Query:
    def __init__(self, table: str, payloads: dict[str, list[dict]]) -> None:
        self._table = table
        self._payloads = payloads
        self._filters: list[tuple[str, str, Any]] = []
        self._update_payload: dict | None = None

    def select(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def update(self, payload: dict) -> "_Query":
        self._update_payload = payload
        return self

    def eq(self, col: str, val: Any) -> "_Query":
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col: str, vals: list) -> "_Query":
        self._filters.append(("in", col, list(vals)))
        return self

    def is_(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def limit(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def order(self, *_a: Any, **_k: Any) -> "_Query":
        return self

    def execute(self) -> _Resp:
        return _Resp(self._payloads.get(self._table, []))


class _FakeSupabase:
    def __init__(self, payloads: dict[str, list[dict]]) -> None:
        self._payloads = payloads
        self.updates: list[tuple[str, dict]] = []

    def table(self, name: str) -> _Query:
        q = _Query(name, self._payloads)
        original_execute = q.execute

        def _tracking_execute() -> _Resp:
            if q._update_payload is not None:
                self.updates.append((name, q._update_payload))
                # Return the updated row(s) so the handler can read row[0]
                base = self._payloads.get(name, [])
                if base:
                    merged = {**base[0], **q._update_payload}
                    return _Resp([merged])
                return _Resp([{**q._update_payload, "id": "row-1"}])
            return original_execute()

        q.execute = _tracking_execute  # type: ignore[method-assign]
        return q


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_request(body: dict) -> Request:
    """Build a minimal ASGI Request stub carrying JSON body."""
    raw = json.dumps(body).encode("utf-8")
    sent = {"done": False}

    async def receive() -> dict:
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": raw, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/logistics/complete",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"",
    }
    return Request(scope, receive=receive)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_complete_returns_409_when_any_invoice_item_unpriced(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """ANY invoice_item with purchase_price_original NULL/0 → 409 CONFLICT.

    The error payload must include ``unpriced_count`` so the UI can mirror
    the count in the disabled-button tooltip ("Осталось проценить N КПП").
    """
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {
        "id": "inv-1",
        "quote_id": "quote-1",
        "logistics_completed_at": None,
        "logistics_needs_review_since": None,
    }
    mock_get_sb.return_value = _FakeSupabase(
        {
            # All invoices belonging to this quote.
            "invoices": [{"id": "inv-1"}, {"id": "inv-2"}],
            # 3 invoice_items total — 2 unpriced (1 NULL, 1 zero).
            "invoice_items": [
                {"id": "ii-1", "invoice_id": "inv-1",
                 "purchase_price_original": 100.0},
                {"id": "ii-2", "invoice_id": "inv-1",
                 "purchase_price_original": None},
                {"id": "ii-3", "invoice_id": "inv-2",
                 "purchase_price_original": 0},
            ],
        }
    )

    request = _make_request({"invoice_id": "inv-1"})
    response = asyncio.run(complete(request))

    assert response.status_code == 409
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["success"] is False
    assert payload["error"]["code"] == "UNPRICED_INVOICE_ITEMS"
    assert payload["error"]["detail"]["unpriced_count"] == 2


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_complete_proceeds_when_all_invoice_items_priced(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """Every invoice_item has purchase_price_original > 0 → 200 OK, write happens."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {
        "id": "inv-1",
        "quote_id": "quote-1",
        "logistics_completed_at": None,
        "logistics_needs_review_since": None,
    }
    fake = _FakeSupabase(
        {
            "invoices": [{"id": "inv-1", "logistics_completed_at": None}],
            "invoice_items": [
                {"id": "ii-1", "invoice_id": "inv-1",
                 "purchase_price_original": 100.0},
            ],
        }
    )
    mock_get_sb.return_value = fake

    request = _make_request({"invoice_id": "inv-1"})
    response = asyncio.run(complete(request))

    # 200 = pricing gate passed. The write may or may not succeed depending
    # on the fake's behaviour — what we pin here is that the gate did NOT
    # short-circuit with 409.
    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["success"] is True


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_complete_with_no_invoice_items_passes_gate(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """No invoice_items → gate is vacuously satisfied.

    Reaching logistics with zero materialised supplier lines is an
    upstream bug (procurement is supposed to gate that), but THIS gate is
    specifically about pricing. We keep the universal-quantifier reading:
    "all rows priced" is True for the empty set. Anything else (treating
    "empty" as failure) would conflate two independent policies and
    surface a confusing tooltip.
    """
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {
        "id": "inv-1",
        "quote_id": "quote-1",
        "logistics_completed_at": None,
        "logistics_needs_review_since": None,
    }
    mock_get_sb.return_value = _FakeSupabase(
        {
            "invoices": [{"id": "inv-1", "logistics_completed_at": None}],
            "invoice_items": [],
        }
    )

    request = _make_request({"invoice_id": "inv-1"})
    response = asyncio.run(complete(request))

    # Gate passes — completion proceeds.
    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["success"] is True
