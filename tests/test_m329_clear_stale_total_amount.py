"""
Tests for migration 329: clear stale `kvota.quotes.total_amount` after
all `quote_calculation_results` rows for that quote are deleted.

Context (followup to PR #235, 2026-05-25):
    `quote_calculation_results` is CASCADE-deleted when `quote_items` change,
    but the denormalised `quotes.total_amount` lingered from older calcs,
    producing "пустой" validation Excel exports. PR #235 added a defensive
    gate; this migration removes the root-cause stale data and prevents it
    from accumulating again.

Two-layer test strategy (matches existing migration-tests in this repo):
    1. SQL-contract assertions (file existence, BEGIN/COMMIT, trigger spec)
       run in pure-Python pytest, no DB required — these gate CI.
    2. Live smoke tests against the VPS Postgres (via ssh+docker+psql)
       confirm the trigger actually fires; these are skipped in CI.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import uuid

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")


# ---------------------------------------------------------------------------
# File location helpers
# ---------------------------------------------------------------------------


def _find_migration_329() -> str | None:
    pattern = os.path.join(_MIGRATIONS_DIR, "329_clear_stale_total_amount.sql")
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def _read_migration_329() -> str:
    path = _find_migration_329()
    if path is None:
        pytest.fail(
            "Migration 329 file does not exist. Expected "
            "migrations/329_clear_stale_total_amount.sql"
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# File existence + transactional wrapping
# ---------------------------------------------------------------------------


class TestMigration329Exists:
    def test_migration_file_exists(self) -> None:
        assert _find_migration_329() is not None, (
            "Expected migrations/329_clear_stale_total_amount.sql"
        )

    def test_migration_is_sql_file(self) -> None:
        path = _find_migration_329()
        assert path is not None and path.endswith(".sql"), (
            f"Migration 329 must be .sql, got {path}"
        )


class TestMigration329IsTransactional:
    """Per the m318 lesson, multi-statement migrations must be wrapped in
    BEGIN/COMMIT so apply-migrations.sh can't silently report success on a
    partial application."""

    def test_wrapped_in_begin_commit(self) -> None:
        sql = _read_migration_329()
        assert re.search(r"^\s*BEGIN\s*;", sql, flags=re.IGNORECASE | re.MULTILINE), (
            "Migration 329 must start with BEGIN;"
        )
        assert re.search(r"^\s*COMMIT\s*;", sql, flags=re.IGNORECASE | re.MULTILINE), (
            "Migration 329 must end with COMMIT;"
        )


# ---------------------------------------------------------------------------
# SQL-contract assertions (the actual fix)
# ---------------------------------------------------------------------------


class TestNullableContract:
    """`total_amount` was NOT NULL with default 0 — neither carries the
    semantic "no calculation present". The migration must relax both so
    NULL can mean "no calc"."""

    def test_drops_not_null(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"ALTER\s+TABLE\s+kvota\.quotes\s+ALTER\s+COLUMN\s+total_amount"
            r"\s+DROP\s+NOT\s+NULL",
            sql,
            flags=re.IGNORECASE,
        ), "Migration 329 must DROP NOT NULL on kvota.quotes.total_amount."

    def test_drops_default(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"ALTER\s+TABLE\s+kvota\.quotes\s+ALTER\s+COLUMN\s+total_amount"
            r"\s+DROP\s+DEFAULT",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 329 must DROP DEFAULT on kvota.quotes.total_amount "
            "so fresh rows are NULL (no calc), not 0."
        )


class TestOneTimeCleanup:
    """One-shot UPDATE: every quote with non-null `total_amount` but no row
    in `quote_calculation_results` is cleared to NULL."""

    def test_update_sets_total_amount_to_null(self) -> None:
        sql = _read_migration_329()
        # Match: UPDATE kvota.quotes ... SET total_amount = NULL ...
        # NOT EXISTS (SELECT 1 FROM kvota.quote_calculation_results ...)
        assert re.search(
            r"UPDATE\s+kvota\.quotes.*?SET\s+total_amount\s*=\s*NULL.*?"
            r"NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+kvota\.quote_calculation_results",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        ), (
            "Migration 329 must run one-time UPDATE setting total_amount = NULL "
            "where no quote_calculation_results row exists for that quote."
        )

    def test_update_guards_against_double_null(self) -> None:
        """Tiny optimization: only update rows where total_amount IS NOT NULL.
        Without this guard, the UPDATE rewrites every untouched row in the
        table on every re-run, bloating WAL for no reason."""
        sql = _read_migration_329()
        assert re.search(
            r"UPDATE\s+kvota\.quotes.*?WHERE\s+total_amount\s+IS\s+NOT\s+NULL",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        ), (
            "Migration 329 UPDATE should be guarded by `WHERE total_amount IS NOT NULL` "
            "to avoid rewriting every row needlessly."
        )


class TestTriggerFunction:
    """Trigger function fires AFTER DELETE on quote_calculation_results and
    nullifies quotes.total_amount when no rows remain for that quote."""

    def test_function_exists(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+"
            r"kvota\.clear_quote_total_amount_when_no_calc\s*\(\s*\)\s+"
            r"RETURNS\s+TRIGGER",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 329 must CREATE OR REPLACE FUNCTION "
            "kvota.clear_quote_total_amount_when_no_calc() RETURNS TRIGGER."
        )

    def test_function_checks_for_remaining_rows(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+kvota\.quote_calculation_results"
            r"\s+WHERE\s+quote_id\s*=\s*OLD\.quote_id",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        ), (
            "Trigger function must check NOT EXISTS for any remaining "
            "quote_calculation_results row with OLD.quote_id."
        )

    def test_function_updates_quotes_to_null(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"UPDATE\s+kvota\.quotes\s+SET\s+total_amount\s*=\s*NULL"
            r"\s+WHERE\s+id\s*=\s*OLD\.quote_id",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        ), (
            "Trigger function must UPDATE kvota.quotes SET total_amount = NULL "
            "WHERE id = OLD.quote_id (when no calc rows remain)."
        )

    def test_function_returns_old(self) -> None:
        """AFTER triggers conventionally RETURN OLD for DELETE; the return
        value is ignored but consistency aids readability."""
        sql = _read_migration_329()
        assert re.search(
            r"RETURN\s+OLD\s*;", sql, flags=re.IGNORECASE
        ), "Trigger function should RETURN OLD; for AFTER DELETE convention."


class TestTriggerBinding:
    """The trigger is bound AFTER DELETE on quote_calculation_results,
    FOR EACH ROW. Drops first to allow re-runs."""

    def test_drops_existing_trigger(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"DROP\s+TRIGGER\s+IF\s+EXISTS\s+clear_quote_total_amount_trg\s+"
            r"ON\s+kvota\.quote_calculation_results",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 329 must DROP TRIGGER IF EXISTS clear_quote_total_amount_trg "
            "to be re-runnable."
        )

    def test_creates_trigger_after_delete(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"CREATE\s+TRIGGER\s+clear_quote_total_amount_trg\s+"
            r"AFTER\s+DELETE\s+ON\s+kvota\.quote_calculation_results\s+"
            r"FOR\s+EACH\s+ROW\s+"
            r"EXECUTE\s+FUNCTION\s+kvota\.clear_quote_total_amount_when_no_calc",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 329 must CREATE TRIGGER clear_quote_total_amount_trg "
            "AFTER DELETE ON kvota.quote_calculation_results FOR EACH ROW "
            "EXECUTE FUNCTION kvota.clear_quote_total_amount_when_no_calc."
        )


class TestPostConditionAssertion:
    """Lesson from m318/m319: a multi-statement migration can silently report
    success if a middle statement fails. The migration must verify its
    own post-state."""

    def test_has_post_condition_check(self) -> None:
        sql = _read_migration_329()
        assert re.search(
            r"RAISE\s+EXCEPTION", sql, flags=re.IGNORECASE
        ), (
            "Migration 329 should RAISE EXCEPTION if any stale rows remain "
            "after cleanup, so apply-migrations.sh cannot quietly succeed "
            "on a partial application."
        )


# ---------------------------------------------------------------------------
# Live smoke tests — require ssh access to beget-kvota, skipped in CI.
# ---------------------------------------------------------------------------


SKIP_IF_NO_SSH = os.environ.get("CI") == "true" or not os.path.exists(
    os.path.expanduser("~/.ssh/config")
)


def _psql(sql: str) -> str:
    cmd = [
        "ssh",
        "beget-kvota",
        "docker",
        "exec",
        "supabase-db",
        "psql",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-tAc",
        sql,
    ]
    return subprocess.run(
        cmd, capture_output=True, text=True, check=True
    ).stdout.strip()


class TestMigration329LiveSmoke:
    """Smoke tests against the VPS DB. Skipped in CI."""

    def test_function_exists_after_apply(self) -> None:
        """After apply-migrations.sh runs, the trigger function must exist.

        This test exists to fail loudly if the migration was edited locally
        but never deployed. It's not run on CI (no ssh)."""
        if SKIP_IF_NO_SSH:
            pytest.skip("requires ssh to beget-kvota")
        out = _psql(
            "SELECT proname FROM pg_proc WHERE proname = "
            "'clear_quote_total_amount_when_no_calc';"
        )
        assert out == "clear_quote_total_amount_when_no_calc", (
            f"trigger function missing on prod: {out!r}"
        )

    def test_trigger_exists_after_apply(self) -> None:
        if SKIP_IF_NO_SSH:
            pytest.skip("requires ssh to beget-kvota")
        out = _psql(
            "SELECT tgname FROM pg_trigger WHERE tgname = "
            "'clear_quote_total_amount_trg';"
        )
        assert out == "clear_quote_total_amount_trg", (
            f"trigger missing on prod: {out!r}"
        )

    def test_no_stale_rows_after_apply(self) -> None:
        """After cleanup, zero quotes should have total_amount set without
        a corresponding quote_calculation_results row."""
        if SKIP_IF_NO_SSH:
            pytest.skip("requires ssh to beget-kvota")
        out = _psql(
            "SELECT COUNT(*) FROM kvota.quotes q "
            "WHERE q.total_amount IS NOT NULL "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM kvota.quote_calculation_results qcr "
            "  WHERE qcr.quote_id = q.id"
            ");"
        )
        assert out == "0", f"{out} stale quotes remain after migration"

    def test_total_amount_is_nullable(self) -> None:
        if SKIP_IF_NO_SSH:
            pytest.skip("requires ssh to beget-kvota")
        out = _psql(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema='kvota' AND table_name='quotes' "
            "AND column_name='total_amount';"
        )
        assert out == "YES", f"total_amount must be nullable, got: {out!r}"

    def test_trigger_fires_on_full_delete(self) -> None:
        """End-to-end: pick a quote with a calc row, delete all its calc
        rows, assert total_amount becomes NULL. Reverts state so prod stays
        pristine."""
        if SKIP_IF_NO_SSH:
            pytest.skip("requires ssh to beget-kvota")

        # Find a quote with exactly one calc result row and non-null total_amount.
        probe = _psql(
            """
            SELECT q.id, q.total_amount, qcr.id
            FROM kvota.quotes q
            JOIN kvota.quote_calculation_results qcr ON qcr.quote_id = q.id
            WHERE q.total_amount IS NOT NULL
            GROUP BY q.id, q.total_amount, qcr.id
            HAVING COUNT(qcr.id) OVER (PARTITION BY q.id) = 1
            LIMIT 1;
            """
        )
        if not probe:
            pytest.skip("no eligible quote on prod to smoke-test")

        quote_id, original_total, calc_row_id = probe.split("|")
        uuid.UUID(quote_id)
        uuid.UUID(calc_row_id)

        # Snapshot the calc row so we can restore it.
        snapshot = _psql(
            f"SELECT row_to_json(qcr.*)::text FROM kvota.quote_calculation_results "
            f"qcr WHERE qcr.id = '{calc_row_id}';"
        )

        try:
            _psql(
                f"DELETE FROM kvota.quote_calculation_results "
                f"WHERE id = '{calc_row_id}';"
            )
            after = _psql(
                f"SELECT total_amount IS NULL FROM kvota.quotes "
                f"WHERE id = '{quote_id}';"
            )
            assert after == "t", (
                f"trigger should NULL total_amount after last calc row deleted; "
                f"got {after!r}"
            )
        finally:
            # Best-effort restore: re-insert via JSON snapshot, restore total.
            # Note: this is intentionally lossy on JSONB ordering — the smoke
            # test only verifies the trigger; a re-calc on prod would replace
            # anyway.
            _psql(
                f"UPDATE kvota.quotes SET total_amount = {original_total} "
                f"WHERE id = '{quote_id}';"
            )
            # Try to restore the calc row.
            _psql(
                f"INSERT INTO kvota.quote_calculation_results "
                f"SELECT * FROM json_populate_record("
                f"NULL::kvota.quote_calculation_results, "
                f"'{snapshot}'::json"
                f") ON CONFLICT (id) DO NOTHING;"
            )
