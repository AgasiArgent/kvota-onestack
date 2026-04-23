"""Tests for Task 12 — invoice SLA timers + Telegram pings.

Covers:
- /api/cron/sla-check route registered (via FastAPI sub-app).
- Reminder (deadline - 24h) sent once, second run is a no-op (dedupe).
- Overdue (past deadline) sent once to head-of-<role> users.
- Pre-existing dedupe row blocks a second send.
- Missing CRON_SECRET env / wrong header returns 403/500 without calling Supabase.

The cron handler talks to Supabase and the Telegram bot. We mock both
at the module boundary — `services.database.get_supabase` and
`services.telegram_service.{send_message,get_user_telegram_id}` — so the
tests run fully offline.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Ensure project root importable for `api` and `services` modules.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import cron as cron_module  # noqa: E402
from api.app import api_sub_app  # noqa: E402


# ----------------------------------------------------------------------------
# Stub Supabase client
# ----------------------------------------------------------------------------


class _StubQuery:
    """Minimal chainable query emulating supabase-py's PostgREST builder.

    Supports the subset used by api.cron.cron_sla_check:
      table(...).select(...).or_(...).execute()
      table(...).select(...).eq(...).eq(...).execute()
      table(...).insert({...}).execute()
    """

    def __init__(self, client: "_StubSupabase", table_name: str) -> None:
        self._client = client
        self._table = table_name
        self._filters: list[tuple[str, Any, Any]] = []
        self._insert_payload: dict | None = None

    def select(self, *_args: Any, **_kwargs: Any) -> "_StubQuery":
        return self

    def eq(self, col: str, val: Any) -> "_StubQuery":
        self._filters.append(("eq", col, val))
        return self

    def or_(self, _expr: str) -> "_StubQuery":
        # We don't parse the or_ expression — rely on the in-memory rows we
        # seeded. `cron_sla_check` applies its own completion filter in Python.
        return self

    def insert(self, payload: dict) -> "_StubQuery":
        self._insert_payload = payload
        return self

    # --- terminal -----------------------------------------------------------

    def execute(self) -> Any:
        if self._insert_payload is not None:
            return self._do_insert(self._insert_payload)

        rows = self._client.tables.get(self._table, [])
        for op, col, val in self._filters:
            if op == "eq":
                rows = [r for r in rows if r.get(col) == val]
        return MagicMock(data=list(rows))

    def _do_insert(self, payload: dict) -> Any:
        if self._table == "invoice_sla_notifications_sent":
            key = (payload["invoice_id"], payload["kind"])
            if key in self._client.sent_keys:
                raise RuntimeError(
                    'duplicate key value violates unique constraint '
                    '"invoice_sla_notifications_sent_invoice_id_kind_key" (23505)'
                )
            self._client.sent_keys.add(key)
            self._client.tables.setdefault(self._table, []).append(
                {**payload, "sent_at": datetime.now(timezone.utc).isoformat()}
            )
            return MagicMock(data=[payload])
        self._client.tables.setdefault(self._table, []).append(payload)
        return MagicMock(data=[payload])


class _StubSupabase:
    """Tiny Supabase stub keyed by table name."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {}
        self.sent_keys: set[tuple[str, str]] = set()

    def table(self, name: str) -> _StubQuery:
        return _StubQuery(self, name)


# ----------------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------------


@pytest.fixture
def subapp_client() -> TestClient:
    return TestClient(api_sub_app)


@pytest.fixture
def cron_secret() -> str:
    return "test-cron-secret-xyz"


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
def telegram_send() -> AsyncMock:
    """AsyncMock recording each send_message call. Returns a truthy message_id."""
    mock = AsyncMock(return_value=123456)
    return mock


@pytest.fixture
def telegram_get_id() -> AsyncMock:
    """AsyncMock returning a valid telegram_id for any user."""
    mock = AsyncMock(return_value=987654321)
    return mock


@pytest.fixture
def patched_cron(
    stub_sb: _StubSupabase,
    telegram_send: AsyncMock,
    telegram_get_id: AsyncMock,
):
    """Patch Supabase + Telegram at the modules the cron handler imports from."""
    with patch.object(cron_module, "get_supabase", return_value=stub_sb), \
         patch("services.telegram_service.send_message", telegram_send), \
         patch("services.telegram_service.get_user_telegram_id", telegram_get_id):
        yield


# ----------------------------------------------------------------------------
# Seed helpers
# ----------------------------------------------------------------------------


ORG_ID = "11111111-1111-1111-1111-111111111111"
QUOTE_ID = "22222222-2222-2222-2222-222222222222"
INVOICE_ID = "33333333-3333-3333-3333-333333333333"
ASSIGNED_LOGISTICS_USER = "44444444-4444-4444-4444-444444444444"
HEAD_LOGISTICS_USER = "55555555-5555-5555-5555-555555555555"
HEAD_LOGISTICS_ROLE_ID = "66666666-6666-6666-6666-666666666666"
HEAD_CUSTOMS_ROLE_ID = "77777777-7777-7777-7777-777777777777"


def _seed_base(sb: _StubSupabase) -> None:
    """Seed quotes/roles/user_roles common to all tests."""
    sb.tables["quotes"] = [{"id": QUOTE_ID, "organization_id": ORG_ID}]
    sb.tables["roles"] = [
        {"id": HEAD_LOGISTICS_ROLE_ID, "slug": "head_of_logistics"},
        {"id": HEAD_CUSTOMS_ROLE_ID, "slug": "head_of_customs"},
    ]
    sb.tables["user_roles"] = [
        {
            "user_id": HEAD_LOGISTICS_USER,
            "organization_id": ORG_ID,
            "role_id": HEAD_LOGISTICS_ROLE_ID,
        },
    ]


def _seed_invoice(
    sb: _StubSupabase,
    *,
    logistics_deadline_at: datetime | None = None,
    logistics_completed_at: datetime | None = None,
    customs_deadline_at: datetime | None = None,
    customs_completed_at: datetime | None = None,
) -> None:
    sb.tables["invoices"] = [
        {
            "id": INVOICE_ID,
            "quote_id": QUOTE_ID,
            "invoice_number": "INV-001",
            "logistics_deadline_at": (
                logistics_deadline_at.isoformat() if logistics_deadline_at else None
            ),
            "logistics_completed_at": (
                logistics_completed_at.isoformat() if logistics_completed_at else None
            ),
            "assigned_logistics_user": ASSIGNED_LOGISTICS_USER,
            "customs_deadline_at": (
                customs_deadline_at.isoformat() if customs_deadline_at else None
            ),
            "customs_completed_at": (
                customs_completed_at.isoformat() if customs_completed_at else None
            ),
            "assigned_customs_user": None,
        }
    ]


# ----------------------------------------------------------------------------
# Route registration
# ----------------------------------------------------------------------------


class TestSlaCheckRouteRegistered:
    def test_post_sla_check_registered(self, subapp_client: TestClient) -> None:
        response = subapp_client.post("/cron/sla-check")
        assert response.status_code != 404, (
            f"Route not registered: POST /cron/sla-check returned 404. "
            f"Body: {response.text[:200]}"
        )

    def test_schema_includes_sla_check(self, subapp_client: TestClient) -> None:
        response = subapp_client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json().get("paths", {})
        assert "/cron/sla-check" in paths
        assert "post" in paths["/cron/sla-check"]


# ----------------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------------


class TestSlaCheckAuth:
    def test_missing_secret_returns_403(
        self, subapp_client: TestClient, patched_cron
    ) -> None:
        response = subapp_client.post("/cron/sla-check")
        assert response.status_code == 403

    def test_wrong_secret_returns_403(
        self, subapp_client: TestClient, patched_cron
    ) -> None:
        response = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": "wrong"}
        )
        assert response.status_code == 403


# ----------------------------------------------------------------------------
# Business logic
# ----------------------------------------------------------------------------


class TestSlaCheckReminder:
    """At T = deadline - 12h (inside the 24h window) we expect one reminder."""

    def test_reminder_sent_once_then_deduped(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        telegram_send: AsyncMock,
        patched_cron,
    ) -> None:
        _seed_base(stub_sb)
        now = datetime.now(timezone.utc)
        _seed_invoice(stub_sb, logistics_deadline_at=now + timedelta(hours=12))

        # First run — should send exactly one reminder to the assignee.
        r1 = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": cron_secret}
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["success"] is True
        assert body1["data"]["sent"]["logistics_reminder"] == 1
        assert body1["data"]["sent"]["logistics_overdue"] == 0
        assert telegram_send.await_count == 1
        assert (INVOICE_ID, "logistics_reminder") in stub_sb.sent_keys

        # Second run — dedupe row blocks resend.
        telegram_send.reset_mock()
        r2 = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": cron_secret}
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["data"]["sent"]["logistics_reminder"] == 0
        assert telegram_send.await_count == 0


class TestSlaCheckOverdue:
    """Past deadline → one overdue ping to head_of_logistics users."""

    def test_overdue_sent_once_to_head_role(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        telegram_send: AsyncMock,
        telegram_get_id: AsyncMock,
        patched_cron,
    ) -> None:
        _seed_base(stub_sb)
        now = datetime.now(timezone.utc)
        _seed_invoice(stub_sb, logistics_deadline_at=now - timedelta(hours=1))

        r = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["data"]["sent"]["logistics_overdue"] == 1
        # No reminder is backfilled once we're past the deadline.
        assert body["data"]["sent"]["logistics_reminder"] == 0
        # The recipient passed to get_user_telegram_id must be the head user.
        telegram_get_id.assert_awaited_with(HEAD_LOGISTICS_USER)
        assert telegram_send.await_count == 1
        assert (INVOICE_ID, "logistics_overdue") in stub_sb.sent_keys


class TestSlaCheckPreExistingDedupe:
    """If a dedupe row already exists for (invoice, kind), nothing is sent."""

    def test_skips_when_row_already_present(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        telegram_send: AsyncMock,
        patched_cron,
    ) -> None:
        _seed_base(stub_sb)
        now = datetime.now(timezone.utc)
        _seed_invoice(stub_sb, logistics_deadline_at=now + timedelta(hours=12))
        # Pre-populate dedupe ledger.
        stub_sb.sent_keys.add((INVOICE_ID, "logistics_reminder"))
        stub_sb.tables["invoice_sla_notifications_sent"] = [
            {"invoice_id": INVOICE_ID, "kind": "logistics_reminder"}
        ]

        r = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200
        assert r.json()["data"]["sent"]["logistics_reminder"] == 0
        assert telegram_send.await_count == 0


class TestSlaCheckCompleted:
    """Completed side is ignored entirely (no reminder, no overdue)."""

    def test_completed_logistics_ignored(
        self,
        subapp_client: TestClient,
        cron_secret: str,
        stub_sb: _StubSupabase,
        telegram_send: AsyncMock,
        patched_cron,
    ) -> None:
        _seed_base(stub_sb)
        now = datetime.now(timezone.utc)
        _seed_invoice(
            stub_sb,
            logistics_deadline_at=now - timedelta(hours=1),
            logistics_completed_at=now - timedelta(hours=2),
        )

        r = subapp_client.post(
            "/cron/sla-check", headers={"X-Cron-Secret": cron_secret}
        )
        assert r.status_code == 200
        sent = r.json()["data"]["sent"]
        assert sent == {
            "logistics_reminder": 0,
            "logistics_overdue": 0,
            "customs_reminder": 0,
            "customs_overdue": 0,
        }
        assert telegram_send.await_count == 0
