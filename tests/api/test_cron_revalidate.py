"""Tests for ``POST /api/cron/revalidate-rates`` — REQ-6 customs-phase-1.

Covers:
- ``X-Cron-Secret`` header validation (missing → 403, wrong → 403).
- Top-1000 selection ordered by ``MAX(last_used_at) DESC`` filtered to
  rows with ``source_fetched_at < now() - 7d``.
- Idempotent re-run within 7 days = no Alta calls (returns processed=0).
- Bulk upsert with ``source='alta-revalidate'``.
- Areal-keyed rates (``A:EAEU``) are skipped — Alta is country-bound.
- ``AltaApiError(140)`` aborts loop and emits Telegram admin alert.
- ``packet_left < 50`` aborts loop and emits Telegram admin alert.
- Response envelope shape ``{success, data: {processed, hits, updates,
  failures, packet_left_at_end}}``.

Mocks Supabase + AltaClient + telegram_service so the suite never hits
real DB / API / Telegram.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Project root on path
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from api import cron as cron_module  # noqa: E402
from api.app import api_sub_app  # noqa: E402
from services.alta_client import AltaApiError, Rate, get_alta_client  # noqa: E402


# ---------------------------------------------------------------------------
# Stub Supabase client — minimal subset of supabase-py used by cron handler.
# ---------------------------------------------------------------------------


class _StubQuery:
    """Chainable query emulating supabase-py for the subset used here.

    Supports:
      table(...).select(...).lt(col, val).execute()         → fetch stale rows
      table(...).upsert([rows...], on_conflict=...).execute() → bulk write
    """

    def __init__(self, client: "_StubSupabase", table_name: str) -> None:
        self._client = client
        self._table = table_name
        self._filters: list[tuple[str, Any, Any]] = []
        self._upsert_payload: list[dict] | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_StubQuery":
        return self

    def lt(self, col: str, val: Any) -> "_StubQuery":
        self._filters.append(("lt", col, val))
        return self

    def upsert(
        self, payload: list[dict], *, on_conflict: str | None = None
    ) -> "_StubQuery":
        self._upsert_payload = payload
        return self

    def execute(self) -> Any:
        if self._upsert_payload is not None:
            self._client.upsert_calls.append(
                {"table": self._table, "payload": self._upsert_payload}
            )
            return MagicMock(data=self._upsert_payload)

        rows = list(self._client.tables.get(self._table, []))
        for op, col, val in self._filters:
            if op == "lt":
                # ISO-string comparison works for timestamp fields used here
                rows = [r for r in rows if (r.get(col) or "") < val]
        return MagicMock(data=rows)


class _StubSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}
        self.upsert_calls: list[dict] = []

    def table(self, name: str) -> _StubQuery:
        return _StubQuery(self, name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    return TestClient(api_sub_app)


@pytest.fixture
def cron_secret() -> str:
    return "test-cron-secret-revalidate"


@pytest.fixture(autouse=True)
def _set_cron_secret(cron_secret: str):
    prev = os.environ.get("CRON_SECRET")
    os.environ["CRON_SECRET"] = cron_secret
    yield
    if prev is None:
        os.environ.pop("CRON_SECRET", None)
    else:
        os.environ["CRON_SECRET"] = prev


@pytest.fixture
def stub_sb() -> _StubSupabase:
    return _StubSupabase()


@pytest.fixture
def alta_client_mock() -> MagicMock:
    """MagicMock with async ``get_rates`` returning an empty list by default.

    ``last_packet_left`` is explicitly None so the handler's
    ``packet_left < FLOOR`` check is a no-op unless a test sets it.
    """
    mock = MagicMock()
    mock.get_rates = AsyncMock(return_value=[])
    mock.last_packet_left = None
    return mock


@pytest.fixture
def notify_admin_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def patched_cron(
    stub_sb: _StubSupabase,
    alta_client_mock: MagicMock,
    notify_admin_mock: AsyncMock,
):
    """Patch get_supabase + get_alta_client + telegram_service.notify_admin.

    The cron handler imports ``notify_admin`` from ``services.telegram_service``;
    we patch it in both ``api.cron`` and ``services.telegram_service`` so the
    name lookup in the handler resolves to our mock regardless of where the
    handler imports from.
    """
    api_sub_app.dependency_overrides[get_alta_client] = lambda: alta_client_mock
    try:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(cron_module, "notify_admin", notify_admin_mock):
            yield
    finally:
        api_sub_app.dependency_overrides.pop(get_alta_client, None)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _stale_iso(days: int = 8) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _fresh_iso(days: int = 1) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _seed_rate_row(
    sb: _StubSupabase,
    *,
    tnved_code: str,
    country_or_areal: str | None,
    last_used_at: str,
    source_fetched_at: str,
    payment_type: str = "IMP",
) -> None:
    sb.tables.setdefault("tnved_rates", []).append({
        "id": f"row-{len(sb.tables.get('tnved_rates', []))}",
        "tnved_code": tnved_code,
        "country_or_areal": country_or_areal,
        "payment_type": payment_type,
        "last_used_at": last_used_at,
        "source_fetched_at": source_fetched_at,
        "valid_from": "2025-01-01",
    })


def _make_rate(
    *,
    tnved_code: str = "1234567890",
    payment_type: str = "IMP",
    country_or_areal: str | None = "C:643",
) -> Rate:
    return Rate(
        tnved_code=tnved_code,
        payment_type=payment_type,
        country_or_areal=country_or_areal,
        valid_from=date(2025, 1, 1),
        value_1_number=10.0,
        value_1_unit="percent",
    )


# ===========================================================================
# Auth / route registration
# ===========================================================================


class TestRouteRegistered:
    def test_post_revalidate_rates_registered(
        self, subapp_client: TestClient, patched_cron
    ) -> None:
        # Without X-Cron-Secret → 403 from the handler. 404 would mean
        # the route was never registered.
        response = subapp_client.post("/cron/revalidate-rates")
        assert response.status_code != 404, (
            f"Route not registered: POST /cron/revalidate-rates returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_schema_includes_revalidate_rates(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        assert "/cron/revalidate-rates" in paths
        assert "post" in paths["/cron/revalidate-rates"]


class TestAuth:
    def test_missing_secret_returns_403(
        self, subapp_client: TestClient, patched_cron
    ) -> None:
        response = subapp_client.post("/cron/revalidate-rates")
        assert response.status_code == 403

    def test_wrong_secret_returns_403(
        self, subapp_client: TestClient, patched_cron
    ) -> None:
        response = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": "wrong"}
        )
        assert response.status_code == 403


# ===========================================================================
# Selection logic
# ===========================================================================


class TestStaleSelection:
    """Only rows older than 7 days enter the revalidation loop."""

    def test_idempotent_no_op_when_no_stale_rows(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        # Only fresh rows in the cache
        _seed_rate_row(
            stub_sb,
            tnved_code="1111111111",
            country_or_areal="C:643",
            last_used_at=_fresh_iso(1),
            source_fetched_at=_fresh_iso(1),
        )

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert body["data"]["processed"] == 0
        # No Alta calls — pure no-op
        assert alta_client_mock.get_rates.await_count == 0

    def test_only_stale_rows_processed(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        # Mix: one stale + one fresh
        _seed_rate_row(
            stub_sb,
            tnved_code="1111111111",
            country_or_areal="C:643",
            last_used_at=_stale_iso(10),
            source_fetched_at=_stale_iso(10),
        )
        _seed_rate_row(
            stub_sb,
            tnved_code="2222222222",
            country_or_areal="C:156",
            last_used_at=_fresh_iso(1),
            source_fetched_at=_fresh_iso(1),
        )
        alta_client_mock.get_rates.return_value = [
            _make_rate(tnved_code="1111111111")
        ]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["data"]["processed"] == 1
        # Only the stale row's TNVED was queried
        assert alta_client_mock.get_rates.await_count == 1
        call_args = alta_client_mock.get_rates.await_args
        assert call_args.kwargs.get("tncode") == "1111111111"


class TestTopRanking:
    """Top-N selection: most-recently-used among stale rows wins."""

    def test_dedupes_pairs_keeping_max_last_used(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        # Two stale rows for the same (tnved, country) pair —
        # MAX(last_used_at) wins as the ranking key.
        _seed_rate_row(
            stub_sb,
            tnved_code="9999999999",
            country_or_areal="C:643",
            last_used_at=_stale_iso(8),  # older max-candidate
            source_fetched_at=_stale_iso(10),
            payment_type="IMP",
        )
        _seed_rate_row(
            stub_sb,
            tnved_code="9999999999",
            country_or_areal="C:643",
            last_used_at=_stale_iso(7).replace("-07:", "-08:"),
            source_fetched_at=_stale_iso(9),
            payment_type="NDS",
        )

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # Pair appears once, not twice
        assert alta_client_mock.get_rates.await_count == 1


# ===========================================================================
# Areal handling
# ===========================================================================


class TestArealRowsSkipped:
    """Areal-keyed rows (``A:EAEU``) cannot be re-fetched country-bound."""

    def test_areal_keyed_rates_not_alta_fetched(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        _seed_rate_row(
            stub_sb,
            tnved_code="3333333333",
            country_or_areal="A:EAEU",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
        )

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # Areal rows are skipped — no Alta call
        assert alta_client_mock.get_rates.await_count == 0


# ===========================================================================
# Upsert behaviour
# ===========================================================================


class TestUpsertSource:
    def test_upsert_uses_alta_revalidate_source(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        _seed_rate_row(
            stub_sb,
            tnved_code="4444444444",
            country_or_areal="C:643",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
        )
        alta_client_mock.get_rates.return_value = [
            _make_rate(tnved_code="4444444444")
        ]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # Inspect upsert payload
        assert len(stub_sb.upsert_calls) >= 1
        payload = stub_sb.upsert_calls[0]["payload"]
        assert all(row["source"] == "alta-revalidate" for row in payload)


# ===========================================================================
# Failure modes — Telegram alerts + abort
# ===========================================================================


class TestAltaError140Aborts:
    def test_insufficient_funds_aborts_with_telegram_alert(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # Two stale pairs — should only see one Alta call before the abort
        _seed_rate_row(
            stub_sb,
            tnved_code="1111111111",
            country_or_areal="C:643",
            last_used_at=_stale_iso(7),
            source_fetched_at=_stale_iso(10),
        )
        _seed_rate_row(
            stub_sb,
            tnved_code="2222222222",
            country_or_areal="C:156",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
        )

        alta_client_mock.get_rates.side_effect = AltaApiError(
            140, "Insufficient funds"
        )

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # Loop aborts on first 140
        assert alta_client_mock.get_rates.await_count == 1
        assert notify_admin_mock.await_count == 1
        # The stats should reflect the failure
        assert r.json()["data"]["failures"] >= 1


class TestPacketLowAborts:
    def test_packet_left_below_50_aborts_with_telegram_alert(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # Two stale pairs — first call should land then trigger abort.
        _seed_rate_row(
            stub_sb,
            tnved_code="1111111111",
            country_or_areal="C:643",
            last_used_at=_stale_iso(7),
            source_fetched_at=_stale_iso(10),
        )
        _seed_rate_row(
            stub_sb,
            tnved_code="2222222222",
            country_or_areal="C:156",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
        )

        alta_client_mock.get_rates.return_value = [_make_rate()]
        # The handler reads packet_left from the client after each call.
        alta_client_mock.last_packet_left = 30

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # First fetch succeeds, then loop aborts before second pair
        assert alta_client_mock.get_rates.await_count == 1
        assert notify_admin_mock.await_count == 1


# ===========================================================================
# Response envelope
# ===========================================================================


class TestResponseShape:
    def test_response_has_processed_hits_updates_failures(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        _seed_rate_row(
            stub_sb,
            tnved_code="5555555555",
            country_or_areal="C:643",
            last_used_at=_stale_iso(7),
            source_fetched_at=_stale_iso(10),
        )
        alta_client_mock.get_rates.return_value = [
            _make_rate(tnved_code="5555555555")
        ]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        data = body["data"]
        for key in ("processed", "hits", "updates", "failures"):
            assert key in data, f"Missing key {key!r} in response data"
