"""
RLS matrix tests for migration 501 — Customer Journey Map annotation tables.

Source of truth: .kiro/specs/customer-journey-map/requirements.md Req 12
and Req 18.2; design.md §4.3 / §6.

Matrix (C = allowed, x = denied) — authenticated SELECT is always allowed
on every journey_* table.

    role              | n_state | n_hist | ghost | pins | verif | flows
    ------------------+---------+--------+-------+------+-------+------
    admin             |  S      |  S     |  CUD  | CUD  |  C    |  CUD
    quote_controller  |  S      |  S     |  S    | CUD  |  C    |  S
    spec_controller   |  S      |  S     |  S    | CUD  |  C    |  S
    sales             |  S      |  S     |  S    |  S   |  S    |  S
    procurement       |  S      |  S     |  S    |  S   |  S    |  S
    logistics         |  S      |  S     |  S    |  S   |  S    |  S
    finance           |  S      |  S     |  S    |  S   |  S    |  S
    top_manager       |  S      |  S     |  S    |  S   |  S    |  S

Key invariants checked explicitly at module scope:
- SELECT allowed for all roles on all 6 tables.
- top_manager denied every INSERT/UPDATE/DELETE.
- journey_verifications DELETE denied for everyone (append-only).
- journey_verifications UPDATE denied for everyone (append-only).
- journey_node_state INSERT/UPDATE/DELETE denied for every authenticated
  role — Python API running as service_role is the only writer.
- journey_node_state_history INSERT/UPDATE/DELETE denied for every
  authenticated role — trigger-only population.

Test impersonation strategy
---------------------------
We connect as the superuser (`postgres`) via DATABASE_URL, then for each
test we open a transaction that:
  1. SETs LOCAL request.jwt.claim.sub to the fake user's uuid (auth.uid()
     reads it via current_setting('request.jwt.claim.sub', true)).
  2. SETs LOCAL ROLE authenticated so that the "TO authenticated" clause on
     our policies matches.
  3. Runs the operation under test.
  4. Rolls back — no data persists even on success.

Because the user has a row in kvota.user_roles joined to the role slug
under test, kvota.user_has_role('<slug>') returns true during the
transaction.

Skipped when DATABASE_URL / SUPABASE_DB_URL is unset or psycopg is not
installed — same pattern as test_journey_migration.py.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Roles we exercise (matches kvota.roles and migration 168 clean-up).
# ---------------------------------------------------------------------------

WRITE_ROLES = [
    "admin",
    "quote_controller",
    "spec_controller",
    "sales",
    "procurement",
    "logistics",
    "finance",
    "top_manager",
]

JOURNEY_TABLES = [
    "journey_node_state",
    "journey_node_state_history",
    "journey_ghost_nodes",
    "journey_pins",
    "journey_verifications",
    "journey_flows",
]

# Roles allowed to INSERT / UPDATE / DELETE (per Req 12 matrix).
PINS_WRITERS = {"admin", "quote_controller", "spec_controller"}
VERIFS_WRITERS = {"admin", "quote_controller", "spec_controller"}
GHOST_WRITERS = {"admin"}
FLOWS_WRITERS = {"admin"}
# journey_node_state and journey_node_state_history: no authenticated writers.
NODE_STATE_WRITERS: set[str] = set()
NODE_STATE_HIST_WRITERS: set[str] = set()


def _get_db_connection():
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping RLS matrix "
            "tests (require direct DB access)."
        )
    try:
        import psycopg  # psycopg v3

        return psycopg.connect(dsn)
    except ImportError:
        pass
    try:
        import psycopg2

        return psycopg2.connect(dsn)
    except ImportError:
        pytest.skip(
            "Neither psycopg nor psycopg2 is installed — skipping RLS "
            "matrix tests."
        )


# ---------------------------------------------------------------------------
# Session-scoped setup: pick an organization and create one auth.users row +
# one kvota.user_roles row PER ROLE under test. The rows are cleaned up at
# the end of the session. Per-test transactions are rolled back so the
# infrastructure rows remain available to the whole matrix run.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def _rls_setup():
    conn = _get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()

    # Pick any existing organization — we just need a valid FK.
    cur.execute("SELECT id FROM kvota.organizations LIMIT 1")
    row = cur.fetchone()
    if row is None:
        pytest.skip("No kvota.organizations row available — cannot set up RLS tests.")
    org_id = row[0]

    # Load role_id for every slug we care about.
    cur.execute(
        "SELECT slug, id FROM kvota.roles WHERE slug = ANY(%s)",
        (WRITE_ROLES,),
    )
    role_by_slug: dict[str, str] = dict(cur.fetchall())
    missing_roles = set(WRITE_ROLES) - set(role_by_slug)
    if missing_roles:
        pytest.skip(
            "Role slugs missing from kvota.roles — cannot run matrix: "
            f"{missing_roles}"
        )

    # Create one fake auth.users row per slug and one kvota.user_roles row.
    # Prefixing the email with the slug keeps the test rows easy to find
    # and safe to clean up.
    user_by_slug: dict[str, str] = {}
    created_user_ids: list[str] = []
    for slug in WRITE_ROLES:
        uid = str(uuid.uuid4())
        email = f"rls-journey-{slug}-{uid[:8]}@test.invalid"
        cur.execute(
            """
            INSERT INTO auth.users (id, email, instance_id, aud, role)
            VALUES (%s, %s,
                    '00000000-0000-0000-0000-000000000000',
                    'authenticated',
                    'authenticated')
            ON CONFLICT (id) DO NOTHING
            """,
            (uid, email),
        )
        cur.execute(
            """
            INSERT INTO kvota.user_roles (user_id, organization_id, role_id)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (uid, org_id, role_by_slug[slug]),
        )
        user_by_slug[slug] = uid
        created_user_ids.append(uid)

    cur.close()

    yield {
        "conn": conn,
        "user_by_slug": user_by_slug,
        "org_id": org_id,
    }

    # Teardown: remove the user_roles rows + auth.users rows we created.
    cleanup = conn.cursor()
    try:
        cleanup.execute(
            "DELETE FROM kvota.user_roles WHERE user_id = ANY(%s)",
            (created_user_ids,),
        )
        cleanup.execute(
            "DELETE FROM auth.users WHERE id = ANY(%s)",
            (created_user_ids,),
        )
    finally:
        cleanup.close()
        conn.close()


@contextmanager
def _tx(conn):
    """Open a savepoint-style transaction that is always rolled back.

    Does NOT switch roles; caller is responsible for any SET LOCAL ROLE.
    """
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        yield cur
    finally:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        cur.close()


def _become_authenticated(cur, user_id: str) -> None:
    """Switch the current transaction to authenticated role with the given uid.

    Must be called from a transaction already opened by `_tx`. After this,
    auth.uid() returns user_id and RLS policies TO authenticated match.
    """
    cur.execute("SET LOCAL ROLE authenticated")
    cur.execute(
        "SELECT set_config('request.jwt.claim.sub', %s, true)",
        (user_id,),
    )


@contextmanager
def _as_user(conn, user_id: str):
    """Convenience: open a tx, become authenticated, yield, rollback.

    Used for INSERT and SELECT tests that don't need pre-existing rows.
    """
    with _tx(conn) as cur:
        _become_authenticated(cur, user_id)
        yield cur


# ---------------------------------------------------------------------------
# SQL fixtures — one INSERT template per table, parameterised enough to
# succeed when RLS allows it. Payloads stay within CHECK constraints.
# ---------------------------------------------------------------------------


def _insert_sql(table: str) -> tuple[str, tuple]:
    node_id_app = f"app:/__rls_test_{uuid.uuid4().hex[:8]}__"
    node_id_ghost = f"ghost:__rls_test_{uuid.uuid4().hex[:8]}__"
    if table == "journey_node_state":
        return (
            "INSERT INTO kvota.journey_node_state "
            "(node_id, impl_status, qa_status, version) "
            "VALUES (%s, 'partial', 'untested', 1)",
            (node_id_app,),
        )
    if table == "journey_node_state_history":
        return (
            "INSERT INTO kvota.journey_node_state_history "
            "(node_id, impl_status, qa_status, version) "
            "VALUES (%s, 'partial', 'untested', 1)",
            (node_id_app,),
        )
    if table == "journey_ghost_nodes":
        return (
            "INSERT INTO kvota.journey_ghost_nodes (node_id, title) "
            "VALUES (%s, 'rls test ghost')",
            (node_id_ghost,),
        )
    if table == "journey_pins":
        return (
            "INSERT INTO kvota.journey_pins "
            "(node_id, selector, expected_behavior, mode) "
            "VALUES (%s, '#btn', 'clickable', 'qa')",
            (node_id_app,),
        )
    if table == "journey_verifications":
        # Needs a real pin_id. We insert a pin first in the same transaction
        # via a CTE, then insert the verification using that id.
        return (
            "WITH new_pin AS ( "
            "  INSERT INTO kvota.journey_pins "
            "    (node_id, selector, expected_behavior, mode) "
            "  VALUES (%s, '#btn', 'clickable', 'qa') "
            "  RETURNING id, node_id "
            ") "
            "INSERT INTO kvota.journey_verifications "
            "  (pin_id, node_id, result) "
            "SELECT id, node_id, 'verified' FROM new_pin",
            (node_id_app,),
        )
    if table == "journey_flows":
        return (
            "INSERT INTO kvota.journey_flows "
            "(slug, title, role, persona) "
            "VALUES (%s, 'rls test flow', 'sales', 'test persona')",
            (f"rls-test-{uuid.uuid4().hex[:8]}",),
        )
    raise AssertionError(f"Unknown table {table}")


def _seed_row(cur, table: str) -> tuple[str, str]:
    """Insert a seed row (as postgres superuser) before switching roles.

    Returns (column, value) that uniquely identifies the inserted row so
    UPDATE / DELETE probes can target it. All inserts are rolled back by
    the surrounding transaction.
    """
    if table == "journey_node_state":
        node_id = f"app:/__rls_seed_{uuid.uuid4().hex[:8]}__"
        cur.execute(
            "INSERT INTO kvota.journey_node_state "
            "(node_id, impl_status, qa_status, version) "
            "VALUES (%s, 'partial', 'untested', 1)",
            (node_id,),
        )
        return ("node_id", node_id)
    if table == "journey_node_state_history":
        node_id = f"app:/__rls_seed_{uuid.uuid4().hex[:8]}__"
        cur.execute(
            "INSERT INTO kvota.journey_node_state_history "
            "(node_id, impl_status, qa_status, version) "
            "VALUES (%s, 'partial', 'untested', 1)",
            (node_id,),
        )
        return ("node_id", node_id)
    if table == "journey_ghost_nodes":
        node_id = f"ghost:__rls_seed_{uuid.uuid4().hex[:8]}__"
        cur.execute(
            "INSERT INTO kvota.journey_ghost_nodes (node_id, title) "
            "VALUES (%s, 'rls seed ghost')",
            (node_id,),
        )
        return ("node_id", node_id)
    if table == "journey_pins":
        cur.execute(
            "INSERT INTO kvota.journey_pins "
            "(node_id, selector, expected_behavior, mode) "
            "VALUES (%s, '#seed', 'clickable', 'qa') RETURNING id",
            (f"app:/__rls_seed_{uuid.uuid4().hex[:8]}__",),
        )
        pin_id = cur.fetchone()[0]
        return ("id", str(pin_id))
    if table == "journey_verifications":
        # Need a pin as FK parent first.
        node_id = f"app:/__rls_seed_{uuid.uuid4().hex[:8]}__"
        cur.execute(
            "INSERT INTO kvota.journey_pins "
            "(node_id, selector, expected_behavior, mode) "
            "VALUES (%s, '#seed', 'clickable', 'qa') RETURNING id",
            (node_id,),
        )
        pin_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO kvota.journey_verifications "
            "(pin_id, node_id, result) VALUES (%s, %s, 'verified') RETURNING id",
            (pin_id, node_id),
        )
        verif_id = cur.fetchone()[0]
        return ("id", str(verif_id))
    if table == "journey_flows":
        slug = f"rls-seed-{uuid.uuid4().hex[:8]}"
        cur.execute(
            "INSERT INTO kvota.journey_flows "
            "(slug, title, role, persona) "
            "VALUES (%s, 'rls seed flow', 'sales', 'seed persona')",
            (slug,),
        )
        return ("slug", slug)
    raise AssertionError(f"Unknown table {table}")


_UPDATE_COL_BY_TABLE = {
    "journey_node_state":         ("notes", "rls-probe"),
    "journey_node_state_history": ("notes", "rls-probe"),
    "journey_ghost_nodes":        ("title", "rls-probe"),
    "journey_pins":               ("expected_behavior", "rls-probe"),
    "journey_verifications":      ("note", "rls-probe"),
    "journey_flows":              ("title", "rls-probe"),
}


def _update_sql(table: str, where_col: str, where_val: str) -> tuple[str, tuple]:
    set_col, set_val = _UPDATE_COL_BY_TABLE[table]
    return (
        f"UPDATE kvota.{table} SET {set_col} = %s WHERE {where_col} = %s",
        (set_val, where_val),
    )


def _delete_sql(table: str, where_col: str, where_val: str) -> tuple[str, tuple]:
    return (
        f"DELETE FROM kvota.{table} WHERE {where_col} = %s",
        (where_val,),
    )


WRITERS_BY_TABLE: dict[str, set[str]] = {
    "journey_node_state":         NODE_STATE_WRITERS,
    "journey_node_state_history": NODE_STATE_HIST_WRITERS,
    "journey_ghost_nodes":        GHOST_WRITERS,
    "journey_pins":               PINS_WRITERS,
    "journey_verifications":      VERIFS_WRITERS,
    "journey_flows":              FLOWS_WRITERS,
}

# DELETE/UPDATE denied for every role on these append-only / API-only tables.
NO_UPDATE_TABLES = {
    "journey_node_state",
    "journey_node_state_history",
    "journey_verifications",
}
NO_DELETE_TABLES = {
    "journey_node_state",
    "journey_node_state_history",
    "journey_verifications",
}


def _run_and_classify(cur, sql: str, params: tuple) -> str:
    """Return 'allowed', 'denied_rls', or 'denied_perm'.

    RLS violations surface as psycopg errors mentioning "row-level security".
    Base-table privilege failures surface as "permission denied for table".
    Both count as "denied" for the matrix, but we keep the distinction for
    debugging.
    """
    try:
        cur.execute(sql, params)
        return "allowed"
    except Exception as exc:  # psycopg / psycopg2 share the Error hierarchy
        msg = str(exc).lower()
        if "row-level security" in msg or "violates row-level security" in msg:
            return "denied_rls"
        if "permission denied" in msg:
            return "denied_perm"
        # Unknown failure — re-raise so the test surfaces it loudly.
        raise


# ---------------------------------------------------------------------------
# SELECT — allowed for every role on every table (Req 12.2, 12.3).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", JOURNEY_TABLES)
@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_select_allowed(_rls_setup, table, slug):
    user_id = _rls_setup["user_by_slug"][slug]
    with _as_user(_rls_setup["conn"], user_id) as cur:
        # LIMIT 0 — we only care that the statement does not raise.
        cur.execute(f"SELECT 1 FROM kvota.{table} LIMIT 0")
        # Successful execution == SELECT permitted.


# ---------------------------------------------------------------------------
# INSERT — permitted set per matrix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", JOURNEY_TABLES)
@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_insert_matrix(_rls_setup, table, slug):
    user_id = _rls_setup["user_by_slug"][slug]
    sql, params = _insert_sql(table)
    expected_allowed = slug in WRITERS_BY_TABLE[table]
    with _as_user(_rls_setup["conn"], user_id) as cur:
        outcome = _run_and_classify(cur, sql, params)
    if expected_allowed:
        assert outcome == "allowed", (
            f"INSERT {table} should be ALLOWED for {slug!r} — got {outcome}"
        )
    else:
        assert outcome.startswith("denied"), (
            f"INSERT {table} should be DENIED for {slug!r} — got {outcome}"
        )


# ---------------------------------------------------------------------------
# UPDATE — permitted set per matrix; appended-only tables deny for everyone.
# A seed row is created as postgres in the same transaction, so RLS has
# something to filter and 0-row no-ops cannot masquerade as "allowed".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", JOURNEY_TABLES)
@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_update_matrix(_rls_setup, table, slug):
    user_id = _rls_setup["user_by_slug"][slug]
    if table in NO_UPDATE_TABLES:
        expected_allowed = False
    else:
        expected_allowed = slug in WRITERS_BY_TABLE[table]

    with _tx(_rls_setup["conn"]) as cur:
        where_col, where_val = _seed_row(cur, table)
        _become_authenticated(cur, user_id)
        sql, params = _update_sql(table, where_col, where_val)
        outcome = _run_and_classify(cur, sql, params)
        rowcount = cur.rowcount if outcome == "allowed" else None

    if expected_allowed:
        assert outcome == "allowed", (
            f"UPDATE {table} should be ALLOWED for {slug!r} — got {outcome}"
        )
        assert rowcount == 1, (
            f"UPDATE {table} for {slug!r}: expected 1 row affected, got {rowcount}"
        )
    else:
        # Denied can mean: RLS/permission error raised, OR the statement
        # returned without error but affected 0 rows (RLS filtered before
        # the UPDATE could touch anything). Both are acceptable "denied".
        if outcome == "allowed":
            assert rowcount == 0, (
                f"UPDATE {table} should be DENIED for {slug!r} — statement "
                f"executed AND affected {rowcount} row(s)"
            )
        else:
            assert outcome.startswith("denied"), (
                f"UPDATE {table} unexpected outcome for {slug!r}: {outcome}"
            )


# ---------------------------------------------------------------------------
# DELETE — permitted set per matrix; append-only tables deny everyone.
# Same seed-row strategy as UPDATE.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", JOURNEY_TABLES)
@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_delete_matrix(_rls_setup, table, slug):
    user_id = _rls_setup["user_by_slug"][slug]
    if table in NO_DELETE_TABLES:
        expected_allowed = False
    else:
        expected_allowed = slug in WRITERS_BY_TABLE[table]

    with _tx(_rls_setup["conn"]) as cur:
        where_col, where_val = _seed_row(cur, table)
        _become_authenticated(cur, user_id)
        sql, params = _delete_sql(table, where_col, where_val)
        outcome = _run_and_classify(cur, sql, params)
        rowcount = cur.rowcount if outcome == "allowed" else None

    if expected_allowed:
        assert outcome == "allowed", (
            f"DELETE {table} should be ALLOWED for {slug!r} — got {outcome}"
        )
        assert rowcount == 1, (
            f"DELETE {table} for {slug!r}: expected 1 row affected, got {rowcount}"
        )
    else:
        if outcome == "allowed":
            assert rowcount == 0, (
                f"DELETE {table} should be DENIED for {slug!r} — statement "
                f"executed AND affected {rowcount} row(s)"
            )
        else:
            assert outcome.startswith("denied"), (
                f"DELETE {table} unexpected outcome for {slug!r}: {outcome}"
            )


# ---------------------------------------------------------------------------
# Explicit top-level invariants — extra coverage beyond the parametrised
# matrix so a regression in one cell fails a clearly-named test.
# ---------------------------------------------------------------------------


def _attempt_write(conn, user_id: str, table: str, op: str) -> tuple[str, int | None]:
    """Seed a target row, switch to authenticated, attempt op.

    op ∈ {"INSERT", "UPDATE", "DELETE"}. Returns (outcome, rowcount).
    rowcount is None when an exception was raised (denied_rls / denied_perm).

    The whole thing runs inside a rolled-back transaction.
    """
    with _tx(conn) as cur:
        if op == "INSERT":
            _become_authenticated(cur, user_id)
            sql, params = _insert_sql(table)
            outcome = _run_and_classify(cur, sql, params)
            return outcome, cur.rowcount if outcome == "allowed" else None
        # UPDATE / DELETE need a pre-existing row.
        where_col, where_val = _seed_row(cur, table)
        _become_authenticated(cur, user_id)
        if op == "UPDATE":
            sql, params = _update_sql(table, where_col, where_val)
        elif op == "DELETE":
            sql, params = _delete_sql(table, where_col, where_val)
        else:
            raise AssertionError(f"Unknown op {op}")
        outcome = _run_and_classify(cur, sql, params)
        return outcome, cur.rowcount if outcome == "allowed" else None


def _assert_denied(outcome: str, rowcount: int | None, context: str) -> None:
    """Write was denied iff a deny error was raised OR 0 rows were affected."""
    if outcome.startswith("denied"):
        return
    assert outcome == "allowed", f"{context}: unexpected outcome {outcome}"
    assert rowcount == 0, (
        f"{context}: statement executed AND affected {rowcount} row(s) "
        f"— should have been denied"
    )


@pytest.mark.parametrize("table", JOURNEY_TABLES)
def test_top_manager_denied_all_writes(_rls_setup, table):
    """Req 12 + design.md §6 amendment: top_manager has no write permission."""
    user_id = _rls_setup["user_by_slug"]["top_manager"]
    for op in ("INSERT", "UPDATE", "DELETE"):
        outcome, rowcount = _attempt_write(
            _rls_setup["conn"], user_id, table, op
        )
        _assert_denied(
            outcome,
            rowcount,
            f"top_manager {op} {table}",
        )


@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_journey_verifications_delete_denied_everyone(_rls_setup, slug):
    """Req 12.7: journey_verifications is append-only — DELETE denied for every role."""
    user_id = _rls_setup["user_by_slug"][slug]
    outcome, rowcount = _attempt_write(
        _rls_setup["conn"], user_id, "journey_verifications", "DELETE"
    )
    _assert_denied(outcome, rowcount, f"{slug} DELETE journey_verifications")


@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_journey_verifications_update_denied_everyone(_rls_setup, slug):
    """Req 12.7: journey_verifications append-only — UPDATE denied for every role."""
    user_id = _rls_setup["user_by_slug"][slug]
    outcome, rowcount = _attempt_write(
        _rls_setup["conn"], user_id, "journey_verifications", "UPDATE"
    )
    _assert_denied(outcome, rowcount, f"{slug} UPDATE journey_verifications")


@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_journey_node_state_writes_denied_everyone(_rls_setup, slug):
    """Req 12.4: client direct INSERT/UPDATE/DELETE on journey_node_state always denied.

    Python API uses service_role which bypasses RLS; all authenticated-role
    writes — including admin — must fail.
    """
    user_id = _rls_setup["user_by_slug"][slug]
    for op in ("INSERT", "UPDATE", "DELETE"):
        outcome, rowcount = _attempt_write(
            _rls_setup["conn"], user_id, "journey_node_state", op
        )
        _assert_denied(
            outcome,
            rowcount,
            f"{slug} {op} journey_node_state",
        )


@pytest.mark.parametrize("slug", WRITE_ROLES)
def test_journey_node_state_history_writes_denied_everyone(_rls_setup, slug):
    """Req 12.8: journey_node_state_history client writes always denied.

    Only the SECURITY DEFINER trigger from migration 500 may INSERT rows.
    """
    user_id = _rls_setup["user_by_slug"][slug]
    for op in ("INSERT", "UPDATE", "DELETE"):
        outcome, rowcount = _attempt_write(
            _rls_setup["conn"], user_id, "journey_node_state_history", op
        )
        _assert_denied(
            outcome,
            rowcount,
            f"{slug} {op} journey_node_state_history",
        )
