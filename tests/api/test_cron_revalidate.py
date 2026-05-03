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
      table(...).select(...).lt|gte|eq(col, val).execute()  → fetch rows
      table(...).upsert([rows...], on_conflict=...).execute() → bulk write
      table(...).update({...}).eq(col, val).execute()       → row update
    """

    def __init__(self, client: "_StubSupabase", table_name: str) -> None:
        self._client = client
        self._table = table_name
        self._filters: list[tuple[str, Any, Any]] = []
        self._upsert_payload: list[dict] | None = None
        self._update_payload: dict | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_StubQuery":
        return self

    def lt(self, col: str, val: Any) -> "_StubQuery":
        self._filters.append(("lt", col, val))
        return self

    def gte(self, col: str, val: Any) -> "_StubQuery":
        self._filters.append(("gte", col, val))
        return self

    def eq(self, col: str, val: Any) -> "_StubQuery":
        self._filters.append(("eq", col, val))
        return self

    def upsert(
        self, payload: list[dict], *, on_conflict: str | None = None
    ) -> "_StubQuery":
        self._upsert_payload = payload
        return self

    def update(self, payload: dict) -> "_StubQuery":
        self._update_payload = payload
        return self

    @staticmethod
    def _matches(row: dict, op: str, col: str, val: Any) -> bool:
        cell = row.get(col)
        if op == "lt":
            return (cell or "") < val
        if op == "gte":
            # String/ISO-timestamp comparison: None never satisfies >= cutoff.
            if cell is None:
                return False
            # Numeric vs string handled uniformly via Python's mixed-type
            # gracefully degrades — both sides come from same column type.
            try:
                return cell >= val
            except TypeError:
                return False
        if op == "eq":
            return cell == val
        return True

    def _filtered_rows(self) -> list[dict]:
        rows = list(self._client.tables.get(self._table, []))
        for op, col, val in self._filters:
            rows = [r for r in rows if self._matches(r, op, col, val)]
        return rows

    def execute(self) -> Any:
        if self._upsert_payload is not None:
            self._client.upsert_calls.append(
                {"table": self._table, "payload": self._upsert_payload}
            )
            return MagicMock(data=self._upsert_payload)

        if self._update_payload is not None:
            matched = self._filtered_rows()
            for row in matched:
                row.update(self._update_payload)
            self._client.update_calls.append({
                "table": self._table,
                "payload": dict(self._update_payload),
                "filters": list(self._filters),
                "matched_count": len(matched),
            })
            return MagicMock(data=matched)

        return MagicMock(data=self._filtered_rows())


class _StubSupabase:
    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}
        self.upsert_calls: list[dict] = []
        self.update_calls: list[dict] = []

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
    revalidate_failure_count: int = 0,
    revalidate_failed_at: str | None = None,
) -> None:
    sb.tables.setdefault("tnved_rates", []).append({
        "id": f"row-{len(sb.tables.get('tnved_rates', []))}",
        "tnved_code": tnved_code,
        "country_or_areal": country_or_areal,
        "payment_type": payment_type,
        "last_used_at": last_used_at,
        "source_fetched_at": source_fetched_at,
        "valid_from": "2025-01-01",
        "revalidate_failure_count": revalidate_failure_count,
        "revalidate_failed_at": revalidate_failed_at,
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


# ===========================================================================
# M6 — REVALIDATE_MAX_FETCH truncation alert
# ===========================================================================


class TestMaxFetchTruncationAlert:
    """When stale-row count >= REVALIDATE_MAX_FETCH, ops gets a Telegram alert."""

    @pytest.fixture(autouse=True)
    def _clean_throttle(self):
        """Throttle dict in cron module persists across tests — clear it."""
        cron_module._cron_last_alert_at.clear()
        yield
        cron_module._cron_last_alert_at.clear()

    def test_alert_fires_when_max_fetch_cap_hit(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # Lower cap so the test stays fast and deterministic
        with patch.object(cron_module, "REVALIDATE_MAX_FETCH", 5):
            # Seed exactly the cap — the >= comparison in the handler
            # must trigger the alert.
            for i in range(5):
                _seed_rate_row(
                    stub_sb,
                    tnved_code=f"99999999{i:02d}",
                    country_or_areal="C:643",
                    last_used_at=_stale_iso(8),
                    source_fetched_at=_stale_iso(10),
                )
            r = subapp_client.post(
                "/cron/revalidate-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 200, r.text
        # The truncation alert is one of the notify_admin calls.
        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        assert any(
            "hard cap" in str(m) or "REVALIDATE_MAX_FETCH" in str(m)
            for m in alert_messages
        ), f"No truncation alert in: {alert_messages!r}"

    def test_no_alert_when_below_cap(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        with patch.object(cron_module, "REVALIDATE_MAX_FETCH", 100):
            _seed_rate_row(
                stub_sb,
                tnved_code="1111111111",
                country_or_areal="C:643",
                last_used_at=_stale_iso(8),
                source_fetched_at=_stale_iso(10),
            )
            r = subapp_client.post(
                "/cron/revalidate-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 200, r.text
        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        # No truncation alert when row count stays below cap
        assert not any(
            "hard cap" in str(m) or "REVALIDATE_MAX_FETCH" in str(m)
            for m in alert_messages
        )


# ===========================================================================
# M8 — high failure-ratio alert
# ===========================================================================


class TestFailureRatioAlert:
    """When > 50% of Alta calls fail, end-of-run alert fires."""

    @pytest.fixture(autouse=True)
    def _clean_throttle(self):
        cron_module._cron_last_alert_at.clear()
        yield
        cron_module._cron_last_alert_at.clear()

    def test_alert_when_majority_fail(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # 4 stale pairs — 3 will fail, 1 succeeds → 75% failure ratio
        for i, code in enumerate(
            ("1111111111", "2222222222", "3333333333", "4444444444")
        ):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{100 + i}",
                last_used_at=_stale_iso(8 - i),
                source_fetched_at=_stale_iso(10),
            )

        call_seq = {"n": 0}

        async def _fail_three_succeed_one(*args, **kwargs):
            call_seq["n"] += 1
            if call_seq["n"] <= 3:
                raise RuntimeError(f"alta error #{call_seq['n']}")
            return [_make_rate(tnved_code=kwargs.get("tncode", "x"))]

        alta_client_mock.get_rates.side_effect = _fail_three_succeed_one

        r = subapp_client.post(
            "/cron/revalidate-rates",
            headers={"X-Cron-Secret": cron_secret},
        )
        assert r.status_code == 200, r.text
        # Alert message references high failure ratio
        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        assert any(
            "failure" in str(m).lower() and "%" in str(m)
            for m in alert_messages
        ), f"No failure-ratio alert in: {alert_messages!r}"

    def test_no_alert_when_failures_under_threshold(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # 4 stale pairs — 1 fails, 3 succeed → 25% failure ratio
        for i, code in enumerate(
            ("1111111111", "2222222222", "3333333333", "4444444444")
        ):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{100 + i}",
                last_used_at=_stale_iso(8 - i),
                source_fetched_at=_stale_iso(10),
            )

        call_seq = {"n": 0}

        async def _fail_one_succeed_three(*args, **kwargs):
            call_seq["n"] += 1
            if call_seq["n"] == 1:
                raise RuntimeError("alta transient error")
            return [_make_rate(tnved_code=kwargs.get("tncode", "x"))]

        alta_client_mock.get_rates.side_effect = _fail_one_succeed_three

        r = subapp_client.post(
            "/cron/revalidate-rates",
            headers={"X-Cron-Secret": cron_secret},
        )
        assert r.status_code == 200, r.text
        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        assert not any(
            "failure ratio" in str(m).lower()
            for m in alert_messages
        ), f"Unexpected failure-ratio alert at 25%: {alert_messages!r}"

    def test_no_alert_when_processed_zero(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # No stale rows → processed=0 → no division-by-zero, no alert
        r = subapp_client.post(
            "/cron/revalidate-rates",
            headers={"X-Cron-Secret": cron_secret},
        )
        assert r.status_code == 200, r.text
        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        assert not any(
            "failure ratio" in str(m).lower()
            for m in alert_messages
        )


# ===========================================================================
# M9 — poison-pill backoff for chronically-failing pairs
# ===========================================================================


def _yesterday_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def _eight_days_ago_iso() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()


class TestPoisonPillSkip:
    """Pairs with revalidate_failure_count >= 3 within the 7d backoff are skipped."""

    @pytest.fixture(autouse=True)
    def _clean_throttle(self):
        cron_module._cron_last_alert_at.clear()
        yield
        cron_module._cron_last_alert_at.clear()

    def test_skips_poison_pill_pairs_within_backoff(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        # 5 stale rows total: 2 are poison-pilled (failure_count=3,
        # failed_at=yesterday → still inside 7d backoff window).
        for i, code in enumerate(("1111111111", "2222222222", "3333333333")):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{100 + i}",
                last_used_at=_stale_iso(8 - i),
                source_fetched_at=_stale_iso(10),
            )
        for i, code in enumerate(("9990000001", "9990000002")):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{200 + i}",
                last_used_at=_stale_iso(7 - i),
                source_fetched_at=_stale_iso(10),
                revalidate_failure_count=3,
                revalidate_failed_at=_yesterday_iso(),
            )
        alta_client_mock.get_rates.return_value = [_make_rate()]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # Only the 3 non-poison pairs hit Alta — the 2 poison-pilled ones skipped
        assert alta_client_mock.get_rates.await_count == 3
        called_codes = {
            call.kwargs["tncode"]
            for call in alta_client_mock.get_rates.await_args_list
        }
        assert "9990000001" not in called_codes
        assert "9990000002" not in called_codes

    def test_retries_poison_pill_pairs_after_7_day_backoff(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        # 5 stale rows total: 2 are poison-pilled but failed_at=8 days ago
        # → backoff has expired, they MUST be retried.
        for i, code in enumerate(("1111111111", "2222222222", "3333333333")):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{100 + i}",
                last_used_at=_stale_iso(8 - i),
                source_fetched_at=_stale_iso(10),
            )
        for i, code in enumerate(("9990000001", "9990000002")):
            _seed_rate_row(
                stub_sb,
                tnved_code=code,
                country_or_areal=f"C:{200 + i}",
                last_used_at=_stale_iso(7 - i),
                source_fetched_at=_stale_iso(10),
                revalidate_failure_count=3,
                revalidate_failed_at=_eight_days_ago_iso(),
            )
        alta_client_mock.get_rates.return_value = [_make_rate()]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        # All 5 pairs are retried — backoff expired
        assert alta_client_mock.get_rates.await_count == 5
        called_codes = {
            call.kwargs["tncode"]
            for call in alta_client_mock.get_rates.await_args_list
        }
        assert "9990000001" in called_codes
        assert "9990000002" in called_codes


class TestPoisonPillCounterUpdates:
    """Per-pair UPDATEs are issued on success and Alta failure."""

    @pytest.fixture(autouse=True)
    def _clean_throttle(self):
        cron_module._cron_last_alert_at.clear()
        yield
        cron_module._cron_last_alert_at.clear()

    def test_increments_failure_count_on_alta_error(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        _seed_rate_row(
            stub_sb,
            tnved_code="1234567890",
            country_or_areal="C:643",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
            revalidate_failure_count=1,
        )
        alta_client_mock.get_rates.side_effect = AltaApiError(120, "bad code")

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text

        # Find the increment UPDATE for our pair
        increments = [
            c for c in stub_sb.update_calls
            if c["payload"].get("revalidate_failed_at") is not None
            and c["payload"].get("revalidate_failure_count") is not None
        ]
        assert len(increments) >= 1, (
            f"Expected at least one increment UPDATE; got: {stub_sb.update_calls!r}"
        )
        # New count = previous (1) + 1 = 2
        target = next(
            (c for c in increments if c["payload"].get("revalidate_failure_count") == 2),
            None,
        )
        assert target is not None, (
            f"No UPDATE setting failure_count=2 (prev=1+1); calls: {stub_sb.update_calls!r}"
        )
        # And revalidate_failed_at was set (non-None)
        assert target["payload"].get("revalidate_failed_at")

    def test_resets_failure_count_on_success(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        patched_cron,
    ) -> None:
        _seed_rate_row(
            stub_sb,
            tnved_code="1234567890",
            country_or_areal="C:643",
            last_used_at=_stale_iso(8),
            source_fetched_at=_stale_iso(10),
            revalidate_failure_count=2,
            revalidate_failed_at=_yesterday_iso(),
        )
        alta_client_mock.get_rates.return_value = [
            _make_rate(tnved_code="1234567890")
        ]

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text

        # Verify a reset UPDATE was issued
        resets = [
            c for c in stub_sb.update_calls
            if c["payload"].get("revalidate_failure_count") == 0
            and c["payload"].get("revalidate_failed_at") is None
        ]
        assert len(resets) >= 1, (
            f"Expected reset UPDATE; got: {stub_sb.update_calls!r}"
        )
        # Filter must target the pair (tnved_code + country_or_areal)
        target = resets[0]
        filter_cols = {f[1]: f[2] for f in target["filters"] if f[0] == "eq"}
        assert filter_cols.get("tnved_code") == "1234567890"
        assert filter_cols.get("country_or_areal") == "C:643"


class TestPoisonPillTelegramAlert:
    """End-of-run alert when many pairs are parked under poison-pill backoff."""

    @pytest.fixture(autouse=True)
    def _clean_throttle(self):
        cron_module._cron_last_alert_at.clear()
        yield
        cron_module._cron_last_alert_at.clear()

    def test_telegram_alert_when_10_pairs_in_poison_state(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # Seed 12 currently-poisoned rows (failure_count=3, failed_at=yesterday)
        # so the post-loop count query returns >= POISON_PILL_ALERT_COUNT.
        for i in range(12):
            _seed_rate_row(
                stub_sb,
                tnved_code=f"99900000{i:02d}",
                country_or_areal=f"C:{700 + i}",
                last_used_at=_stale_iso(8),
                source_fetched_at=_stale_iso(10),
                revalidate_failure_count=3,
                revalidate_failed_at=_yesterday_iso(),
            )

        r = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text

        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        # Exactly one poison-pill alert in the messages
        poison_alerts = [
            m for m in alert_messages if "poison-pill" in str(m).lower()
        ]
        assert len(poison_alerts) == 1, (
            f"Expected exactly one poison-pill alert; got: {alert_messages!r}"
        )

    def test_telegram_alert_throttled_1_per_day(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        alta_client_mock: MagicMock,
        notify_admin_mock: AsyncMock,
        patched_cron,
    ) -> None:
        # Same scenario as above — but invoked twice within 24h.
        # Throttle key 'poison_pill' must suppress the second alert.
        for i in range(12):
            _seed_rate_row(
                stub_sb,
                tnved_code=f"99900000{i:02d}",
                country_or_areal=f"C:{700 + i}",
                last_used_at=_stale_iso(8),
                source_fetched_at=_stale_iso(10),
                revalidate_failure_count=3,
                revalidate_failed_at=_yesterday_iso(),
            )

        # First run — alert fires
        r1 = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r1.status_code == 200, r1.text
        # Second run within the same hour — alert MUST be throttled
        r2 = subapp_client.post(
            "/cron/revalidate-rates", headers={"X-Cron-Secret": cron_secret}
        )
        assert r2.status_code == 200, r2.text

        alert_messages = [
            (call.args[0] if call.args else call.kwargs.get("message", ""))
            for call in notify_admin_mock.call_args_list
        ]
        poison_alerts = [
            m for m in alert_messages if "poison-pill" in str(m).lower()
        ]
        assert len(poison_alerts) == 1, (
            f"Expected throttled to 1; got {len(poison_alerts)}: {alert_messages!r}"
        )
