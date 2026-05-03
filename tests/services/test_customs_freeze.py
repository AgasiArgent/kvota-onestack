"""Unit tests for services.customs_freeze_service — REQ-8 + Q4 ACs.

Mocks ``rate_resolver.resolve_rate`` and ``get_supabase`` so the suite
covers the three-tier fallback logic without hitting a real DB or Alta.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.customs_freeze_service import (
    AbortSnapshot,
    CacheStaleSnapshot,
    FreezeSnapshotResult,
    OkSnapshot,
    build_snapshot,
)
from services.rate_resolver import ResolvedRate
from services.alta_client import Rate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_resolved(
    *,
    payment_type: str = "IMP",
    value_1_number: float = 10.0,
    value_1_unit: str = "percent",
    source: str = "alta-live",
) -> ResolvedRate:
    rate = Rate(
        tnved_code="8409910008",
        payment_type=payment_type,
        country_or_areal="C:156",
        valid_from=date(2026, 1, 1),
        value_1_number=value_1_number,
        value_1_unit=value_1_unit,
        raw_value_string=f"{value_1_number}{value_1_unit}",
        source=source,
    )
    return ResolvedRate(
        id=f"rate-{payment_type}",
        rate=rate,
        source=source,
        source_fetched_at=datetime.now(timezone.utc),
        last_used_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_alta_client() -> MagicMock:
    return MagicMock()


def _mock_quote_items_response(items: list[dict]) -> MagicMock:
    """Build a mock supabase chain that returns these items for the
    quote_items table query inside build_snapshot.
    """
    mock_sb = MagicMock()
    items_resp = MagicMock()
    items_resp.data = items
    (mock_sb.table.return_value
            .select.return_value
            .eq.return_value
            .execute.return_value) = items_resp
    return mock_sb


# ---------------------------------------------------------------------------
# Tier 1 — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_1_live_alta_for_all_items(mock_alta_client):
    items = [
        {
            "id": "item-1",
            "hs_code": "8409910008",
            "country_of_origin_oksm": 156,
            "has_origin_certificate": False,
            "has_fta_certificate": False,
        },
    ]
    mock_sb = _mock_quote_items_response(items)

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve:
        # 7 default payment_types — return live rate for every call
        mock_resolve.return_value = _make_resolved()

        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert result.status == "ok"
    assert result.source_at_freeze == "alta-live"
    assert "item-1" in result.items
    snapshot = result.items["item-1"]
    assert snapshot["source_at_freeze"] == "alta-live"
    # 7 default payment types attempted, all returned same fixture, so 7 rates
    assert len(snapshot["rates"]) == 7
    assert result.warnings == []


@pytest.mark.asyncio
async def test_empty_quote_returns_ok_with_no_items(mock_alta_client):
    mock_sb = _mock_quote_items_response([])

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb):
        result = await build_snapshot("quote-empty", alta_client=mock_alta_client)

    assert result.status == "ok"
    assert result.items == {}
    assert result.source_at_freeze == "alta-live"


@pytest.mark.asyncio
async def test_skips_items_without_tnved_code(mock_alta_client):
    items = [
        {"id": "item-1", "hs_code": None, "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
        {"id": "item-2", "hs_code": "8409910008", "country_of_origin_oksm": None,
         "has_origin_certificate": False, "has_fta_certificate": False},
        {"id": "item-3", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]
    mock_sb = _mock_quote_items_response(items)

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve:
        mock_resolve.return_value = _make_resolved()

        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert result.status == "ok"
    # Only item-3 had both tnved_code AND country
    assert list(result.items.keys()) == ["item-3"]


# ---------------------------------------------------------------------------
# Tier 2 — Alta down, cache available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_2_cache_stale_when_resolver_returns_none(mock_alta_client):
    """When resolve_rate returns None for ALL payment_types but the
    Tier-2 stale-cache lookup finds at least one row → cache-stale.
    """
    items = [
        {"id": "item-1", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]
    mock_sb = _mock_quote_items_response(items)

    cache_row = {
        "id": "stale-rate-1",
        "tnved_code": "8409910008",
        "payment_type": "IMP",
        "country_or_areal": "C:156",
        "valid_from": "2026-01-01",
        "value_1_number": 12.0,
        "value_1_unit": "percent",
        "value_1_currency": None,
        "value_2_number": None, "value_2_unit": None, "value_2_currency": None,
        "sign_1": None,
        "raw_value_string": "12%",
        "source": "alta-live",
        "source_fetched_at": "2026-04-15T10:00:00+00:00",
        "certificate_required": False,
        "sp_certificate_required": False,
    }

    # _lookup_stale_cache exact-country call returns the cache_row for IMP only
    def lookup_chain_for_table(name: str):
        chain = MagicMock()
        if name == "tnved_rates":
            # Configure: first call (.eq("tnved_code")...).execute() returns row
            # for IMP, others return empty
            call_count = {"n": 0}

            def execute_fn():
                call_count["n"] += 1
                resp = MagicMock()
                # Only first attempt for IMP returns cache_row
                resp.data = [cache_row] if call_count["n"] == 1 else []
                return resp
            chain.select.return_value.eq.return_value.eq.return_value \
                 .eq.return_value.eq.return_value.lte.return_value \
                 .gte.return_value.eq.return_value.order.return_value \
                 .limit.return_value.execute.side_effect = execute_fn
            chain.select.return_value.eq.return_value.eq.return_value \
                 .eq.return_value.eq.return_value.lte.return_value \
                 .gte.return_value.is_.return_value.order.return_value \
                 .limit.return_value.execute.side_effect = execute_fn
        elif name == "country_areals":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=[])
        elif name == "quote_items":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=items)
        return chain

    mock_sb.table.side_effect = lookup_chain_for_table

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve:
        # Resolver always returns None — simulating Alta down
        mock_resolve.return_value = None

        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert result.status == "cache-stale"
    assert result.source_at_freeze == "cache-stale"
    assert "item-1" in result.items
    # At least one warning surfaces about cache use
    assert any("кэш" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Tier 3 — abort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tier_3_abort_when_no_live_no_cache(mock_alta_client):
    """No live rates AND no stale-cache rows → abort + Telegram alert."""
    items = [
        {"id": "item-1", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]

    def lookup_chain_for_table(name: str):
        chain = MagicMock()
        if name == "quote_items":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=items)
        else:
            # tnved_rates and country_areals always empty
            empty_resp = MagicMock(data=[])
            for path in [
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.eq.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.is_.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.execute,
            ]:
                path.return_value = empty_resp
        return chain

    mock_sb = MagicMock()
    mock_sb.table.side_effect = lookup_chain_for_table

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve, \
         patch("services.customs_freeze_service.notify_admin",
               new_callable=AsyncMock) as mock_notify:
        mock_resolve.return_value = None

        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert result.status == "abort"
    assert result.source_at_freeze == "abort"
    assert result.message is not None
    assert "не удалось" in result.message.lower() or "попробуйте" in result.message.lower()
    # Telegram admin alert was emitted
    mock_notify.assert_called_once()


@pytest.mark.asyncio
async def test_tier_3_abort_message_mentions_user_action(mock_alta_client):
    """The abort message should advise the user what to do (per Q4)."""
    items = [
        {"id": "item-1", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]

    def lookup_chain_for_table(name: str):
        chain = MagicMock()
        if name == "quote_items":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=items)
        else:
            empty_resp = MagicMock(data=[])
            for path in [
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.eq.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.is_.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.execute,
            ]:
                path.return_value = empty_resp
        return chain

    mock_sb = MagicMock()
    mock_sb.table.side_effect = lookup_chain_for_table

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve, \
         patch("services.customs_freeze_service.notify_admin",
               new_callable=AsyncMock):
        mock_resolve.return_value = None
        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert "администратору" in (result.message or "")


# ---------------------------------------------------------------------------
# Telegram failure should NOT crash the freeze (defensive)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_failure_does_not_break_abort_response(mock_alta_client):
    items = [
        {"id": "item-1", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]

    def lookup_chain_for_table(name: str):
        chain = MagicMock()
        if name == "quote_items":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=items)
        else:
            empty_resp = MagicMock(data=[])
            for path in [
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.eq.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.is_.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.execute,
            ]:
                path.return_value = empty_resp
        return chain

    mock_sb = MagicMock()
    mock_sb.table.side_effect = lookup_chain_for_table

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new_callable=AsyncMock) as mock_resolve, \
         patch("services.customs_freeze_service.notify_admin",
               new_callable=AsyncMock) as mock_notify:
        mock_resolve.return_value = None
        mock_notify.side_effect = RuntimeError("telegram bot down")

        # Should NOT raise — the abort result must still be returned
        result = await build_snapshot("quote-1", alta_client=mock_alta_client)

    assert result.status == "abort"
    assert result.message is not None


# ---------------------------------------------------------------------------
# Aggregate worst-tier semantics across multi-item quotes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_worst_tier_one_abort_makes_all_abort(mock_alta_client):
    """If item A is Tier 1 and item B is Tier 3, aggregate is abort."""
    items = [
        {"id": "good", "hs_code": "8409910008", "country_of_origin_oksm": 156,
         "has_origin_certificate": False, "has_fta_certificate": False},
        {"id": "bad",  "hs_code": "9999999999", "country_of_origin_oksm": 999,
         "has_origin_certificate": False, "has_fta_certificate": False},
    ]

    def lookup_chain_for_table(name: str):
        chain = MagicMock()
        if name == "quote_items":
            chain.select.return_value.eq.return_value.execute.return_value = \
                MagicMock(data=items)
        else:
            empty_resp = MagicMock(data=[])
            for path in [
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.eq.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.eq.return_value
                     .eq.return_value.eq.return_value.lte.return_value
                     .gte.return_value.is_.return_value.order.return_value
                     .limit.return_value.execute,
                chain.select.return_value.eq.return_value.execute,
            ]:
                path.return_value = empty_resp
        return chain

    mock_sb = MagicMock()
    mock_sb.table.side_effect = lookup_chain_for_table

    async def resolve_side_effect(**kwargs):
        if kwargs["tnved_code"] == "8409910008":
            return _make_resolved()
        return None

    with patch("services.customs_freeze_service.get_supabase", return_value=mock_sb), \
         patch("services.customs_freeze_service.resolve_rate",
               new=resolve_side_effect), \
         patch("services.customs_freeze_service.notify_admin",
               new_callable=AsyncMock):
        result = await build_snapshot("quote-mixed", alta_client=mock_alta_client)

    assert result.status == "abort"


# ---------------------------------------------------------------------------
# FreezeSnapshotResult shape
# ---------------------------------------------------------------------------


def test_ok_snapshot_shape():
    """OkSnapshot — Tier 1 outcome. Live Alta for every item."""
    r = OkSnapshot(items={"x": {"rates": []}})
    assert r.status == "ok"
    assert r.source_at_freeze == "alta-live"
    assert r.warnings == []
    assert r.message is None
    assert r.items == {"x": {"rates": []}}


def test_cache_stale_snapshot_shape():
    """CacheStaleSnapshot — Tier 2 outcome. Cache fallback used."""
    warnings = ["8409910008/156/IMP: использован кэш (Alta недоступна)"]
    r = CacheStaleSnapshot(items={"x": {"rates": []}}, warnings=warnings)
    assert r.status == "cache-stale"
    assert r.source_at_freeze == "cache-stale"
    assert r.warnings == warnings
    assert r.message is None


def test_abort_snapshot_shape():
    """AbortSnapshot — Tier 3 outcome. Carries a user-facing message."""
    msg = "Не удалось получить актуальные ставки для freeze."
    warnings = ["item failure"]
    r = AbortSnapshot(items={}, warnings=warnings, message=msg)
    assert r.status == "abort"
    assert r.source_at_freeze == "abort"
    assert r.warnings == warnings
    assert r.message == msg


def test_freeze_snapshot_result_is_union_of_three_variants():
    """FreezeSnapshotResult must accept any of the three variant types
    (typing.Union annotation), preserving backwards-compat for callers
    that read .status / .warnings / .message generically.
    """
    variants: list[FreezeSnapshotResult] = [
        OkSnapshot(items={}),
        CacheStaleSnapshot(items={}, warnings=["w"]),
        AbortSnapshot(items={}, warnings=[], message="m"),
    ]
    statuses = {v.status for v in variants}
    assert statuses == {"ok", "cache-stale", "abort"}
    # Every variant exposes the same attribute surface
    for v in variants:
        assert hasattr(v, "items")
        assert hasattr(v, "warnings")
        assert hasattr(v, "message")
        assert hasattr(v, "source_at_freeze")
