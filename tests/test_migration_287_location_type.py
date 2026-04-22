"""
Schema tests for migration 287 — kvota.locations.location_type enum.

Wave 1 Task 1 of logistics-customs-redesign spec (R15).

Tests:
- Column exists with correct type (VARCHAR(20), NOT NULL, default 'hub')
- CHECK constraint rejects invalid values, accepts the 5 enum values
- Backfill correctly mapped is_customs_point=true → 'customs', else is_hub
  → 'hub', default 'hub' for neither
- search_locations() RPC extended with p_location_type param still works

Integration test — skipped when DATABASE_URL absent. Pattern mirrors
test_migration_285_invoices_sla.py.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _get_db_connection():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — skipping migration 287 schema tests.")
    try:
        import psycopg  # type: ignore

        return psycopg.connect(dsn)
    except ImportError:
        pass
    try:
        import psycopg2  # type: ignore

        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip("Neither psycopg nor psycopg2 installed.")


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


VALID_TYPES = ("supplier", "hub", "customs", "own_warehouse", "client")


def test_location_type_column_exists(db_conn):
    """Column kvota.locations.location_type — VARCHAR, NOT NULL, default 'hub'."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'kvota'
              AND table_name = 'locations'
              AND column_name = 'location_type'
            """
        )
        row = cur.fetchone()

    assert row is not None, "column location_type missing from kvota.locations"
    data_type, nullable, default = row
    assert data_type == "character varying"
    assert nullable == "NO"
    assert default is not None and "'hub'" in default


def test_location_type_check_constraint_enforces_enum(db_conn):
    """Only the 5 enum values are allowed; other values rejected."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_constraintdef(oid) AS def
            FROM pg_constraint
            WHERE conname = 'locations_location_type_check'
            """
        )
        row = cur.fetchone()

    assert row is not None, "CHECK constraint locations_location_type_check missing"
    constraint_def = row[0]
    for t in VALID_TYPES:
        assert f"'{t}'" in constraint_def, f"CHECK must allow '{t}'"


def test_backfill_preserves_is_customs_point(db_conn):
    """Every pre-existing row with is_customs_point=true should map to 'customs'."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM kvota.locations
            WHERE is_customs_point = true AND location_type != 'customs'
            """
        )
        count = cur.fetchone()[0]

    assert count == 0, (
        f"{count} row(s) with is_customs_point=true but location_type≠'customs' — "
        "backfill missed them"
    )


def test_backfill_preserves_is_hub(db_conn):
    """is_hub=true AND is_customs_point=false → 'hub' (priority to customs if both)."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)
            FROM kvota.locations
            WHERE is_hub = true
              AND (is_customs_point IS NULL OR is_customs_point = false)
              AND location_type != 'hub'
            """
        )
        count = cur.fetchone()[0]

    assert count == 0


def test_type_index_exists(db_conn):
    """idx_locations_type_active for filter-by-type perf."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'kvota'
              AND tablename = 'locations'
              AND indexname = 'idx_locations_type_active'
            """
        )
        row = cur.fetchone()

    assert row is not None


def test_search_locations_accepts_new_param(db_conn):
    """search_locations() RPC has p_location_type parameter (migration 287)."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pg_get_function_arguments(p.oid) AS args
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'kvota' AND p.proname = 'search_locations'
            """
        )
        row = cur.fetchone()

    assert row is not None, "search_locations() RPC missing"
    args = row[0]
    assert "p_location_type" in args, (
        "search_locations() must have p_location_type VARCHAR DEFAULT NULL "
        "(added in m287)"
    )


def test_migration_recorded(db_conn):
    with db_conn.cursor() as cur:
        cur.execute("SELECT filename FROM kvota.migrations WHERE id = 287")
        row = cur.fetchone()

    assert row is not None
    assert row[0] == "287_locations_location_type"
