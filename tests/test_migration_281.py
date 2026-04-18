"""
Schema tests for migration 281 — kvota.invoice_items table (Phase 5c).

Phase 5c replaces Phase 5b's `invoice_item_prices` with a more expressive
`invoice_items` table that carries per-invoice positions with their own
product identity, pricing, and supplier-specific attributes. This is the
foundation for split/merge composition (1 quote_item → N invoice_items or
N quote_items → 1 invoice_item).

These tests assert the schema matches the design exactly:
- 28 columns with the expected types and nullability
- UNIQUE (invoice_id, position, version)
- 3 indexes, including a partial index on unfrozen rows
- RLS enabled with 4 policies covering 10/4/4/2 roles

The tests require a live DB connection (psycopg). When no DATABASE_URL is
set or psycopg is not installed, the whole module is skipped — mirroring
the pattern in `test_migration_268_currency_constraint.py`.

Source of truth: .kiro/specs/phase-5c-invoice-items/design.md §1.1 + §5.1
"""

import os

import pytest


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Connection helper — skips the whole file if no DB is available.
# ---------------------------------------------------------------------------


def _get_db_connection():
    """Open a direct psycopg connection. Skip if prerequisites missing."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 281 "
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
            "281 schema tests."
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
# Expected schema — mirrors design.md §1.1
# ---------------------------------------------------------------------------

# (column_name, data_type prefix, is_nullable 'YES'/'NO')
# data_type is a prefix match — e.g. 'numeric' matches both 'numeric' and
# 'numeric' with precision; 'timestamp with time zone' is the full form.
EXPECTED_COLUMNS = [
    ("id", "uuid", "NO"),
    ("invoice_id", "uuid", "NO"),
    ("organization_id", "uuid", "NO"),
    ("position", "integer", "NO"),
    ("product_name", "text", "NO"),
    ("supplier_sku", "text", "YES"),
    ("brand", "text", "YES"),
    ("quantity", "numeric", "NO"),
    ("purchase_price_original", "numeric", "YES"),
    ("purchase_currency", "text", "NO"),
    ("base_price_vat", "numeric", "YES"),
    ("price_includes_vat", "boolean", "NO"),
    ("vat_rate", "numeric", "YES"),
    ("weight_in_kg", "numeric", "YES"),
    ("customs_code", "text", "YES"),
    ("supplier_country", "text", "YES"),
    ("production_time_days", "integer", "YES"),
    ("minimum_order_quantity", "integer", "YES"),
    ("dimension_height_mm", "integer", "YES"),
    ("dimension_width_mm", "integer", "YES"),
    ("dimension_length_mm", "integer", "YES"),
    ("license_ds_cost", "numeric", "YES"),
    ("license_ss_cost", "numeric", "YES"),
    ("license_sgr_cost", "numeric", "YES"),
    ("supplier_notes", "text", "YES"),
    ("version", "integer", "NO"),
    ("frozen_at", "timestamp with time zone", "YES"),
    ("frozen_by", "uuid", "YES"),
    ("created_at", "timestamp with time zone", "NO"),
    ("updated_at", "timestamp with time zone", "NO"),
    ("created_by", "uuid", "YES"),
]


# ---------------------------------------------------------------------------
# Tests — schema shape
# ---------------------------------------------------------------------------


def test_invoice_items_table_exists(db_conn):
    """kvota.invoice_items must exist as a base table after migration 281."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'kvota' AND table_name = 'invoice_items'
        """
    )
    assert cur.fetchone() is not None, (
        "kvota.invoice_items does not exist — migration 281 has not been applied."
    )
    cur.close()


def test_invoice_items_has_expected_column_count(db_conn):
    """Exactly 31 columns per design.md §1.1."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = 'kvota' AND table_name = 'invoice_items'
        """
    )
    count = cur.fetchone()[0]
    cur.close()
    assert count == len(EXPECTED_COLUMNS), (
        f"invoice_items has {count} columns, expected {len(EXPECTED_COLUMNS)}."
    )


@pytest.mark.parametrize(
    "col_name,expected_type,expected_nullable", EXPECTED_COLUMNS
)
def test_invoice_items_column_shape(
    db_conn, col_name, expected_type, expected_nullable
):
    """Each expected column has the right data type and nullability."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'kvota'
          AND table_name = 'invoice_items'
          AND column_name = %s
        """,
        (col_name,),
    )
    row = cur.fetchone()
    cur.close()
    assert row is not None, f"Column '{col_name}' missing from invoice_items."
    data_type, is_nullable = row
    assert data_type.startswith(expected_type), (
        f"Column '{col_name}' has type '{data_type}', expected prefix "
        f"'{expected_type}'."
    )
    assert is_nullable == expected_nullable, (
        f"Column '{col_name}' nullable={is_nullable}, expected {expected_nullable}."
    )


# ---------------------------------------------------------------------------
# Tests — constraints
# ---------------------------------------------------------------------------


def test_invoice_items_primary_key_on_id(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'kvota'
          AND c.relname = 'invoice_items'
          AND i.indisprimary
        """
    )
    cols = [r[0] for r in cur.fetchall()]
    cur.close()
    assert cols == ["id"], (
        f"invoice_items primary key should be (id), got {cols}."
    )


def test_invoice_items_unique_invoice_position_version(db_conn):
    """UNIQUE (invoice_id, position, version) must exist."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT c.conname,
               array_agg(a.attname ORDER BY array_position(c.conkey, a.attnum))
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE n.nspname = 'kvota'
          AND t.relname = 'invoice_items'
          AND c.contype = 'u'
        GROUP BY c.conname
        """
    )
    rows = cur.fetchall()
    cur.close()
    found = any(
        set(cols) == {"invoice_id", "position", "version"} for _name, cols in rows
    )
    assert found, (
        f"UNIQUE(invoice_id, position, version) not found. Got: {rows}"
    )


def test_invoice_items_quantity_check_positive(db_conn):
    """quantity CHECK (> 0) must be present."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'kvota'
          AND t.relname = 'invoice_items'
          AND c.contype = 'c'
        """
    )
    defs = [row[0] for row in cur.fetchall()]
    cur.close()
    assert any("quantity" in d and "> (0" in d.replace(" ", "") or "quantity > 0" in d.replace("(", "").replace(")", "") for d in defs), (
        f"CHECK (quantity > 0) not found. Got: {defs}"
    )


def test_invoice_items_version_check_positive(db_conn):
    """version CHECK (>= 1) must be present."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'kvota'
          AND t.relname = 'invoice_items'
          AND c.contype = 'c'
        """
    )
    defs = [row[0] for row in cur.fetchall()]
    cur.close()
    assert any(
        "version" in d and (">= 1" in d or ">=1" in d.replace(" ", ""))
        for d in defs
    ), f"CHECK (version >= 1) not found. Got: {defs}"


# ---------------------------------------------------------------------------
# Tests — foreign keys
# ---------------------------------------------------------------------------


def _get_fks(conn, table):
    """Return list of (col, target_table, on_delete) for FKs on a kvota.table."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            a.attname,
            nf.nspname || '.' || tf.relname,
            c.confdeltype
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_class tf ON tf.oid = c.confrelid
        JOIN pg_namespace nf ON nf.oid = tf.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE n.nspname = 'kvota'
          AND t.relname = %s
          AND c.contype = 'f'
        ORDER BY a.attname
        """,
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def test_invoice_items_fk_invoice_cascade(db_conn):
    """invoice_id FK → kvota.invoices ON DELETE CASCADE."""
    fks = _get_fks(db_conn, "invoice_items")
    invoice_fk = [(col, tgt, od) for col, tgt, od in fks if col == "invoice_id"]
    assert len(invoice_fk) == 1, f"invoice_id FK missing: {fks}"
    _, target, on_delete = invoice_fk[0]
    assert target == "kvota.invoices", f"invoice_id FK points at {target}"
    assert on_delete == "c", (
        f"invoice_id ON DELETE should be CASCADE ('c'), got '{on_delete}'"
    )


def test_invoice_items_fk_organization_no_cascade(db_conn):
    """organization_id FK → kvota.organizations, no cascade (restrict default)."""
    fks = _get_fks(db_conn, "invoice_items")
    org_fk = [(col, tgt, od) for col, tgt, od in fks if col == "organization_id"]
    assert len(org_fk) == 1, f"organization_id FK missing: {fks}"
    _, target, on_delete = org_fk[0]
    assert target == "kvota.organizations"
    # 'a' = NO ACTION (default); design says "no action"
    assert on_delete in ("a", "r"), (
        f"organization_id ON DELETE should be NO ACTION/RESTRICT, got '{on_delete}'"
    )


# ---------------------------------------------------------------------------
# Tests — indexes
# ---------------------------------------------------------------------------


def _get_indexes(conn, table):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.relname, pg_get_indexdef(ix.indexrelid)
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = 'kvota' AND t.relname = %s
        """,
        (table,),
    )
    rows = cur.fetchall()
    cur.close()
    return {name: definition for name, definition in rows}


def test_invoice_items_index_invoice_exists(db_conn):
    indexes = _get_indexes(db_conn, "invoice_items")
    assert "idx_invoice_items_invoice" in indexes, (
        f"idx_invoice_items_invoice not found. Indexes: {list(indexes)}"
    )


def test_invoice_items_index_organization_exists(db_conn):
    indexes = _get_indexes(db_conn, "invoice_items")
    assert "idx_invoice_items_organization" in indexes, (
        f"idx_invoice_items_organization not found. Indexes: {list(indexes)}"
    )


def test_invoice_items_partial_index_on_active_rows(db_conn):
    indexes = _get_indexes(db_conn, "invoice_items")
    assert "idx_invoice_items_active" in indexes, (
        f"idx_invoice_items_active not found. Indexes: {list(indexes)}"
    )
    # Partial index: must include 'WHERE' clause on frozen_at IS NULL
    defn = indexes["idx_invoice_items_active"]
    assert "WHERE" in defn.upper() and "frozen_at" in defn.lower(), (
        f"idx_invoice_items_active must be partial on frozen_at IS NULL. Def: {defn}"
    )


# ---------------------------------------------------------------------------
# Tests — RLS
# ---------------------------------------------------------------------------


def test_invoice_items_rls_enabled(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT c.relrowsecurity
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'kvota' AND c.relname = 'invoice_items'
        """
    )
    row = cur.fetchone()
    cur.close()
    assert row is not None, "invoice_items table not found"
    assert row[0] is True, "RLS is not enabled on kvota.invoice_items"


def _get_policy_roles(conn, policy_name):
    """Return the list of role slugs referenced in a policy's USING/CHECK clause."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT qual, with_check
        FROM pg_policies
        WHERE schemaname = 'kvota'
          AND tablename = 'invoice_items'
          AND policyname = %s
        """,
        (policy_name,),
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    qual, with_check = row
    body = (qual or "") + " " + (with_check or "")
    # Extract quoted slugs from r.slug IN ('a', 'b', ...)
    import re

    matches = re.findall(r"'([a-z_]+)'", body)
    return set(matches)


def test_invoice_items_select_policy_roles(db_conn):
    """SELECT policy must grant to 10 roles per design.md §5.1."""
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
    roles = _get_policy_roles(db_conn, "invoice_items_select")
    assert roles is not None, "invoice_items_select policy not found"
    assert expected.issubset(roles), (
        f"SELECT policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_invoice_items_insert_policy_roles(db_conn):
    expected = {
        "admin",
        "procurement",
        "procurement_senior",
        "head_of_procurement",
    }
    roles = _get_policy_roles(db_conn, "invoice_items_insert")
    assert roles is not None, "invoice_items_insert policy not found"
    assert expected.issubset(roles), (
        f"INSERT policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_invoice_items_update_policy_roles(db_conn):
    expected = {
        "admin",
        "procurement",
        "procurement_senior",
        "head_of_procurement",
    }
    roles = _get_policy_roles(db_conn, "invoice_items_update")
    assert roles is not None, "invoice_items_update policy not found"
    assert expected.issubset(roles), (
        f"UPDATE policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_invoice_items_delete_policy_roles(db_conn):
    expected = {"admin", "head_of_procurement"}
    roles = _get_policy_roles(db_conn, "invoice_items_delete")
    assert roles is not None, "invoice_items_delete policy not found"
    assert expected.issubset(roles), (
        f"DELETE policy missing roles: {expected - roles}. Got: {roles}"
    )


def test_invoice_items_policy_count(db_conn):
    """Exactly 4 policies (one per command)."""
    cur = db_conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*)
        FROM pg_policies
        WHERE schemaname = 'kvota' AND tablename = 'invoice_items'
        """
    )
    count = cur.fetchone()[0]
    cur.close()
    assert count == 4, f"Expected 4 policies on invoice_items, got {count}."
