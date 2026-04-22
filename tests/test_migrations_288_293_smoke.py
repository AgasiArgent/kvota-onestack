"""
Smoke tests for migrations 288-293 — Wave 1 foundation tables.

Quick schema-presence checks. Integration-style: skipped without DATABASE_URL.

Covers:
- 288: logistics_route_segments + logistics_segment_expenses
- 289: logistics_operational_events + logistics_route_templates +
       logistics_route_template_segments
- 290: view v_logistics_plan_fact_items
- 291: entity_notes + entity_notes_user_has_any_role function
- 292: head_of_customs role seed
- 293: customs_item_expenses + customs_quote_expenses, customs_psm_pts rename,
       customs_ds_sgr + customs_marking drop
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration


def _get_db():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — skipping migration 288-293 smoke.")
    try:
        import psycopg  # type: ignore

        return psycopg.connect(dsn)
    except ImportError:
        pass
    try:
        import psycopg2  # type: ignore

        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip("psycopg not installed.")


@pytest.fixture
def db():
    conn = _get_db()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


NEW_TABLES = [
    # m288
    "logistics_route_segments",
    "logistics_segment_expenses",
    # m289
    "logistics_operational_events",
    "logistics_route_templates",
    "logistics_route_template_segments",
    # m291
    "entity_notes",
    # m293
    "customs_item_expenses",
    "customs_quote_expenses",
]


def test_all_new_tables_present(db):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'kvota' AND table_name = ANY(%s)
            """,
            (NEW_TABLES,),
        )
        present = {r[0] for r in cur.fetchall()}

    missing = set(NEW_TABLES) - present
    assert not missing, f"Tables missing in kvota: {missing}"


def test_view_v_logistics_plan_fact_items(db):
    """m290 — view present and selectable."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'kvota' AND table_name = 'v_logistics_plan_fact_items'
            """
        )
        assert cur.fetchone() is not None

        # Smoke-select. View should be empty (no segments yet) but not error.
        cur.execute(
            "SELECT COUNT(*) FROM kvota.v_logistics_plan_fact_items"
        )
        count = cur.fetchone()[0]
        assert isinstance(count, int)


def test_head_of_customs_role_seeded(db):
    """m292 — at least one org has head_of_customs."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM kvota.roles
            WHERE slug = 'head_of_customs'
            """
        )
        count = cur.fetchone()[0]
    assert count >= 1, "Expected head_of_customs role in at least one org"


def test_entity_notes_rls_helper_exists(db):
    """m291 — SECURITY DEFINER helper function for visible_to check."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'kvota'
              AND p.proname = 'entity_notes_user_has_any_role'
            """
        )
        assert cur.fetchone() is not None


def test_customs_psm_pts_renamed(db):
    """m293 — customs_psn_pts renamed to customs_psm_pts."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'kvota' AND table_name = 'quote_items'
              AND column_name IN ('customs_psn_pts', 'customs_psm_pts')
            """
        )
        names = {r[0] for r in cur.fetchall()}

    assert "customs_psm_pts" in names, "Expected new column customs_psm_pts"
    assert "customs_psn_pts" not in names, "Old column customs_psn_pts should be gone"


def test_customs_legacy_columns_dropped(db):
    """m293 — customs_ds_sgr and customs_marking dropped."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'kvota' AND table_name = 'quote_items'
              AND column_name IN ('customs_ds_sgr', 'customs_marking')
            """
        )
        lingering = [r[0] for r in cur.fetchall()]

    assert not lingering, f"Expected legacy columns dropped: {lingering}"


def test_migrations_recorded(db):
    """All migration IDs 288-293 recorded in kvota.migrations."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM kvota.migrations
            WHERE id IN (288, 289, 290, 291, 292, 293)
            ORDER BY id
            """
        )
        ids = [r[0] for r in cur.fetchall()]

    assert ids == [288, 289, 290, 291, 292, 293], f"Expected 288-293, got {ids}"
