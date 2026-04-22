"""
Schema tests for migration 285 — invoices SLA timers + customs assignment.

Wave 1 Task 7.1 of logistics-customs-redesign spec. Adds 10 new columns
on kvota.invoices (5 logistics SLA + 5 customs SLA) + 1 assigned_customs_user
FK + 2 review-flag columns, plus 5 indexes.

Source of truth: .kiro/specs/logistics-customs-redesign/design.md §5.2.

Test pattern follows test_migration_281.py — integration test that skips
when no DB available.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _get_db_connection():
    """Open a direct psycopg connection. Skip if prerequisites missing."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 285 "
            "schema tests (require direct DB access)."
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
            "Neither psycopg nor psycopg2 is installed — skipping migration 285."
        )


@pytest.fixture
def db_conn():
    conn = _get_db_connection()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


# Columns added by migration 285
EXPECTED_COLUMNS = [
    ("assigned_customs_user", "uuid", "YES"),
    ("logistics_assigned_at", "timestamp with time zone", "YES"),
    ("logistics_deadline_at", "timestamp with time zone", "YES"),
    ("logistics_completed_at", "timestamp with time zone", "YES"),
    ("logistics_sla_hours", "integer", "YES"),
    ("customs_assigned_at", "timestamp with time zone", "YES"),
    ("customs_deadline_at", "timestamp with time zone", "YES"),
    ("customs_completed_at", "timestamp with time zone", "YES"),
    ("customs_sla_hours", "integer", "YES"),
    ("logistics_needs_review_since", "timestamp with time zone", "YES"),
    ("customs_needs_review_since", "timestamp with time zone", "YES"),
]

EXPECTED_INDEXES = [
    "idx_invoices_assigned_customs_user",
    "idx_invoices_logistics_active",
    "idx_invoices_customs_active",
    "idx_invoices_logistics_needs_review",
    "idx_invoices_customs_needs_review",
]


def test_all_columns_exist(db_conn):
    """Each column from design §5.2 is present with correct type."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'kvota' AND table_name = 'invoices'
              AND column_name = ANY(%s)
            """,
            ([name for name, _, _ in EXPECTED_COLUMNS],),
        )
        rows = {r[0]: (r[1], r[2], r[3]) for r in cur.fetchall()}

    for name, expected_type, expected_nullable in EXPECTED_COLUMNS:
        assert name in rows, f"Column {name} missing from kvota.invoices"
        actual_type, actual_nullable, _ = rows[name]
        assert actual_type == expected_type, (
            f"{name}: expected type {expected_type!r}, got {actual_type!r}"
        )
        assert actual_nullable == expected_nullable


def test_sla_hours_defaults_to_72(db_conn):
    """logistics_sla_hours and customs_sla_hours default to 72 (3 days)."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_schema = 'kvota' AND table_name = 'invoices'
              AND column_name IN ('logistics_sla_hours', 'customs_sla_hours')
            """
        )
        defaults = {r[0]: r[1] for r in cur.fetchall()}

    assert defaults.get("logistics_sla_hours") == "72"
    assert defaults.get("customs_sla_hours") == "72"


def test_assigned_customs_user_fk_to_auth_users(db_conn):
    """assigned_customs_user has FK to auth.users(id)."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_schema = 'kvota'
              AND tc.table_name = 'invoices'
              AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = 'assigned_customs_user'
              AND ccu.table_schema = 'auth'
              AND ccu.table_name = 'users'
            """
        )
        rows = cur.fetchall()

    assert len(rows) == 1, "Expected exactly one FK on assigned_customs_user → auth.users"


def test_all_indexes_exist(db_conn):
    """All 5 indexes from migration 285 are present."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'kvota' AND tablename = 'invoices'
              AND indexname = ANY(%s)
            """,
            (EXPECTED_INDEXES,),
        )
        actual = {r[0] for r in cur.fetchall()}

    missing = set(EXPECTED_INDEXES) - actual
    assert not missing, f"Missing indexes: {missing}"


def test_migration_recorded(db_conn):
    """Migration 285 row exists in kvota.migrations."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, filename FROM kvota.migrations WHERE id = 285"
        )
        row = cur.fetchone()

    assert row is not None, "Migration 285 not recorded in kvota.migrations"
    assert row[1] == "285_invoices_sla_and_customs_assignment"
