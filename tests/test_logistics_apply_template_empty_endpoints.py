"""Regression test for apply_template empty-endpoint handling (Testing 2 row 30 #3).

A route template may intentionally leave the FIRST segment's origin (Откуда)
and/or the LAST segment's destination (Куда) empty so the logistician fills
them from МОЗ data after applying the template. Before the fix, apply_template
fell back to "the first org-scoped location of that type" for every missing
location id, silently autofilling those endpoint slots (e.g. "Китай Шэньчжэнь"
and "Россия СПб").

The fix: open endpoints (first.from / last.to) keep a NULL location id;
interior slots still fall back so the route stays connected.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

from starlette.requests import Request

from api.logistics import apply_template


# ---------------------------------------------------------------------------
# Fake Supabase that covers every table apply_template touches and records
# the rows inserted into logistics_route_segments.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.error = None


class _Query:
    def __init__(self, table: str, db: "_FakeSupabase") -> None:
        self._table = table
        self._db = db
        self._filters: list[tuple[str, str, Any]] = []
        self._op: str | None = None
        self._insert_rows: list[dict] | None = None

    # -- builders ----------------------------------------------------------
    def select(self, *_a: Any, **_k: Any) -> "_Query":
        self._op = "select"
        return self

    def insert(self, rows: Any) -> "_Query":
        self._op = "insert"
        self._insert_rows = rows if isinstance(rows, list) else [rows]
        return self

    def delete(self) -> "_Query":
        self._op = "delete"
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

    # -- execution ---------------------------------------------------------
    def execute(self) -> _Resp:
        if self._op == "insert" and self._table == "logistics_route_segments":
            self._db.inserted_segments.extend(self._insert_rows or [])
            return _Resp(list(self._insert_rows or []))
        if self._op == "delete":
            return _Resp([])
        if self._table == "locations":
            # Override-check path uses .in_(); type-fallback path uses .eq().
            in_filter = next((f for f in self._filters if f[0] == "in"), None)
            if in_filter:
                requested = set(in_filter[2])
                return _Resp(
                    [{"id": x} for x in requested & self._db.locations_in_org]
                )
            type_filter = next(
                (f for f in self._filters if f[0] == "eq" and f[1] == "location_type"),
                None,
            )
            if type_filter:
                loc_type = type_filter[2]
                fallback = self._db.fallback_by_type.get(loc_type)
                return _Resp([{"id": fallback}] if fallback else [])
            return _Resp([])
        if self._table == "logistics_route_templates":
            return _Resp(self._db.template_rows)
        if self._table == "logistics_route_segments":
            # The "existing segments" max-sequence_order lookup.
            return _Resp([])
        raise AssertionError(f"Unexpected table {self._table!r}")


class _FakeSupabase:
    def __init__(
        self,
        *,
        template_rows: list[dict],
        fallback_by_type: dict[str, str],
        locations_in_org: set[str] | None = None,
    ) -> None:
        self.template_rows = template_rows
        self.fallback_by_type = fallback_by_type
        self.locations_in_org = locations_in_org or set()
        self.inserted_segments: list[dict] = []

    def table(self, name: str) -> _Query:
        return _Query(name, self)


def _make_request(body: dict) -> Request:
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
        "path": "/api/logistics/templates/tpl-1/apply",
        "headers": [(b"content-type", b"application/json")],
        "query_string": b"invoice_id=inv-1",
    }
    return Request(scope, receive=receive)


def _template(segments: list[dict]) -> list[dict]:
    return [
        {
            "id": "tpl-1",
            "organization_id": "org-A",
            "logistics_route_template_segments": segments,
        }
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_empty_first_and_last_locations_stay_null(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """A template whose first.from and last.to have no concrete location id
    must materialise segments with NULL endpoints — no autofill."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}

    # 3-segment route: supplier -> hub -> customs -> client.
    # First segment's origin and last segment's destination are left empty.
    segments = [
        {
            "sequence_order": 1,
            "from_location_type": "supplier",
            "to_location_type": "hub",
            "default_label": "First mile",
            "default_days": 2,
            "from_location_id": None,  # open endpoint — must stay NULL
            "to_location_id": None,
        },
        {
            "sequence_order": 2,
            "from_location_type": "hub",
            "to_location_type": "customs",
            "default_label": "Main freight",
            "default_days": 10,
            "from_location_id": None,
            "to_location_id": None,
        },
        {
            "sequence_order": 3,
            "from_location_type": "customs",
            "to_location_type": "client",
            "default_label": "Last mile",
            "default_days": 3,
            "from_location_id": None,
            "to_location_id": None,  # open endpoint — must stay NULL
        },
    ]
    fake = _FakeSupabase(
        template_rows=_template(segments),
        fallback_by_type={
            "hub": "loc-hub-A",
            "customs": "loc-customs-A",
            # 'supplier' / 'client' default rows exist but must NOT be used
            # for the open endpoints.
            "supplier": "loc-supplier-default",
            "client": "loc-client-default",
        },
    )
    mock_get_sb.return_value = fake

    response = asyncio.run(apply_template(_make_request({}), template_id="tpl-1"))
    assert response.status_code == 201, response.body

    rows = sorted(fake.inserted_segments, key=lambda r: r["sequence_order"])
    assert len(rows) == 3

    # First segment: origin stays NULL, destination falls back to hub.
    assert rows[0]["from_location_id"] is None
    assert rows[0]["to_location_id"] == "loc-hub-A"

    # Interior segment: both sides fall back so the route stays connected.
    assert rows[1]["from_location_id"] == "loc-hub-A"
    assert rows[1]["to_location_id"] == "loc-customs-A"

    # Last segment: origin falls back to customs, destination stays NULL.
    assert rows[2]["from_location_id"] == "loc-customs-A"
    assert rows[2]["to_location_id"] is None


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_concrete_endpoint_ids_are_honored(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """When a template DOES pin a concrete endpoint location, that id is used
    (the empty-endpoint rule only applies to missing ids)."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}

    segments = [
        {
            "sequence_order": 1,
            "from_location_type": "supplier",
            "to_location_type": "client",
            "default_label": "Direct",
            "default_days": 5,
            "from_location_id": "loc-pinned-origin",
            "to_location_id": "loc-pinned-dest",
        },
    ]
    fake = _FakeSupabase(
        template_rows=_template(segments),
        fallback_by_type={"supplier": "x", "client": "y"},
    )
    mock_get_sb.return_value = fake

    response = asyncio.run(apply_template(_make_request({}), template_id="tpl-1"))
    assert response.status_code == 201, response.body

    rows = fake.inserted_segments
    assert len(rows) == 1
    assert rows[0]["from_location_id"] == "loc-pinned-origin"
    assert rows[0]["to_location_id"] == "loc-pinned-dest"


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_single_segment_template_has_both_endpoints_open(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """For a one-segment template, that segment is both first and last —
    both its origin and destination are open endpoints when not pinned."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}

    segments = [
        {
            "sequence_order": 1,
            "from_location_type": "supplier",
            "to_location_type": "client",
            "default_label": "Direct",
            "default_days": 5,
            "from_location_id": None,
            "to_location_id": None,
        },
    ]
    fake = _FakeSupabase(
        template_rows=_template(segments),
        fallback_by_type={"supplier": "loc-s", "client": "loc-c"},
    )
    mock_get_sb.return_value = fake

    response = asyncio.run(apply_template(_make_request({}), template_id="tpl-1"))
    assert response.status_code == 201, response.body

    rows = fake.inserted_segments
    assert len(rows) == 1
    assert rows[0]["from_location_id"] is None
    assert rows[0]["to_location_id"] is None
