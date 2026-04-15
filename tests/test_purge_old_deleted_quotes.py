"""Tests for scripts/purge_old_deleted_quotes.py.

Covers REQ-008 acceptance criteria for the soft-delete hard-purge cron.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest

from scripts import purge_old_deleted_quotes as purge


# --------------------------------------------------------------------------- #
# Helpers — a light fake of the Supabase query-builder that records calls.
# --------------------------------------------------------------------------- #

class _Response:
    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []


class _FakeQuery:
    """Fluent query-builder that records method calls on a shared call_log."""

    def __init__(
        self,
        table: str,
        call_log: list[tuple[str, str]],
        fetch_map: dict[tuple[str, str, str], list[dict[str, Any]]],
        delete_returns: dict[str, list[dict[str, Any]]],
    ) -> None:
        self._table = table
        self._op = "select"  # select|delete
        self._filter: tuple[str, str, Any] | None = None  # (op, col, value)
        self._call_log = call_log
        self._fetch_map = fetch_map
        self._delete_returns = delete_returns
        self._order_applied = False
        self._limit_applied: int | None = None

    # --- builder methods --------------------------------------------------- #
    def select(self, _cols: str = "*") -> "_FakeQuery":
        self._op = "select"
        return self

    def delete(self) -> "_FakeQuery":
        self._op = "delete"
        return self

    def eq(self, col: str, val: Any) -> "_FakeQuery":
        self._filter = ("eq", col, val)
        return self

    def in_(self, col: str, vals: list[Any]) -> "_FakeQuery":
        self._filter = ("in", col, tuple(vals))
        return self

    def lt(self, col: str, val: Any) -> "_FakeQuery":
        self._filter = ("lt", col, val)
        return self

    def order(self, _col: str, desc: bool = False) -> "_FakeQuery":  # noqa: ARG002
        self._order_applied = True
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit_applied = n
        return self

    # --- terminal ---------------------------------------------------------- #
    def execute(self) -> _Response:
        if self._op == "delete":
            self._call_log.append(("delete", self._table))
            data = self._delete_returns.get(self._table, [{"_": 1}])
            return _Response(data)

        # select
        self._call_log.append(("select", self._table))
        if self._filter is None:
            return _Response([])
        op, col, val = self._filter
        key = (self._table, op, col)
        rows = self._fetch_map.get(key)
        if rows is None:
            return _Response([])
        # `lt` simulation: rows are pre-filtered in the fixture
        # honor limit
        if self._limit_applied is not None:
            rows = rows[: self._limit_applied]
        return _Response(list(rows))


class _FakeRpc:
    """Captures supabase.rpc(name, params).execute() calls."""

    def __init__(
        self,
        name: str,
        params: dict[str, Any],
        call_log: list[tuple[str, str]],
        rpc_returns: dict[str, list[dict[str, Any]]],
        rpc_raises: dict[str, Exception],
    ) -> None:
        self._name = name
        self._params = params
        self._call_log = call_log
        self._rpc_returns = rpc_returns
        self._rpc_raises = rpc_raises

    def execute(self) -> _Response:
        self._call_log.append(("rpc", self._name))
        if self._name in self._rpc_raises:
            raise self._rpc_raises[self._name]
        data = self._rpc_returns.get(
            self._name,
            [{"deals_deleted": 1, "specs_deleted": 1, "quotes_deleted": 1}],
        )
        return _Response(data)


class _FakeSupabase:
    def __init__(
        self,
        fetch_map: dict[tuple[str, str, str], list[dict[str, Any]]] | None = None,
        delete_returns: dict[str, list[dict[str, Any]]] | None = None,
        rpc_returns: dict[str, list[dict[str, Any]]] | None = None,
        rpc_raises: dict[str, Exception] | None = None,
    ) -> None:
        self.call_log: list[tuple[str, str]] = []
        self._fetch_map = fetch_map or {}
        self._delete_returns = delete_returns or {}
        self._rpc_returns = rpc_returns or {}
        self._rpc_raises = rpc_raises or {}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(
            name, self.call_log, self._fetch_map, self._delete_returns
        )

    def rpc(self, name: str, params: dict[str, Any]) -> _FakeRpc:
        return _FakeRpc(
            name, params, self.call_log, self._rpc_returns, self._rpc_raises
        )


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

@pytest.mark.unit
def test_dry_run_makes_no_changes(caplog: pytest.LogCaptureFixture) -> None:
    quote = {
        "id": "q1",
        "idn_quote": "Q-1",
        "customer_id": "c1",
        "deleted_at": _iso_days_ago(400),
    }
    fake = _FakeSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): [quote],
            ("specifications", "eq", "quote_id"): [{"id": "s1"}],
            ("deals", "in", "specification_id"): [{"id": "d1"}],
        }
    )
    with patch.object(purge, "get_supabase", return_value=fake), caplog.at_level(
        logging.INFO, logger="purge_old_deleted_quotes"
    ):
        rc = purge.run(["--dry-run"])

    assert rc == 0
    # Zero delete calls in dry-run
    assert not any(op == "delete" for op, _ in fake.call_log)
    # Log formatted as DRY-RUN
    assert any("[DRY-RUN]" in rec.message for rec in caplog.records)


@pytest.mark.unit
def test_purges_quotes_older_than_retention() -> None:
    # Fixture: cutoff at 365d — fetch only returns rows older than cutoff.
    old_a = {"id": "qA", "idn_quote": "Q-A", "deleted_at": _iso_days_ago(400)}
    old_b = {"id": "qB", "idn_quote": "Q-B", "deleted_at": _iso_days_ago(500)}
    fake = _FakeSupabase(
        fetch_map={("quotes", "lt", "deleted_at"): [old_a, old_b]}
    )
    with patch.object(purge, "get_supabase", return_value=fake):
        rc = purge.run([])

    assert rc == 0
    # One rpc per quote — hard_purge_quote wraps the 3 deletes atomically.
    rpc_calls = [entry for entry in fake.call_log if entry == ("rpc", "hard_purge_quote")]
    assert len(rpc_calls) == 2


@pytest.mark.unit
def test_real_run_invokes_hard_purge_quote_rpc() -> None:
    """Verify the real-run path calls kvota.hard_purge_quote once per quote —
    the PL/pgSQL function owns the transactional delete order internally
    (migration 281), so tests assert the rpc is invoked, not individual DELETEs."""
    quote = {"id": "q1", "idn_quote": "Q-1", "deleted_at": _iso_days_ago(400)}
    fake = _FakeSupabase(
        fetch_map={("quotes", "lt", "deleted_at"): [quote]}
    )
    with patch.object(purge, "get_supabase", return_value=fake):
        rc = purge.run([])

    assert rc == 0
    # Exactly one rpc call, zero raw DELETE calls.
    rpc_calls = [e for e in fake.call_log if e[0] == "rpc"]
    delete_calls = [e for e in fake.call_log if e[0] == "delete"]
    assert rpc_calls == [("rpc", "hard_purge_quote")], rpc_calls
    assert delete_calls == [], "no raw DELETEs — purge must go through the rpc"


@pytest.mark.unit
def test_skip_missing_row_no_error(caplog: pytest.LogCaptureFixture) -> None:
    """If a quote row is gone by the time we purge, next quote still processes.
    Triggered by the rpc returning quotes_deleted=0."""
    a = {"id": "qA", "idn_quote": "Q-A", "deleted_at": _iso_days_ago(400)}
    b = {"id": "qB", "idn_quote": "Q-B", "deleted_at": _iso_days_ago(500)}
    fake = _FakeSupabase(
        fetch_map={("quotes", "lt", "deleted_at"): [a, b]},
        # rpc reports 0 rows affected for BOTH — loop must keep going and log [SKIP].
        rpc_returns={
            "hard_purge_quote": [
                {"deals_deleted": 0, "specs_deleted": 0, "quotes_deleted": 0}
            ]
        },
    )
    with patch.object(purge, "get_supabase", return_value=fake), caplog.at_level(
        logging.INFO, logger="purge_old_deleted_quotes"
    ):
        rc = purge.run([])

    assert rc == 0
    skip_messages = [r for r in caplog.records if "[SKIP]" in r.message]
    assert len(skip_messages) == 2


@pytest.mark.unit
def test_retention_under_30_days_refuses(caplog: pytest.LogCaptureFixture) -> None:
    fake = _FakeSupabase()
    with patch.object(purge, "get_supabase", return_value=fake), caplog.at_level(
        logging.ERROR, logger="purge_old_deleted_quotes"
    ):
        rc = purge.run(["--days", "5"])

    assert rc == 1
    # No queries should have been issued.
    assert fake.call_log == []
    assert any("refusing to run" in r.message for r in caplog.records)


@pytest.mark.unit
def test_limit_caps_batch_size() -> None:
    rows = [
        {"id": f"q{i}", "idn_quote": f"Q-{i}", "deleted_at": _iso_days_ago(400 + i)}
        for i in range(10)
    ]
    fake = _FakeSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): rows,
            ("specifications", "eq", "quote_id"): [],
        }
    )
    with patch.object(purge, "get_supabase", return_value=fake):
        rc = purge.run(["--limit", "3", "--dry-run"])

    assert rc == 0
    # In dry-run we fetch-once, then for each returned quote do 1 select on
    # specifications. Limit applies at fetch time. The fake _FakeQuery honors
    # .limit() and slices accordingly.
    spec_selects = [
        entry for entry in fake.call_log if entry == ("select", "specifications")
    ]
    assert len(spec_selects) == 3


@pytest.mark.unit
def test_summary_counts_accurate(caplog: pytest.LogCaptureFixture) -> None:
    rows = [
        {"id": "q1", "idn_quote": "Q-1", "deleted_at": _iso_days_ago(400)},
        {"id": "q2", "idn_quote": "Q-2", "deleted_at": _iso_days_ago(410)},
        {"id": "q3", "idn_quote": "Q-3", "deleted_at": _iso_days_ago(420)},
    ]
    fake = _FakeSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): rows,
            ("specifications", "eq", "quote_id"): [],
        }
    )
    with patch.object(purge, "get_supabase", return_value=fake), caplog.at_level(
        logging.INFO, logger="purge_old_deleted_quotes"
    ):
        rc = purge.run(["--dry-run"])

    assert rc == 0
    summary = [r for r in caplog.records if "purge complete" in r.message]
    assert len(summary) == 1
    assert "3 quote(s) purged" in summary[0].message


@pytest.mark.unit
def test_unexpected_error_returns_exit_code_1(caplog: pytest.LogCaptureFixture) -> None:
    """main() should catch unexpected exceptions and return 1."""

    def _boom() -> Any:
        raise RuntimeError("db down")

    with patch.object(purge, "get_supabase", side_effect=_boom), caplog.at_level(
        logging.ERROR, logger="purge_old_deleted_quotes"
    ):
        rc = purge.main([])

    assert rc == 1
    assert any("unexpected error" in r.message for r in caplog.records)


@pytest.mark.unit
def test_fk_restrict_violation_aborts_batch_with_exit_1(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If the rpc raises (e.g., FK RESTRICT inside hard_purge_quote because of
    unexpected related-row state), main() must log the exception and exit
    non-zero rather than silently swallowing — no partial purge undetected."""

    quote = {"id": "qX", "idn_quote": "Q-X", "deleted_at": _iso_days_ago(400)}
    fake = _FakeSupabase(
        fetch_map={("quotes", "lt", "deleted_at"): [quote]},
        rpc_raises={
            "hard_purge_quote": RuntimeError(
                'APIError: update or delete on table "quotes" violates '
                'foreign key constraint "deals_quote_id_fkey"'
            ),
        },
    )
    with patch.object(purge, "get_supabase", return_value=fake), caplog.at_level(
        logging.ERROR, logger="purge_old_deleted_quotes"
    ):
        rc = purge.main([])

    assert rc == 1, "FK violation must propagate to exit code 1"
    assert any(
        "unexpected error" in r.message for r in caplog.records
    ), "error must be logged via logger.exception"
    # The error message includes the FK name so an operator knows what failed.
    assert any(
        "deals_quote_id_fkey" in (r.exc_text or "") for r in caplog.records
    ), "the FK constraint name must appear in the traceback for debuggability"
