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


class _FakeSupabase:
    def __init__(
        self,
        fetch_map: dict[tuple[str, str, str], list[dict[str, Any]]] | None = None,
        delete_returns: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.call_log: list[tuple[str, str]] = []
        self._fetch_map = fetch_map or {}
        self._delete_returns = delete_returns or {}

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(
            name, self.call_log, self._fetch_map, self._delete_returns
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
        fetch_map={
            ("quotes", "lt", "deleted_at"): [old_a, old_b],
            # Both have no specs — simplifies delete-order test elsewhere.
            ("specifications", "eq", "quote_id"): [],
        }
    )
    with patch.object(purge, "get_supabase", return_value=fake):
        rc = purge.run([])

    assert rc == 0
    # Two quote deletes issued.
    quote_deletes = [entry for entry in fake.call_log if entry == ("delete", "quotes")]
    assert len(quote_deletes) == 2


@pytest.mark.unit
def test_delete_order_is_deal_then_spec_then_quote() -> None:
    """Verify per-quote delete order: deals -> specifications -> quotes."""
    quote = {"id": "q1", "idn_quote": "Q-1", "deleted_at": _iso_days_ago(400)}
    fake = _FakeSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): [quote],
            ("specifications", "eq", "quote_id"): [{"id": "s1"}, {"id": "s2"}],
        }
    )
    with patch.object(purge, "get_supabase", return_value=fake):
        rc = purge.run([])

    assert rc == 0
    delete_sequence = [tbl for op, tbl in fake.call_log if op == "delete"]
    assert delete_sequence == ["deals", "specifications", "quotes"], delete_sequence


@pytest.mark.unit
def test_skip_missing_row_no_error(caplog: pytest.LogCaptureFixture) -> None:
    """If a quote row is gone by the time we delete, next quote still processes."""
    a = {"id": "qA", "idn_quote": "Q-A", "deleted_at": _iso_days_ago(400)}
    b = {"id": "qB", "idn_quote": "Q-B", "deleted_at": _iso_days_ago(500)}
    fake = _FakeSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): [a, b],
            ("specifications", "eq", "quote_id"): [],
        },
        # quotes delete returns empty list for BOTH — but loop must keep going.
        delete_returns={"quotes": []},
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
    """If a delete raises (e.g., FK RESTRICT on deals.quote_id because a deal
    orphan snuck in), main() should log the exception and exit non-zero rather
    than silently swallowing — no partial purge should go undetected."""

    class _RestrictQuery(_FakeQuery):
        def execute(self) -> _Response:  # type: ignore[override]
            # Raise on the first delete call, pass-through on selects.
            if self._op == "delete" and self._table == "quotes":
                raise RuntimeError(
                    'APIError: update or delete on table "quotes" violates '
                    'foreign key constraint "deals_quote_id_fkey"'
                )
            return super().execute()

    class _RestrictSupabase(_FakeSupabase):
        def table(self, name: str) -> _FakeQuery:  # type: ignore[override]
            return _RestrictQuery(
                name, self.call_log, self._fetch_map, self._delete_returns
            )

    quote = {"id": "qX", "idn_quote": "Q-X", "deleted_at": _iso_days_ago(400)}
    fake = _RestrictSupabase(
        fetch_map={
            ("quotes", "lt", "deleted_at"): [quote],
            ("specifications", "eq", "quote_id"): [],
        },
        # deals/specs deletes return empty (no rows matched to delete) — that's
        # fine. The quote delete is the one that raises.
        delete_returns={"deals": [], "specifications": [], "quotes": []},
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
