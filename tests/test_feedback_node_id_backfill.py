"""Integration tests for migration 502 — kvota.user_feedback.node_id backfill.

Requires a live DB connection (psycopg). When DATABASE_URL / SUPABASE_DB_URL
is not set, the module is skipped — matches the pattern used by
test_journey_migration.py.

The tests insert rows with various page_url shapes, apply the same mapping
SQL that migration 502 uses, and assert the resulting node_id values.
Every row is cleaned up inside the per-test transaction (rollback in the
fixture teardown).

Spec reference: .kiro/specs/customer-journey-map/requirements.md Req 11.1
(backfill half).
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
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 502 "
            "backfill tests (require direct DB access)."
        )

    try:
        import psycopg

        return psycopg.connect(dsn)
    except ImportError:
        pass

    try:
        import psycopg2

        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip(
            "Neither psycopg nor psycopg2 is installed — skipping migration "
            "502 backfill tests."
        )


@pytest.fixture
def db_conn():
    """Yield a live DB connection and roll back after each test.

    A rollback after every test is sufficient — no committed state leaks
    between cases.
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
# The exact SQL mapping expression migration 502 applies. Keep in lock-step
# with migrations/502_user_feedback_node_id_backfill.sql — if the migration
# changes, this snippet must change too.
# ---------------------------------------------------------------------------

_MAP_EXPR = """
regexp_replace(
    regexp_replace(
        split_part(split_part(%(url)s, '?', 1), '#', 1),
        '^https?://[^/]+',
        ''
    ),
    '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
    '/[id]',
    'g'
)
"""


def _apply_mapping(cur, url: str) -> str:
    """Run the migration's mapping expression against a single URL.

    Returns the parametrised path (without the 'app:' prefix). An empty
    string or a value that does not start with '/' means the backfill would
    leave node_id NULL.
    """
    cur.execute(f"SELECT {_MAP_EXPR}", {"url": url})
    return cur.fetchone()[0] or ""


# ---------------------------------------------------------------------------
# Unit-style tests on the mapping expression itself
# ---------------------------------------------------------------------------


class TestBackfillMapping:
    """The SQL expression alone — no rows inserted."""

    def test_bare_path_is_normalised(self, db_conn):
        cur = db_conn.cursor()
        assert _apply_mapping(cur, "/quotes") == "/quotes"
        cur.close()

    def test_full_url_strips_host(self, db_conn):
        cur = db_conn.cursor()
        assert (
            _apply_mapping(cur, "https://app.kvotaflow.ru/quotes") == "/quotes"
        )
        cur.close()

    def test_http_scheme_also_supported(self, db_conn):
        cur = db_conn.cursor()
        assert _apply_mapping(cur, "http://localhost:3000/tasks") == "/tasks"
        cur.close()

    def test_uuid_segment_is_parametrised(self, db_conn):
        cur = db_conn.cursor()
        result = _apply_mapping(
            cur,
            "https://app.kvotaflow.ru/quotes/"
            "45896473-4a6d-455d-aaf0-14be579263fa",
        )
        assert result == "/quotes/[id]"
        cur.close()

    def test_query_string_is_stripped(self, db_conn):
        cur = db_conn.cursor()
        result = _apply_mapping(
            cur,
            "https://app.kvotaflow.ru/quotes/"
            "45896473-4a6d-455d-aaf0-14be579263fa?step=procurement",
        )
        assert result == "/quotes/[id]"
        cur.close()

    def test_fragment_is_stripped(self, db_conn):
        cur = db_conn.cursor()
        result = _apply_mapping(
            cur,
            "https://app.kvotaflow.ru/quotes#top",
        )
        assert result == "/quotes"
        cur.close()

    def test_nested_uuid_is_parametrised(self, db_conn):
        cur = db_conn.cursor()
        result = _apply_mapping(
            cur,
            "https://app.kvotaflow.ru/procurement/"
            "0e08076b-dd0b-4987-9ad8-bc4a627231ab",
        )
        assert result == "/procurement/[id]"
        cur.close()

    def test_non_uuid_slug_is_preserved(self, db_conn):
        """Non-UUID path segments (e.g. /quotes/new) are not rewritten."""
        cur = db_conn.cursor()
        assert (
            _apply_mapping(cur, "https://kvotaflow.ru/quotes/new")
            == "/quotes/new"
        )
        cur.close()


# ---------------------------------------------------------------------------
# End-to-end test — insert rows, run the migration's UPDATE, assert node_id.
# ---------------------------------------------------------------------------


class TestBackfillOnRealRows:
    """Seed user_feedback rows, run the backfill statement, assert node_id."""

    def _seed(self, cur, rows: list[dict]) -> list[str]:
        """Insert rows, return their short_ids (used as handles)."""
        short_ids = []
        for i, r in enumerate(rows):
            # short_id is UNIQUE — prefix with the test run's pid to keep it so.
            short_id = f"FB-TEST-502-{os.getpid()}-{i:04d}"
            short_ids.append(short_id)
            cur.execute(
                """
                INSERT INTO kvota.user_feedback
                    (short_id, feedback_type, description, page_url, node_id)
                VALUES (%s, 'bug', 'test', %s, %s)
                """,
                (short_id, r.get("page_url"), r.get("node_id")),
            )
        return short_ids

    def _run_backfill(self, cur):
        """Run the UPDATE body from migration 502."""
        cur.execute(
            """
            WITH candidates AS (
                SELECT
                    id,
                    regexp_replace(
                        split_part(split_part(page_url, '?', 1), '#', 1),
                        '^https?://[^/]+',
                        ''
                    ) AS clean_path
                FROM kvota.user_feedback
                WHERE node_id IS NULL
                  AND page_url IS NOT NULL
                  AND page_url <> ''
            ),
            mapped AS (
                SELECT
                    id,
                    clean_path,
                    regexp_replace(
                        clean_path,
                        '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                        '/[id]',
                        'g'
                    ) AS parametrised_path
                FROM candidates
                WHERE clean_path LIKE '/%'
            )
            UPDATE kvota.user_feedback uf
               SET node_id = 'app:' || m.parametrised_path
              FROM mapped m
             WHERE uf.id = m.id
               AND uf.node_id IS NULL
            """
        )

    def _fetch(self, cur, short_ids: list[str]) -> dict[str, str | None]:
        cur.execute(
            """
            SELECT short_id, node_id
            FROM kvota.user_feedback
            WHERE short_id = ANY(%s)
            """,
            (short_ids,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}

    def test_known_urls_get_mapped(self, db_conn):
        cur = db_conn.cursor()
        short_ids = self._seed(
            cur,
            [
                {"page_url": "https://app.kvotaflow.ru/quotes"},
                {
                    "page_url": "https://app.kvotaflow.ru/quotes/"
                    "45896473-4a6d-455d-aaf0-14be579263fa?step=procurement"
                },
                {
                    "page_url": "https://kvotaflow.ru/procurement/"
                    "0e08076b-dd0b-4987-9ad8-bc4a627231ab"
                },
                {"page_url": "https://app.kvotaflow.ru/admin/users"},
            ],
        )
        self._run_backfill(cur)
        got = self._fetch(cur, short_ids)

        assert got[short_ids[0]] == "app:/quotes"
        assert got[short_ids[1]] == "app:/quotes/[id]"
        assert got[short_ids[2]] == "app:/procurement/[id]"
        assert got[short_ids[3]] == "app:/admin/users"
        cur.close()

    def test_unknown_url_shapes_stay_null(self, db_conn):
        """Malformed / empty / non-path URLs must leave node_id NULL.

        NOTE: `user_feedback.page_url` is NOT NULL, so we exercise the
        non-NULL-but-unmappable shapes. The NULL branch is covered by the
        backfill's `WHERE page_url IS NOT NULL` clause and validated by
        inspection of the migration SQL.
        """
        cur = db_conn.cursor()
        short_ids = self._seed(
            cur,
            [
                {"page_url": ""},
                {"page_url": "not-a-url-at-all"},  # no leading slash
                {"page_url": "mailto:x@y.com"},
            ],
        )
        self._run_backfill(cur)
        got = self._fetch(cur, short_ids)

        for sid in short_ids:
            assert got[sid] is None, (
                f"{sid}: expected NULL node_id for malformed page_url, "
                f"got {got[sid]}"
            )
        cur.close()

    def test_backfill_is_idempotent(self, db_conn):
        """A second run must not touch rows that already have node_id."""
        cur = db_conn.cursor()
        short_ids = self._seed(
            cur,
            [
                # Pre-populated: the new-feedback logic already set it.
                {
                    "page_url": "https://app.kvotaflow.ru/quotes",
                    "node_id": "app:/quotes/custom",
                },
            ],
        )
        self._run_backfill(cur)
        # First run must not touch it.
        assert self._fetch(cur, short_ids)[short_ids[0]] == "app:/quotes/custom"
        # Second run must not either.
        self._run_backfill(cur)
        assert self._fetch(cur, short_ids)[short_ids[0]] == "app:/quotes/custom"
        cur.close()
