"""
Integration tests for the journey QA test-user seed (Task 25).

Covers Req 10.3–10.4 of `.kiro/specs/customer-journey-map/requirements.md`:
  - One `qa-{role_slug}@kvotaflow.ru` account exists per active role.
  - Each account has a role mapping in `kvota.user_roles` to the matching slug.
  - Each account has an active `kvota.organization_members` row.
  - Credentials log in successfully with `JOURNEY_TEST_USERS_PASSWORD`
    (smoke-tests one role).

The tests are DB-gated: they skip locally unless a direct DB connection
(`DATABASE_URL` / `SUPABASE_DB_URL`) is configured. This mirrors the pattern
in `tests/test_journey_storage_migration.py`.
"""

from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


# Roles that MUST have a seeded QA user (see seed-journey-test-users.py).
# Requirements doc §10.4 says "12 test users" — stale. `procurement_senior`
# became an active role after the spec was written, so we seed 13.
EXPECTED_ROLE_SLUGS: tuple[str, ...] = (
    "admin",
    "sales",
    "procurement",
    "procurement_senior",
    "logistics",
    "customs",
    "quote_controller",
    "spec_controller",
    "finance",
    "top_manager",
    "head_of_sales",
    "head_of_procurement",
    "head_of_logistics",
)


def _get_db_connection():
    """Open a direct psycopg connection or skip if unavailable."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping journey "
            "test-user seed integration tests."
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
            "Neither psycopg nor psycopg2 installed — cannot run journey "
            "seed integration tests."
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


def _qa_email(slug: str) -> str:
    return f"qa-{slug}@kvotaflow.ru"


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------


def test_all_qa_auth_users_exist(db_conn):
    """One auth.users row exists for every expected role."""
    emails = [_qa_email(slug) for slug in EXPECTED_ROLE_SLUGS]
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT email FROM auth.users WHERE email = ANY(%s)",
            (emails,),
        )
        found = {row[0].lower() for row in cur.fetchall()}

    missing = sorted(set(e.lower() for e in emails) - found)
    assert not missing, (
        f"Missing {len(missing)} QA auth users — run "
        "scripts/seed-journey-test-users.py on this environment: "
        f"{missing!r}"
    )


def test_each_qa_user_has_matching_role(db_conn):
    """Every qa-{slug}@... must have a kvota.user_roles row with the slug."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.email, r.slug
            FROM auth.users u
            JOIN kvota.user_roles ur ON ur.user_id = u.id
            JOIN kvota.roles r ON r.id = ur.role_id
            WHERE u.email LIKE 'qa-%%@kvotaflow.ru'
            """
        )
        pairs = {(row[0].lower(), row[1]) for row in cur.fetchall()}

    missing = []
    for slug in EXPECTED_ROLE_SLUGS:
        if (_qa_email(slug).lower(), slug) not in pairs:
            missing.append((_qa_email(slug), slug))

    assert not missing, (
        f"QA users missing role assignment: {missing!r}"
    )


def test_each_qa_user_has_active_org_membership(db_conn):
    """Every QA user must belong to an active organization."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.email
            FROM auth.users u
            JOIN kvota.organization_members om ON om.user_id = u.id
            WHERE u.email LIKE 'qa-%%@kvotaflow.ru'
              AND om.status = 'active'
            """
        )
        members = {row[0].lower() for row in cur.fetchall()}

    missing = [
        _qa_email(slug)
        for slug in EXPECTED_ROLE_SLUGS
        if _qa_email(slug).lower() not in members
    ]
    assert not missing, (
        f"QA users without active org_members row: {missing!r}"
    )


# ---------------------------------------------------------------------------
# Credentials smoke-test
# ---------------------------------------------------------------------------


def test_admin_qa_user_can_sign_in():
    """Password from JOURNEY_TEST_USERS_PASSWORD must authenticate qa-admin.

    Uses the public Supabase auth endpoint rather than the DB so we verify
    the password hash, not just row presence.
    """
    password = os.environ.get("JOURNEY_TEST_USERS_PASSWORD")
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")

    if not (password and supabase_url and supabase_anon_key):
        pytest.skip(
            "JOURNEY_TEST_USERS_PASSWORD / SUPABASE_URL / SUPABASE_ANON_KEY "
            "not set — skipping sign-in smoke test."
        )

    try:
        from supabase import create_client  # type: ignore
    except ImportError:  # pragma: no cover
        pytest.skip("supabase-py not installed")

    client = create_client(supabase_url, supabase_anon_key)
    resp = client.auth.sign_in_with_password(
        {"email": _qa_email("admin"), "password": password}
    )
    assert getattr(resp, "user", None) is not None, (
        "sign-in failed: no user returned — password or seed out of sync"
    )
