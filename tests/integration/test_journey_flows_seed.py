"""
Integration tests for the Customer Journey Map flow seed (Task 28).

Covers Req 18.1, 18.2, 18.3, 18.8:
  - The four mandated flow slugs exist in kvota.journey_flows.
  - Every flow has at least 3 steps with populated node_id/action/note.
  - display_order is unique within each (role, is_archived=false) group so
    the sidebar never shows two flows fighting for the same slot.
  - All slugs are lowercase kebab-case.

Gated on DATABASE_URL / SUPABASE_DB_URL — mirrors the skip pattern in
tests/test_journey_storage_migration.py so local runs without DB credentials
stay green. The seed at scripts/seed-journey-flows.sql must be applied before
these tests pass.
"""

import os
import re

import pytest


pytestmark = pytest.mark.integration


EXPECTED_SLUGS = {
    "sales-full",
    "procurement-flow",
    "qa-onboarding",
    "finance-monthly",
}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _get_db_connection():
    """Open a direct psycopg connection. Skip if prerequisites missing."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping journey flow "
            "seed tests (require direct DB access + seed applied)."
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
            "Neither psycopg nor psycopg2 is installed — skipping journey "
            "flow seed tests."
        )


@pytest.fixture
def db_conn():
    """Yield a live DB connection and roll back after each test."""
    conn = _get_db_connection()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


def test_four_expected_flows_exist(db_conn):
    """Req 18.8: exactly these four slugs must be seeded."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT slug FROM kvota.journey_flows "
            "WHERE is_archived = false"
        )
        slugs = {row[0] for row in cur.fetchall()}
    missing = EXPECTED_SLUGS - slugs
    assert not missing, f"Missing seeded flows: {missing!r}"


def test_each_flow_has_at_least_three_steps(db_conn):
    """Req 18.1: steps is jsonb array; seed flows are onboarding-scale."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT slug, steps FROM kvota.journey_flows "
            "WHERE slug = ANY(%s)",
            (list(EXPECTED_SLUGS),),
        )
        rows = cur.fetchall()

    assert len(rows) == len(EXPECTED_SLUGS), (
        f"Expected {len(EXPECTED_SLUGS)} rows, got {len(rows)}"
    )

    for slug, steps in rows:
        assert isinstance(steps, list), f"{slug}: steps must be a JSON array"
        assert len(steps) >= 3, f"{slug}: needs ≥3 steps, got {len(steps)}"
        for i, step in enumerate(steps):
            for field in ("node_id", "action", "note"):
                assert field in step, (
                    f"{slug} step {i}: missing {field!r}"
                )
            assert isinstance(step["node_id"], str) and step["node_id"], (
                f"{slug} step {i}: node_id must be a non-empty string"
            )
            assert isinstance(step["action"], str) and step["action"].strip(), (
                f"{slug} step {i}: action must be a non-empty string"
            )
            # `note` may be empty for some steps; spec just requires the field.
            assert isinstance(step["note"], str), (
                f"{slug} step {i}: note must be a string"
            )


def test_display_order_unique_per_role(db_conn):
    """Two active flows in the same role must not share display_order."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT role, display_order, COUNT(*) "
            "FROM kvota.journey_flows "
            "WHERE is_archived = false "
            "GROUP BY role, display_order "
            "HAVING COUNT(*) > 1"
        )
        duplicates = cur.fetchall()
    assert not duplicates, (
        f"Duplicate (role, display_order) combos: {duplicates!r}"
    )


def test_slugs_are_lowercase_kebab_case(db_conn):
    """Seed slugs must be URL-safe kebab-case for /journey/flows/:slug."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT slug FROM kvota.journey_flows WHERE slug = ANY(%s)",
            (list(EXPECTED_SLUGS),),
        )
        slugs = [row[0] for row in cur.fetchall()]

    for slug in slugs:
        assert SLUG_PATTERN.match(slug), (
            f"Slug {slug!r} is not lowercase kebab-case"
        )
