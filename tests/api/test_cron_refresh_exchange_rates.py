"""Tests for ``POST /api/cron/refresh-exchange-rates``.

Restores the CBR (ЦБ РФ) FX feed the decommissioned lisa backend used to
maintain. Covers:

- ``X-Cron-Secret`` header validation (missing → 403, wrong → 403).
- Valute → row mapping: rate = Value / Nominal, to_currency='RUB',
  source='cbr' (including a Nominal>1 case where the per-unit rate divides).
- RUB->RUB=1.0 identity row is present (matches the live data).
- The write is an UPSERT with on_conflict targeting the UNIQUE
  (from_currency, to_currency, fetched_at) — NOT a plain insert.
- A CBR fetch failure returns the error envelope with a non-2xx status and
  performs NO DB write (no silent swallow).

Mocks the HTTP fetch (``httpx.AsyncClient``) and the Supabase client so the
suite never hits the real CBR endpoint or DB. Mirrors the stub style of
``tests/api/test_cron_revalidate.py``.
"""
from __future__ import annotations

import os
import sys
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


# ---------------------------------------------------------------------------
# Stub Supabase client — records upsert payload + on_conflict, and asserts
# the handler never falls back to a plain insert.
# ---------------------------------------------------------------------------


class _StubQuery:
    def __init__(self, client: "_StubSupabase", table_name: str) -> None:
        self._client = client
        self._table = table_name
        self._upsert_payload: list[dict] | None = None
        self._upsert_on_conflict: str | None = None
        self._insert_payload: Any = None

    def upsert(
        self, payload: list[dict], *, on_conflict: str | None = None
    ) -> "_StubQuery":
        self._upsert_payload = payload
        self._upsert_on_conflict = on_conflict
        return self

    def insert(self, payload: Any) -> "_StubQuery":
        # Should never be used by the refresh handler — record so the test
        # can assert it didn't happen.
        self._insert_payload = payload
        return self

    def execute(self) -> Any:
        if self._upsert_payload is not None:
            self._client.upsert_calls.append(
                {
                    "table": self._table,
                    "payload": self._upsert_payload,
                    "on_conflict": self._upsert_on_conflict,
                }
            )
            return MagicMock(data=self._upsert_payload)
        if self._insert_payload is not None:
            self._client.insert_calls.append(
                {"table": self._table, "payload": self._insert_payload}
            )
            return MagicMock(data=self._insert_payload)
        return MagicMock(data=[])


class _StubSupabase:
    def __init__(self) -> None:
        self.upsert_calls: list[dict] = []
        self.insert_calls: list[dict] = []

    def table(self, name: str) -> _StubQuery:
        return _StubQuery(self, name)


# ---------------------------------------------------------------------------
# Fake CBR daily_json.js payload — small dump with a Nominal>1 case.
# ---------------------------------------------------------------------------


def _fake_cbr_payload() -> dict[str, Any]:
    return {
        "Date": "2026-05-29T11:30:00+03:00",
        "PreviousDate": "2026-05-28T11:30:00+03:00",
        "Valute": {
            "USD": {"CharCode": "USD", "Nominal": 1, "Value": 71.3715},
            "EUR": {"CharCode": "EUR", "Nominal": 1, "Value": 80.5},
            # Nominal>1: CBR publishes JPY per 100 units → per-unit rate divides.
            "JPY": {"CharCode": "JPY", "Nominal": 100, "Value": 44.7246},
        },
    }


def _mock_httpx_client(payload: dict[str, Any] | None) -> MagicMock:
    """Build a MagicMock standing in for ``httpx.AsyncClient`` used as an
    async context manager. ``get`` returns a response whose ``.json()``
    yields ``payload``; ``raise_for_status`` is a no-op.
    """
    response = MagicMock()
    response.raise_for_status = MagicMock(return_value=None)
    response.json = MagicMock(return_value=payload)

    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=ctx)
    return factory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    return TestClient(api_sub_app)


@pytest.fixture
def cron_secret() -> str:
    return "test-cron-secret-refresh-fx"


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


# ===========================================================================
# Route registration
# ===========================================================================


class TestRouteRegistered:
    def test_post_refresh_exchange_rates_registered(
        self, subapp_client: TestClient
    ) -> None:
        # Without X-Cron-Secret → 403 from the handler. 404 would mean the
        # route was never registered.
        response = subapp_client.post("/cron/refresh-exchange-rates")
        assert response.status_code != 404, (
            "Route not registered: POST /cron/refresh-exchange-rates "
            f"returned 404. Body: {response.text[:200]}"
        )

    def test_schema_includes_refresh_exchange_rates(
        self, subapp_client: TestClient
    ) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        assert "/cron/refresh-exchange-rates" in paths
        assert "post" in paths["/cron/refresh-exchange-rates"]


# ===========================================================================
# Auth
# ===========================================================================


class TestAuth:
    def test_missing_secret_returns_403(
        self, subapp_client: TestClient, stub_sb: _StubSupabase
    ) -> None:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client(_fake_cbr_payload()),
             ):
            response = subapp_client.post("/cron/refresh-exchange-rates")
        assert response.status_code == 403
        # Auth gate must short-circuit BEFORE any DB write.
        assert stub_sb.upsert_calls == []

    def test_wrong_secret_returns_403(
        self, subapp_client: TestClient, stub_sb: _StubSupabase
    ) -> None:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client(_fake_cbr_payload()),
             ):
            response = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": "wrong"},
            )
        assert response.status_code == 403
        assert stub_sb.upsert_calls == []


# ===========================================================================
# Valute → row mapping + upsert behaviour
# ===========================================================================


class TestRowMapping:
    def test_maps_valutes_with_nominal_and_includes_rub_identity(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
    ) -> None:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client(_fake_cbr_payload()),
             ):
            r = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        # 3 valutes + RUB identity = 4 rows
        assert body["data"]["rows_written"] == 4
        assert body["data"]["currencies"] == 4

        assert len(stub_sb.upsert_calls) == 1
        call = stub_sb.upsert_calls[0]
        assert call["table"] == "exchange_rates"
        rows = {row["from_currency"]: row for row in call["payload"]}

        # Every row targets RUB with source 'cbr'.
        for row in call["payload"]:
            assert row["to_currency"] == "RUB"
            assert row["source"] == "cbr"

        # Nominal=1 → rate == Value
        assert rows["USD"]["rate"] == pytest.approx(71.3715)
        assert rows["EUR"]["rate"] == pytest.approx(80.5)
        # Nominal=100 → rate == Value / 100
        assert rows["JPY"]["rate"] == pytest.approx(0.447246)
        # RUB identity row present and equal to 1.0
        assert "RUB" in rows
        assert rows["RUB"]["rate"] == pytest.approx(1.0)

    def test_write_is_upsert_with_on_conflict_not_plain_insert(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
    ) -> None:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client(_fake_cbr_payload()),
             ):
            r = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 200, r.text
        # Exactly one upsert, zero plain inserts.
        assert len(stub_sb.upsert_calls) == 1
        assert stub_sb.insert_calls == []
        # on_conflict must target the UNIQUE constraint columns.
        assert (
            stub_sb.upsert_calls[0]["on_conflict"]
            == "from_currency,to_currency,fetched_at"
        )

    def test_fetched_at_derived_from_cbr_date(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
    ) -> None:
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client(_fake_cbr_payload()),
             ):
            r = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 200, r.text
        fetched = {row["fetched_at"] for row in stub_sb.upsert_calls[0]["payload"]}
        # All rows share one fetched_at, derived from the CBR Date (tz stripped
        # for the naive timestamp column).
        assert fetched == {"2026-05-29T11:30:00"}


# ===========================================================================
# Failure modes — no silent swallow
# ===========================================================================


class TestFetchFailure:
    def test_fetch_failure_returns_error_envelope_no_write(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
    ) -> None:
        # httpx.AsyncClient(...).__aenter__().get(...) raises a transport error.
        failing_client = MagicMock()
        failing_client.get = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=failing_client)
        ctx.__aexit__ = AsyncMock(return_value=None)
        factory = MagicMock(return_value=ctx)

        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(cron_module.httpx, "AsyncClient", factory):
            r = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 502, r.text
        body = r.json()
        assert body["success"] is False
        assert body["error"]["code"] == "CBR_FETCH_FAILED"
        assert body["error"]["message"]  # non-empty context
        # No DB write attempted on fetch failure.
        assert stub_sb.upsert_calls == []
        assert stub_sb.insert_calls == []

    def test_missing_valute_returns_parse_error_no_write(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
    ) -> None:
        # Payload without a "Valute" dict → CBR_PARSE_FAILED.
        with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
             patch.object(
                 cron_module.httpx,
                 "AsyncClient",
                 _mock_httpx_client({"Date": "2026-05-29T11:30:00+03:00"}),
             ):
            r = subapp_client.post(
                "/cron/refresh-exchange-rates",
                headers={"X-Cron-Secret": cron_secret},
            )

        assert r.status_code == 502, r.text
        body = r.json()
        assert body["success"] is False
        assert body["error"]["code"] == "CBR_PARSE_FAILED"
        assert stub_sb.upsert_calls == []
