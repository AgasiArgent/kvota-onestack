"""
Schema tests for migration 295 — journey annotation tables.

Covers the 6 tables that back every mutable Customer Journey Map annotation,
plus the `kvota.user_has_role(slug)` helper reuse, the
`journey_node_state` → `journey_node_state_history` AFTER UPDATE trigger, and
the `node_id` column on `kvota.user_feedback`.

Source of truth: .kiro/specs/customer-journey-map/design.md §3 and §4.3,
with amendments in requirements.md Req 2, Req 11, Req 18.

The tests require a live DB connection (psycopg). When no DATABASE_URL is
set or psycopg is not installed, the whole module is skipped — mirroring
the pattern in `test_migration_281.py`.

NOTE ON FEEDBACK TABLE NAME: the spec says `kvota.feedback` but the actual
table in this codebase is `kvota.user_feedback` (created in migration 144).
This migration targets `user_feedback` — there is no `kvota.feedback`.
"""

import os

import pytest


pytestmark = pytest.mark.integration


def _get_db_connection():
    """Open a direct psycopg connection. Skip if prerequisites missing."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 295 "
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
            "Neither psycopg nor psycopg2 is installed — skipping migration "
            "295 schema tests."
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


# ---------------------------------------------------------------------------
# Expected tables + their required columns
# ---------------------------------------------------------------------------

JOURNEY_TABLES = [
    "journey_node_state",
    "journey_node_state_history",
    "journey_ghost_nodes",
    "journey_pins",
    "journey_verifications",
    "journey_flows",
]


EXPECTED_COLUMNS = {
    "journey_node_state": {
        "node_id": "text",
        "impl_status": "text",
        "qa_status": "text",
        "notes": "text",
        "version": "integer",
        "last_tested_at": "timestamp with time zone",
        "updated_at": "timestamp with time zone",
        "updated_by": "uuid",
    },
    "journey_node_state_history": {
        "id": "uuid",
        "node_id": "text",
        "impl_status": "text",
        "qa_status": "text",
        "notes": "text",
        "version": "integer",
        "changed_by": "uuid",
        "changed_at": "timestamp with time zone",
    },
    "journey_ghost_nodes": {
        "id": "uuid",
        "node_id": "text",
        "proposed_route": "text",
        "title": "text",
        "planned_in": "text",
        "assignee": "uuid",
        "parent_node_id": "text",
        "cluster": "text",
        "status": "text",
        "created_by": "uuid",
        "created_at": "timestamp with time zone",
    },
    "journey_pins": {
        "id": "uuid",
        "node_id": "text",
        "selector": "text",
        "expected_behavior": "text",
        "mode": "text",
        "training_step_order": "integer",
        "linked_story_ref": "text",
        "last_rel_x": "numeric",
        "last_rel_y": "numeric",
        "last_rel_width": "numeric",
        "last_rel_height": "numeric",
        "last_position_update": "timestamp with time zone",
        "selector_broken": "boolean",
        "created_by": "uuid",
        "created_at": "timestamp with time zone",
    },
    "journey_verifications": {
        "id": "uuid",
        "pin_id": "uuid",
        "node_id": "text",
        "result": "text",
        "note": "text",
        "attachment_urls": "ARRAY",
        "tested_by": "uuid",
        "tested_at": "timestamp with time zone",
    },
    "journey_flows": {
        "id": "uuid",
        "slug": "text",
        "title": "text",
        "role": "text",
        "persona": "text",
        "description": "text",
        "est_minutes": "integer",
        "steps": "jsonb",
        "display_order": "integer",
        "is_archived": "boolean",
        "created_by": "uuid",
        "created_at": "timestamp with time zone",
        "updated_at": "timestamp with time zone",
    },
}


# Per-table CHECK constraint fragments we expect to find (substring match
# against a normalised pg_get_constraintdef output).
EXPECTED_CHECK_FRAGMENTS = {
    "journey_node_state": [
        # impl_status IN ('done','partial','missing')
        "impl_status",
        # qa_status IN ('verified','broken','untested')
        "qa_status",
    ],
    "journey_ghost_nodes": [
        "status",  # proposed/approved/in_progress/shipped
        "ghost:",  # node_id LIKE 'ghost:%'
    ],
    "journey_pins": [
        "mode",  # qa/training
    ],
    "journey_verifications": [
        "result",  # verified/broken/skip
    ],
}


# ---------------------------------------------------------------------------
# Core test #1 — tables, columns, constraints, trigger, RLS, feedback column
# ---------------------------------------------------------------------------


def test_journey_tables_migration(db_conn):
    """All 6 journey tables + trigger + RLS + user_feedback.node_id."""
    cur = db_conn.cursor()

    # 1) Every table exists in kvota schema.
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'kvota' AND table_name = ANY(%s)
        """,
        (JOURNEY_TABLES,),
    )
    present = {row[0] for row in cur.fetchall()}
    missing = set(JOURNEY_TABLES) - present
    assert not missing, f"Missing journey tables: {missing}"

    # 2) Required columns exist with expected data types.
    for table, columns in EXPECTED_COLUMNS.items():
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'kvota' AND table_name = %s
            """,
            (table,),
        )
        rows = {name: dtype for name, dtype in cur.fetchall()}
        for col, expected_type in columns.items():
            assert col in rows, (
                f"kvota.{table} missing column '{col}'. Present: "
                f"{sorted(rows)}"
            )
            actual = rows[col]
            assert actual.startswith(expected_type) or actual == expected_type, (
                f"kvota.{table}.{col}: got type '{actual}', expected "
                f"prefix '{expected_type}'."
            )

    # 3) CHECK constraints mention expected columns / values.
    for table, fragments in EXPECTED_CHECK_FRAGMENTS.items():
        cur.execute(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'kvota'
              AND t.relname = %s
              AND c.contype = 'c'
            """,
            (table,),
        )
        defs = " ".join(row[0] for row in cur.fetchall())
        for fragment in fragments:
            assert fragment in defs, (
                f"kvota.{table}: expected CHECK fragment '{fragment}' "
                f"missing from: {defs}"
            )

    # 4) Trigger trg_journey_node_state_history on journey_node_state.
    cur.execute(
        """
        SELECT tgname
        FROM pg_trigger
        WHERE tgrelid = 'kvota.journey_node_state'::regclass
          AND NOT tgisinternal
        """
    )
    triggers = {row[0] for row in cur.fetchall()}
    assert "trg_journey_node_state_history" in triggers, (
        f"Trigger missing. Found: {triggers}"
    )

    # 5) RLS enabled on all 6 tables.
    cur.execute(
        """
        SELECT c.relname, c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'kvota' AND c.relname = ANY(%s)
        """,
        (JOURNEY_TABLES,),
    )
    rls = dict(cur.fetchall())
    for table in JOURNEY_TABLES:
        assert rls.get(table) is True, f"RLS not enabled on kvota.{table}"

    # 6) kvota.user_feedback.node_id column + index.
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'user_feedback'
          AND column_name = 'node_id'
        """
    )
    assert cur.fetchone() is not None, "user_feedback.node_id missing"

    cur.execute(
        """
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = 'kvota'
          AND tablename = 'user_feedback'
          AND indexdef ILIKE '%(node_id%'
        """
    )
    idx_rows = cur.fetchall()
    assert idx_rows, (
        "No index on kvota.user_feedback(node_id) found. "
        f"Indexes queried returned: {idx_rows}"
    )

    cur.close()


# ---------------------------------------------------------------------------
# Core test #2 — history trigger fires on UPDATE
# ---------------------------------------------------------------------------


def test_history_trigger_fires(db_conn):
    """UPDATE on journey_node_state copies OLD row into history."""
    cur = db_conn.cursor()

    test_node = "app:/__trigger_test__"

    # Clean up any prior run.
    cur.execute(
        "DELETE FROM kvota.journey_node_state_history WHERE node_id = %s",
        (test_node,),
    )
    cur.execute(
        "DELETE FROM kvota.journey_node_state WHERE node_id = %s",
        (test_node,),
    )

    # INSERT — should NOT fire the history trigger (AFTER UPDATE only).
    cur.execute(
        """
        INSERT INTO kvota.journey_node_state
            (node_id, impl_status, qa_status, notes, version)
        VALUES (%s, 'partial', 'untested', 'first note', 1)
        """,
        (test_node,),
    )

    cur.execute(
        "SELECT COUNT(*) FROM kvota.journey_node_state_history "
        "WHERE node_id = %s",
        (test_node,),
    )
    assert cur.fetchone()[0] == 0, "History row created on INSERT (should be UPDATE-only)"

    # UPDATE — should copy the OLD row into history.
    cur.execute(
        """
        UPDATE kvota.journey_node_state
           SET impl_status = 'done',
               qa_status   = 'verified',
               notes       = 'second note',
               version     = version + 1
         WHERE node_id = %s
        """,
        (test_node,),
    )

    cur.execute(
        """
        SELECT impl_status, qa_status, notes, version
        FROM kvota.journey_node_state_history
        WHERE node_id = %s
        ORDER BY changed_at DESC
        LIMIT 1
        """,
        (test_node,),
    )
    row = cur.fetchone()
    assert row is not None, "History row not written on UPDATE"
    impl_status, qa_status, notes, version = row
    # The trigger captures the OLD row, so we expect pre-update values.
    assert impl_status == "partial", (
        f"History impl_status should be OLD value 'partial', got {impl_status}"
    )
    assert qa_status == "untested", (
        f"History qa_status should be OLD value 'untested', got {qa_status}"
    )
    assert notes == "first note", (
        f"History notes should be OLD value 'first note', got {notes}"
    )
    assert version == 1, f"History version should be OLD value 1, got {version}"

    # Cleanup (rollback fixture handles this, but be tidy in case of commit).
    cur.execute(
        "DELETE FROM kvota.journey_node_state_history WHERE node_id = %s",
        (test_node,),
    )
    cur.execute(
        "DELETE FROM kvota.journey_node_state WHERE node_id = %s",
        (test_node,),
    )
    cur.close()


# ---------------------------------------------------------------------------
# Core test #3 — user_has_role helper
# ---------------------------------------------------------------------------


def test_user_has_role_helper(db_conn):
    """kvota.user_has_role(slug) exists, returns boolean, is SECURITY DEFINER."""
    cur = db_conn.cursor()

    # Function exists with exactly this signature.
    cur.execute(
        """
        SELECT pg_get_function_arguments(oid),
               pg_get_function_result(oid),
               prosecdef
        FROM pg_proc
        WHERE pronamespace = 'kvota'::regnamespace
          AND proname = 'user_has_role'
        """
    )
    rows = cur.fetchall()
    assert rows, "kvota.user_has_role not found"
    # Pick the single-arg (text) overload.
    candidates = [r for r in rows if "text" in r[0] and "uuid" not in r[0]]
    assert candidates, (
        f"kvota.user_has_role(text) overload not found. Got: {rows}"
    )
    args, result, secdef = candidates[0]
    assert "text" in args, f"Expected text argument, got: {args}"
    assert result == "boolean", f"Expected boolean return, got: {result}"
    assert secdef is True, "user_has_role should be SECURITY DEFINER"

    # Call with an unknown slug — should return false without error, even
    # when auth.uid() is null (unauthenticated psycopg session).
    cur.execute("SELECT kvota.user_has_role(%s)", ("__definitely_not_a_role__",))
    result = cur.fetchone()[0]
    assert result is False, (
        f"user_has_role('__definitely_not_a_role__') should be false, got {result}"
    )

    # Call with a known slug — for an unauthenticated session auth.uid() is
    # null so the EXISTS returns false, which is what we assert here. This
    # confirms the function runs and does not raise.
    cur.execute("SELECT kvota.user_has_role(%s)", ("admin",))
    result = cur.fetchone()[0]
    assert result is False, (
        "user_has_role('admin') without a session should still return false, "
        f"got {result}"
    )

    cur.close()
