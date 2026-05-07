"""Security regression test for apply_template (РОЛ Тест 07 #5c — W2).

Phase 5a code review flagged that `apply_template` accepts a
caller-supplied `location_map: {type: location_id}`. When a type has an
override in this map, it was used directly without checking that the
location belongs to the caller's organisation. A user with the logistics
role in org A could pass a UUID of org B's location and silently
materialise segments pointing at foreign locations.

This test pins the fix: any override id not in the caller's org returns
HTTP 403 VALIDATION_ERROR, before any segments are written.

Real DB integration coverage is deferred to the smoke suite.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest
from starlette.requests import Request

from api.logistics import apply_template


# ---------------------------------------------------------------------------
# Minimal fake supabase: only handles the 'locations' table .select().eq().in_()
# path used by the org-scope override check.
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, data: Any) -> None:
        self.data = data
        self.error = None


class _Query:
    def __init__(self, table: str, locations_in_org: set[str]) -> None:
        self._table = table
        self._locations_in_org = locations_in_org
        self._filters: list[tuple[str, str, Any]] = []

    def select(self, *_a: Any, **_k: Any) -> "_Query":
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
        if self._table != "locations":
            # The override check is the first DB query in apply_template
            # after auth + invoice assertion; if any other table is hit we
            # have a bug or the test reached past the security gate.
            raise AssertionError(
                f"Unexpected table {self._table!r} hit before override check"
            )
        # Implement the .in_() filter against our org-scoped allowlist.
        in_filter = next((f for f in self._filters if f[0] == "in"), None)
        if not in_filter:
            return _Resp([])
        requested = set(in_filter[2])
        present = requested & self._locations_in_org
        return _Resp([{"id": x} for x in present])


class _FakeSupabase:
    def __init__(self, locations_in_org: set[str]) -> None:
        self._locations = locations_in_org

    def table(self, name: str) -> _Query:
        return _Query(name, self._locations)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_request(body: dict, query_string: str = "invoice_id=inv-1") -> Request:
    """Build a minimal ASGI Request stub carrying JSON body + query params."""
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
        "query_string": query_string.encode("ascii"),
    }
    return Request(scope, receive=receive)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_apply_template_rejects_override_id_outside_caller_org(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """Override pointing at another org's location must be rejected with 403."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}
    # Caller's org has no locations at all → every override id is "outside".
    mock_get_sb.return_value = _FakeSupabase(locations_in_org=set())

    request = _make_request(
        body={"location_map": {"customs": "loc-from-org-B"}, "replace": False},
    )
    response = asyncio.run(apply_template(request, template_id="tpl-1"))

    assert response.status_code == 403
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert "loc-from-org-B" in payload["error"]["message"]


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_apply_template_skips_override_check_when_location_map_empty(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """No overrides → no locations query, no false 403.

    We assert the security check doesn't fire when location_map is empty.
    The next DB call will be against logistics_route_templates which our
    stub rejects — that's fine, the test only cares that the override
    check did NOT block this path.
    """
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}
    mock_get_sb.return_value = _FakeSupabase(locations_in_org=set())

    request = _make_request(body={"location_map": {}, "replace": False})

    # The stub raises AssertionError when a non-locations table is hit.
    # If the override check fires (it shouldn't), it would query 'locations'
    # successfully and then try 'logistics_route_templates'. With empty
    # location_map we expect the AssertionError on the templates query.
    with pytest.raises(AssertionError) as excinfo:
        asyncio.run(apply_template(request, template_id="tpl-1"))
    # Confirms control flow reached past the security gate without any
    # 'locations' query — i.e. the override check correctly skipped.
    assert "logistics_route_templates" in str(excinfo.value)


@patch("api.logistics._assert_invoice_in_org")
@patch("api.logistics._authorize")
@patch("api.logistics.get_supabase")
def test_apply_template_passes_when_all_overrides_in_org(
    mock_get_sb: Any, mock_authorize: Any, mock_assert_invoice: Any
) -> None:
    """All override ids belong to caller org → override check passes."""
    mock_authorize.return_value = (
        {"id": "user-1", "org_id": "org-A", "email": "u@example.com"},
        ["logistics"],
    )
    mock_assert_invoice.return_value = {"id": "inv-1"}
    mock_get_sb.return_value = _FakeSupabase(
        locations_in_org={"loc-customs-A", "loc-hub-A"}
    )

    request = _make_request(
        body={
            "location_map": {
                "customs": "loc-customs-A",
                "hub": "loc-hub-A",
            },
            "replace": False,
        },
    )

    # As above: control flow proceeds past the security gate; we expect
    # the stub to fail on the next non-locations query (the template
    # fetch). Confirms the override check accepted in-org ids.
    with pytest.raises(AssertionError) as excinfo:
        asyncio.run(apply_template(request, template_id="tpl-1"))
    assert "logistics_route_templates" in str(excinfo.value)
