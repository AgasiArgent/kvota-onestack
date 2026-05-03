"""Endpoint tests for POST /api/quotes/{quote_id}/refresh-customs-snapshot.

Tests the handler directly (skipping FastAPI routing) — same pattern
as tests/api/test_customs_api.py.
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.customs import refresh_customs_snapshot_handler
from services.customs_freeze_service import FreezeSnapshotResult


def _make_request(json_body: dict | None, *, user_id: str | None = "user-1",
                  role_codes: list[str] | None = None) -> MagicMock:
    """Mock starlette Request whose .json() returns json_body and whose
    state.api_user is configured for _resolve_dual_auth."""
    req = MagicMock()
    req.json = AsyncMock(return_value=json_body or {})

    # Configure _resolve_dual_auth's expected attribute path
    if user_id is None:
        req.state.api_user = None
        req.session = {}
    else:
        api_user = MagicMock()
        api_user.id = user_id
        api_user.email = "user@example.com"
        req.state.api_user = api_user
        req.session = {}

    return req


def _patch_dual_auth(role_codes: list[str], user_id: str = "user-1"):
    """Replace _resolve_dual_auth with a stub that returns (user, roles)."""
    return patch(
        "api.customs._resolve_dual_auth",
        return_value=(
            {"id": user_id, "org_id": "org-1", "email": "user@example.com"},
            role_codes,
        ),
    )


@pytest.mark.asyncio
async def test_unauthenticated_returns_401():
    req = _make_request({"reason": "test"})

    with patch("api.customs._resolve_dual_auth", return_value=(None, [])):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 401
    body = json.loads(bytes(resp.body).decode())
    assert body["success"] is False
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_non_customs_role_returns_403():
    req = _make_request({"reason": "test"})

    with _patch_dual_auth(role_codes=["sales"]):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 403
    body = json.loads(bytes(resp.body).decode())
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_quote_not_found_returns_404():
    req = _make_request({"reason": "test"})

    mock_sb = MagicMock()
    # quote lookup raises (mimics .single() with no row)
    (mock_sb.table.return_value
            .select.return_value
            .eq.return_value
            .single.return_value
            .execute.side_effect) = Exception("no rows")

    with _patch_dual_auth(role_codes=["customs"]), \
         patch("api.customs.get_supabase", return_value=mock_sb):
        resp = await refresh_customs_snapshot_handler(
            req, "missing-quote", alta_client=MagicMock(),
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tier_3_abort_returns_409_freeze_aborted():
    req = _make_request({"reason": "manual_test"})

    mock_sb = MagicMock()
    quote_resp = MagicMock(data={"id": "quote-1", "organization_id": "org-1"})
    (mock_sb.table.return_value
            .select.return_value
            .eq.return_value
            .single.return_value
            .execute.return_value) = quote_resp

    abort_result = FreezeSnapshotResult(
        status="abort",
        items={},
        source_at_freeze="abort",
        warnings=[],
        message="Не удалось зафиксировать ставки. Обратитесь к администратору.",
    )

    with _patch_dual_auth(role_codes=["customs"]), \
         patch("api.customs.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.build_snapshot",
               new_callable=AsyncMock, return_value=abort_result):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 409
    body = json.loads(bytes(resp.body).decode())
    assert body["success"] is False
    assert body["error"]["code"] == "FREEZE_ABORTED"
    assert "администратору" in body["error"]["message"]


@pytest.mark.asyncio
async def test_happy_path_persists_snapshot_and_returns_version_id():
    req = _make_request({"reason": "scheduled_refresh"})

    # Set up supabase mock with stateful update tracking
    mock_sb = MagicMock()
    update_payloads: list[dict] = []

    quote_resp = MagicMock(data={"id": "quote-1", "organization_id": "org-1"})
    versions_resp = MagicMock(data=[{
        "id": "version-uuid-42",
        "input_variables": {"variables": {"foo": "bar"}, "products": []},
    }])

    def table_router(name: str):
        chain = MagicMock()
        if name == "quotes":
            chain.select.return_value.eq.return_value.single.return_value \
                 .execute.return_value = quote_resp
        elif name == "quote_versions":
            chain.select.return_value.eq.return_value.order.return_value \
                 .limit.return_value.execute.return_value = versions_resp

            def capture_update(payload):
                update_payloads.append(payload)
                update_chain = MagicMock()
                update_chain.eq.return_value.execute.return_value = MagicMock(data=[])
                return update_chain
            chain.update.side_effect = capture_update
        return chain

    mock_sb.table.side_effect = table_router

    snapshot_result = FreezeSnapshotResult(
        status="ok",
        items={
            "item-1": {"rates": [{"payment_type": "IMP"}], "fetched_at": "now"},
        },
        source_at_freeze="alta-live",
        warnings=[],
    )

    with _patch_dual_auth(role_codes=["customs"]), \
         patch("api.customs.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.build_snapshot",
               new_callable=AsyncMock, return_value=snapshot_result):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 200
    body = json.loads(bytes(resp.body).decode())
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["source_at_freeze"] == "alta-live"
    assert body["data"]["version_id"] == "version-uuid-42"
    assert body["data"]["item_count"] == 1

    # The merged input_variables update was issued and includes the
    # snapshot keys + the audit-bearing change_reason
    assert len(update_payloads) == 1
    payload = update_payloads[0]
    iv = payload["input_variables"]
    assert iv["customs_rates"] == snapshot_result.items
    assert iv["source_at_freeze"] == "alta-live"
    assert "scheduled_refresh" in iv["change_reason"]
    assert "user-1" in iv["change_reason"]
    # Existing keys preserved
    assert iv["variables"] == {"foo": "bar"}
    assert iv["products"] == []


@pytest.mark.asyncio
async def test_tier_2_cache_stale_returns_warnings_to_caller():
    """Tier 2 cache-stale → 200 with warnings array; UI shows yellow toast."""
    req = _make_request({"reason": "auto"})

    mock_sb = MagicMock()
    quote_resp = MagicMock(data={"id": "quote-1", "organization_id": "org-1"})
    versions_resp = MagicMock(data=[{
        "id": "version-uuid-99",
        "input_variables": {},
    }])

    def table_router(name: str):
        chain = MagicMock()
        if name == "quotes":
            chain.select.return_value.eq.return_value.single.return_value \
                 .execute.return_value = quote_resp
        elif name == "quote_versions":
            chain.select.return_value.eq.return_value.order.return_value \
                 .limit.return_value.execute.return_value = versions_resp
            chain.update.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[])
        return chain
    mock_sb.table.side_effect = table_router

    snapshot_result = FreezeSnapshotResult(
        status="cache-stale",
        items={"item-1": {"rates": [], "fetched_at": "old"}},
        source_at_freeze="cache-stale",
        warnings=[
            "8409910008/156/IMP: использован кэш (Alta недоступна)",
        ],
    )

    with _patch_dual_auth(role_codes=["customs"]), \
         patch("api.customs.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.build_snapshot",
               new_callable=AsyncMock, return_value=snapshot_result):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 200
    body = json.loads(bytes(resp.body).decode())
    assert body["data"]["status"] == "cache-stale"
    assert len(body["data"]["warnings"]) == 1
    assert "Alta" in body["data"]["warnings"][0]


@pytest.mark.asyncio
async def test_no_quote_version_returns_409_no_version():
    """Re-freeze before any /calculate ran → 409 NO_VERSION."""
    req = _make_request({"reason": "premature"})

    mock_sb = MagicMock()
    quote_resp = MagicMock(data={"id": "quote-1", "organization_id": "org-1"})
    empty_versions_resp = MagicMock(data=[])

    def table_router(name: str):
        chain = MagicMock()
        if name == "quotes":
            chain.select.return_value.eq.return_value.single.return_value \
                 .execute.return_value = quote_resp
        elif name == "quote_versions":
            chain.select.return_value.eq.return_value.order.return_value \
                 .limit.return_value.execute.return_value = empty_versions_resp
        return chain
    mock_sb.table.side_effect = table_router

    snapshot_result = FreezeSnapshotResult(
        status="ok",
        items={"item-1": {"rates": []}},
        source_at_freeze="alta-live",
    )

    with _patch_dual_auth(role_codes=["admin"]), \
         patch("api.customs.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.build_snapshot",
               new_callable=AsyncMock, return_value=snapshot_result):
        resp = await refresh_customs_snapshot_handler(
            req, "quote-1", alta_client=MagicMock(),
        )

    assert resp.status_code == 409
    body = json.loads(bytes(resp.body).decode())
    assert body["error"]["code"] == "NO_VERSION"
