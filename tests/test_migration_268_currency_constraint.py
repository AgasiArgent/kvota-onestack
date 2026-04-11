"""
Regression tests for migration 268 — loosened currency CHECK constraint on
kvota.deal_logistics_expenses.

Migration 268 replaced the hardcoded currency allowlist with a format-only
regex check (`currency ~ '^[A-Z]{3}$'`). These tests assert that:

1. Inserts with the new currencies (AED, KZT, JPY, GBP, CHF) succeed
2. Inserts with invalid formats (lowercase, wrong length, empty) fail
3. The constraint name is preserved (`deal_logistics_expenses_currency_check`)

These tests require a real database connection — no in-memory fixture can
exercise a CHECK constraint. When `DATABASE_URL` is not configured (e.g. CI
without DB access), the entire module is skipped with a clear message.
"""

import os
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Connection helper — skips the whole file if no DB is available.
# ---------------------------------------------------------------------------


def _get_db_connection():
    """Open a direct psycopg connection for constraint-level tests.

    Reads DATABASE_URL (preferred) or SUPABASE_DB_URL. psycopg2 or psycopg
    must be installed. Skips gracefully on any setup failure.
    """
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 268 "
            "constraint tests (require direct DB access)."
        )

    try:
        import psycopg  # psycopg v3
        return psycopg.connect(dsn)
    except ImportError:
        pass

    try:
        import psycopg2  # psycopg v2
        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip(
            "Neither psycopg nor psycopg2 is installed — skipping migration "
            "268 constraint tests."
        )


@pytest.fixture
def db_conn():
    """Yield a live DB connection and roll back after each test.

    Rollback-only test isolation: we never commit, so no data leaks between
    tests or into production-like environments.
    """
    conn = _get_db_connection()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


# ---------------------------------------------------------------------------
# Fixture data — a minimal valid parent row set for foreign keys.
# ---------------------------------------------------------------------------


def _fetch_existing_ids(conn):
    """Fetch one existing (deal_id, logistics_stage_id, organization_id) triple.

    We piggy-back on existing rows rather than creating new ones because
    deal_logistics_expenses has FKs to deals, logistics_stages, and organizations.
    Creating all those from scratch would test far more than the constraint.
    If the dev DB has no existing stages with linked deals, skip.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ls.deal_id, ls.id, d.organization_id
        FROM kvota.logistics_stages ls
        JOIN kvota.deals d ON d.id = ls.deal_id
        LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        pytest.skip(
            "No existing logistics_stages linked to deals — cannot exercise "
            "the constraint without creating full FK chains."
        )
    return row  # (deal_id, stage_id, org_id)


def _insert_expense(conn, currency: str):
    """Attempt a minimal INSERT into deal_logistics_expenses with the given currency.

    Returns the cursor so callers can inspect the error (if any). Always
    rolls back to a SAVEPOINT so the connection stays usable.
    """
    deal_id, stage_id, org_id = _fetch_existing_ids(conn)
    cur = conn.cursor()
    cur.execute("SAVEPOINT constraint_test")
    try:
        cur.execute(
            """
            INSERT INTO kvota.deal_logistics_expenses
                (id, deal_id, logistics_stage_id, organization_id,
                 expense_subtype, amount, currency, expense_date)
            VALUES (%s, %s, %s, %s, 'transport', 100.00, %s, %s)
            """,
            (str(uuid4()), deal_id, stage_id, org_id, currency, date.today()),
        )
        return cur, None
    except Exception as exc:
        cur.execute("ROLLBACK TO SAVEPOINT constraint_test")
        return cur, exc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("currency", ["AED", "KZT", "JPY", "GBP", "CHF"])
def test_deal_logistics_expenses_accepts_new_currencies(db_conn, currency):
    """After migration 268, the new currencies must pass the CHECK constraint."""
    cur, exc = _insert_expense(db_conn, currency)
    assert exc is None, (
        f"Expected currency={currency!r} to be accepted after migration 268, "
        f"but got error: {exc}"
    )
    cur.close()


@pytest.mark.parametrize(
    "invalid_currency", ["usd", "EURo", "XX", "ABCD", "", "12A", "U$D"]
)
def test_deal_logistics_expenses_rejects_invalid_format(db_conn, invalid_currency):
    """Migration 268 enforces `^[A-Z]{3}$` — these must fail."""
    cur, exc = _insert_expense(db_conn, invalid_currency)
    assert exc is not None, (
        f"Expected currency={invalid_currency!r} to violate the regex check, "
        "but the INSERT succeeded."
    )
    cur.close()


def test_deal_logistics_expenses_constraint_name_preserved(db_conn):
    """Constraint must still be named `deal_logistics_expenses_currency_check`.

    Migration 268 drops and re-adds the constraint with the same name so that
    any tooling/monitoring keyed off the constraint identifier keeps working.
    """
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'kvota'
          AND t.relname = 'deal_logistics_expenses'
          AND c.conname = 'deal_logistics_expenses_currency_check'
          AND c.contype = 'c'
        """
    )
    found = cur.fetchone()
    cur.close()
    assert found is not None, (
        "Constraint 'deal_logistics_expenses_currency_check' not found after "
        "migration 268. The migration must preserve the constraint name."
    )


def test_deal_logistics_expenses_accepts_existing_currencies(db_conn):
    """Sanity: migration 268 must not break the pre-existing five currencies."""
    for currency in ["USD", "EUR", "RUB", "CNY", "TRY"]:
        cur, exc = _insert_expense(db_conn, currency)
        assert exc is None, (
            f"Regression: currency={currency!r} rejected after migration 268: {exc}"
        )
        cur.close()
