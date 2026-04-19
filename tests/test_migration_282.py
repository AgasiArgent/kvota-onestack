"""
Schema tests for migration 282 — kvota.invoice_item_coverage junction.

Phase 5c adds a proper M:N junction between invoice_items (mig 281) and
quote_items. Each coverage row carries a ratio coefficient — the number of
invoice_item units per quote_item unit — so the calc engine can handle:

- 1:1 (ratio=1)            — legacy/no-op composition
- split (1 qi → N ii)      — each invoice_item has its own ratio
- merge (N qi → 1 ii)      — N coverage rows, each ratio=1

Tests asserted here:
- composite PK (invoice_item_id, quote_item_id)
- ratio > 0 via CHECK, including a behavioural CHECK test (INSERT with
  ratio=0 must fail; ratio=0.5 and 1 must succeed)
- CASCADE on both FKs
- 2 indexes (idx_coverage_invoice_item, idx_coverage_quote_item)
- RLS enabled with 4 policies (SELECT/INSERT/UPDATE with 10/4/4 roles,
  DELETE with 2)

Source of truth: .kiro/specs/phase-5c-invoice-items/design.md §1.1 + §5.2
"""

import os
import re

import pytest


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Connection helper — skip module if no DB available.
# ---------------------------------------------------------------------------


def _get_db_connection():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 282 "
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
            "282 schema tests."
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


# ---------------------------------------------------------------------------
# Tests — table existence and shape
# ---------------------------------------------------------------------------


def test_coverage_table_exists(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema='kvota' AND table_name='invoice_item_coverage'
        """
    )
    assert cur.fetchone() is not None, (
        "kvota.invoice_item_coverage does not exist — migration 282 not applied."
    )
    cur.close()


EXPECTED_COLUMNS = [
    ("invoice_item_id", "uuid", "NO"),
    ("quote_item_id", "uuid", "NO"),
    ("ratio", "numeric", "NO"),
]


def test_coverage_column_count(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_schema='kvota' AND table_name='invoice_item_coverage'
        """
    )
    count = cur.fetchone()[0]
    cur.close()
    assert count == len(EXPECTED_COLUMNS), (
        f"invoice_item_coverage has {count} columns, expected {len(EXPECTED_COLUMNS)}."
    )


@pytest.mark.parametrize(
    "col_name,expected_type,expected_nullable", EXPECTED_COLUMNS
)
def test_coverage_column_shape(
    db_conn, col_name, expected_type, expected_nullable
):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='kvota' AND table_name='invoice_item_coverage'
          AND column_name=%s
        """,
        (col_name,),
    )
    row = cur.fetchone()
    cur.close()
    assert row is not None, f"Column {col_name} missing."
    data_type, is_nullable = row
    assert data_type.startswith(expected_type), (
        f"{col_name}: type {data_type}, expected {expected_type}"
    )
    assert is_nullable == expected_nullable


# ---------------------------------------------------------------------------
# Tests — constraints
# ---------------------------------------------------------------------------


def test_coverage_composite_primary_key(db_conn):
    """PK = (invoice_item_id, quote_item_id)."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname='kvota' AND c.relname='invoice_item_coverage'
          AND i.indisprimary
        ORDER BY array_position(i.indkey, a.attnum)
        """
    )
    cols = [r[0] for r in cur.fetchall()]
    cur.close()
    assert set(cols) == {"invoice_item_id", "quote_item_id"}, (
        f"PK should be (invoice_item_id, quote_item_id), got {cols}"
    )
    assert len(cols) == 2, f"PK must be composite, got {len(cols)} cols"


def test_coverage_ratio_check_constraint_present(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname='kvota' AND t.relname='invoice_item_coverage'
          AND c.contype='c'
        """
    )
    defs = [row[0] for row in cur.fetchall()]
    cur.close()
    # Postgres normalises "ratio > 0" to "(ratio > (0)::numeric)" for the
    # NUMERIC column; compare on a whitespace+cast-stripped form.
    def _normalise(s: str) -> str:
        # Drop whitespace and drop "::numeric" cast tokens so the definition
        # "CHECK ((ratio > (0)::numeric))" normalises to "CHECK((ratio>(0)))"
        # which plainly contains "ratio>(0)".
        return re.sub(r"::\w+", "", s).replace(" ", "")

    found = any("ratio>(0)" in _normalise(d) for d in defs)
    assert found, f"CHECK (ratio > 0) not found. Got: {defs}"


# ---------------------------------------------------------------------------
# Tests — foreign keys with CASCADE
# ---------------------------------------------------------------------------


def test_coverage_fk_invoice_item_cascade(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT a.attname, nf.nspname || '.' || tf.relname, c.confdeltype
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_class tf ON tf.oid = c.confrelid
        JOIN pg_namespace nf ON nf.oid = tf.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE n.nspname='kvota' AND t.relname='invoice_item_coverage' AND c.contype='f'
        ORDER BY a.attname
        """
    )
    rows = cur.fetchall()
    cur.close()
    ii_fk = [r for r in rows if r[0] == "invoice_item_id"]
    qi_fk = [r for r in rows if r[0] == "quote_item_id"]
    assert len(ii_fk) == 1, f"invoice_item_id FK missing: {rows}"
    assert len(qi_fk) == 1, f"quote_item_id FK missing: {rows}"
    assert ii_fk[0][1] == "kvota.invoice_items"
    assert ii_fk[0][2] == "c", "invoice_item_id must CASCADE on delete"
    assert qi_fk[0][1] == "kvota.quote_items"
    assert qi_fk[0][2] == "c", "quote_item_id must CASCADE on delete"


# ---------------------------------------------------------------------------
# Tests — indexes
# ---------------------------------------------------------------------------


def test_coverage_has_both_indexes(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT i.relname
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname='kvota' AND t.relname='invoice_item_coverage'
        """
    )
    names = [r[0] for r in cur.fetchall()]
    cur.close()
    assert "idx_coverage_invoice_item" in names, (
        f"idx_coverage_invoice_item not found. Got: {names}"
    )
    assert "idx_coverage_quote_item" in names, (
        f"idx_coverage_quote_item not found. Got: {names}"
    )


# ---------------------------------------------------------------------------
# Tests — behavioural check on ratio constraint
# ---------------------------------------------------------------------------


def _fetch_existing_invoice_item_and_quote_item(conn):
    """Find a matching (invoice_item, quote_item) pair in the same org.

    We need both sides already to exist so the FK inserts don't fail for
    unrelated reasons. If none exists yet (e.g. fresh DB), skip the test —
    the pure-SQL CHECK test still runs via `test_coverage_ratio_check_constraint_present`.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ii.id, qi.id
        FROM kvota.invoice_items ii
        JOIN kvota.invoices inv ON inv.id = ii.invoice_id
        JOIN kvota.quote_items qi ON qi.quote_id = inv.quote_id
        LIMIT 1
        """
    )
    row = cur.fetchone()
    cur.close()
    return row  # (ii_id, qi_id) or None


def _insert_coverage(conn, ii_id, qi_id, ratio):
    cur = conn.cursor()
    cur.execute("SAVEPOINT check_test")
    try:
        cur.execute(
            """
            INSERT INTO kvota.invoice_item_coverage
                (invoice_item_id, quote_item_id, ratio)
            VALUES (%s, %s, %s)
            """,
            (str(ii_id), str(qi_id), ratio),
        )
        return cur, None
    except Exception as exc:
        cur.execute("ROLLBACK TO SAVEPOINT check_test")
        return cur, exc


def test_coverage_ratio_zero_rejected(db_conn):
    """Behavioural: INSERT with ratio=0 must fail the CHECK constraint."""
    pair = _fetch_existing_invoice_item_and_quote_item(db_conn)
    if pair is None:
        pytest.skip(
            "No existing invoice_items + quote_items pair available — "
            "behavioural CHECK test requires seed data."
        )
    ii_id, qi_id = pair
    cur, exc = _insert_coverage(db_conn, ii_id, qi_id, 0)
    cur.close()
    assert exc is not None, "INSERT with ratio=0 must fail the CHECK."


def test_coverage_ratio_negative_rejected(db_conn):
    pair = _fetch_existing_invoice_item_and_quote_item(db_conn)
    if pair is None:
        pytest.skip(
            "No existing invoice_items + quote_items pair available — "
            "behavioural CHECK test requires seed data."
        )
    ii_id, qi_id = pair
    cur, exc = _insert_coverage(db_conn, ii_id, qi_id, -1)
    cur.close()
    assert exc is not None, "INSERT with ratio=-1 must fail the CHECK."


def test_coverage_fractional_ratio_accepted(db_conn):
    """Behavioural: ratio=0.5 is valid (fractional splits)."""
    pair = _fetch_existing_invoice_item_and_quote_item(db_conn)
    if pair is None:
        pytest.skip(
            "No existing invoice_items + quote_items pair available — "
            "behavioural CHECK test requires seed data."
        )
    ii_id, qi_id = pair
    cur, exc = _insert_coverage(db_conn, ii_id, qi_id, 0.5)
    cur.close()
    assert exc is None, f"INSERT with ratio=0.5 must succeed: {exc}"


# ---------------------------------------------------------------------------
# Tests — RLS
# ---------------------------------------------------------------------------


def test_coverage_rls_enabled(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname='kvota' AND c.relname='invoice_item_coverage'
        """
    )
    row = cur.fetchone()
    cur.close()
    assert row is not None
    assert row[0] is True, "RLS not enabled on kvota.invoice_item_coverage"


def _get_policy_roles(conn, policy_name):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT qual, with_check
        FROM pg_policies
        WHERE schemaname='kvota'
          AND tablename='invoice_item_coverage'
          AND policyname=%s
        """,
        (policy_name,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    qual, with_check = row
    body = (qual or "") + " " + (with_check or "")
    return set(re.findall(r"'([a-z_]+)'", body))


def test_coverage_select_policy_roles(db_conn):
    expected = {
        "admin",
        "top_manager",
        "procurement",
        "procurement_senior",
        "head_of_procurement",
        "sales",
        "head_of_sales",
        "finance",
        "quote_controller",
        "spec_controller",
    }
    roles = _get_policy_roles(db_conn, "invoice_item_coverage_select")
    assert roles is not None, "invoice_item_coverage_select policy not found"
    assert expected.issubset(roles), (
        f"SELECT policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_coverage_insert_policy_roles(db_conn):
    expected = {"admin", "procurement", "procurement_senior", "head_of_procurement"}
    roles = _get_policy_roles(db_conn, "invoice_item_coverage_insert")
    assert roles is not None
    assert expected.issubset(roles), (
        f"INSERT policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_coverage_update_policy_roles(db_conn):
    expected = {"admin", "procurement", "procurement_senior", "head_of_procurement"}
    roles = _get_policy_roles(db_conn, "invoice_item_coverage_update")
    assert roles is not None
    assert expected.issubset(roles), (
        f"UPDATE policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_coverage_delete_policy_roles(db_conn):
    expected = {"admin", "head_of_procurement"}
    roles = _get_policy_roles(db_conn, "invoice_item_coverage_delete")
    assert roles is not None
    assert expected.issubset(roles), (
        f"DELETE policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_coverage_policy_count(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM pg_policies
        WHERE schemaname='kvota' AND tablename='invoice_item_coverage'
        """
    )
    count = cur.fetchone()[0]
    cur.close()
    assert count == 4, f"Expected 4 policies, got {count}."


# ---------------------------------------------------------------------------
# Tests — cross-org containment via invoice_items FK chain
# ---------------------------------------------------------------------------


def test_coverage_policies_reference_invoice_items(db_conn):
    """RLS must resolve org via invoice_items (per design.md §5.2).

    We don't have multi-tenant seed data to exercise RLS across orgs in this
    test module, so we assert the policy text references invoice_items —
    that's the subquery that enforces org containment via cascade.
    """
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT policyname, qual, with_check
        FROM pg_policies
        WHERE schemaname='kvota' AND tablename='invoice_item_coverage'
        """
    )
    rows = cur.fetchall()
    cur.close()
    assert rows, "No policies found on invoice_item_coverage"
    for policyname, qual, with_check in rows:
        body = (qual or "") + " " + (with_check or "")
        assert "invoice_items" in body, (
            f"Policy {policyname} should reference invoice_items for org scoping. "
            f"Body: {body!r}"
        )
