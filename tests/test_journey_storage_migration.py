"""
Schema tests for migration 503 — Supabase Storage bucket for verification
screenshots (Customer Journey Map, Task 24).

Covers:
  - Bucket `journey-verification-attachments` exists with correct private flag,
    size limit, and MIME whitelist (Req 9.7, 9.8).
  - Storage RLS policies: SELECT granted to authenticated org members,
    INSERT gated to `admin` / `quote_controller` / `spec_controller` only,
    UPDATE and DELETE denied for every role (append-only — Req 9.2 + 9.6).

Requires a live DB connection (psycopg). Mirrors the skip pattern in
`test_journey_migration.py` so local runs without Supabase credentials stay
green.
"""

import os

import pytest


pytestmark = pytest.mark.integration


def _get_db_connection():
    """Open a direct psycopg connection. Skip if prerequisites missing."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip(
            "DATABASE_URL / SUPABASE_DB_URL not set — skipping migration 503 "
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
            "503 schema tests."
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


BUCKET_ID = "journey-verification-attachments"


# ---------------------------------------------------------------------------
# Bucket existence + constraints
# ---------------------------------------------------------------------------


def test_bucket_exists(db_conn):
    """The bucket must be created by migration 503."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id, public, file_size_limit, allowed_mime_types "
            "FROM storage.buckets WHERE id = %s",
            (BUCKET_ID,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"Bucket {BUCKET_ID!r} missing — migration 503 not applied?"
    )


def test_bucket_is_private(db_conn):
    """Req 9.7: the bucket must NOT be public (read via signed URLs only)."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT public FROM storage.buckets WHERE id = %s",
            (BUCKET_ID,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] is False, "Bucket must be private (public=false)"


def test_bucket_size_limit_is_2mb(db_conn):
    """Req 9.8: max 2 MB per file."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT file_size_limit FROM storage.buckets WHERE id = %s",
            (BUCKET_ID,),
        )
        row = cur.fetchone()
    assert row is not None
    assert row[0] == 2 * 1024 * 1024, (
        f"Expected 2 MB limit, got {row[0]} bytes"
    )


def test_bucket_mime_whitelist(db_conn):
    """Req 9.8: image/png, image/jpeg, image/webp only."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT allowed_mime_types FROM storage.buckets WHERE id = %s",
            (BUCKET_ID,),
        )
        row = cur.fetchone()
    assert row is not None
    mimes = set(row[0] or [])
    assert mimes == {"image/png", "image/jpeg", "image/webp"}, (
        f"Unexpected MIME whitelist: {mimes!r}"
    )


# ---------------------------------------------------------------------------
# Storage RLS policies — existence + command
# ---------------------------------------------------------------------------


EXPECTED_POLICIES = {
    # policyname: (cmd, role)
    "journey_attachments_select_authenticated": ("SELECT", "authenticated"),
    "journey_attachments_insert_qa": ("INSERT", "authenticated"),
    "journey_attachments_no_update": ("UPDATE", "authenticated"),
    "journey_attachments_no_delete": ("DELETE", "authenticated"),
}


def test_all_storage_policies_exist(db_conn):
    """Every policy we depend on must be attached to storage.objects."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT policyname, cmd, roles "
            "FROM pg_policies "
            "WHERE schemaname = 'storage' AND tablename = 'objects' "
            "  AND policyname LIKE 'journey_attachments_%%'",
        )
        rows = cur.fetchall()
    found = {row[0]: (row[1], row[2]) for row in rows}

    for name, (cmd, role) in EXPECTED_POLICIES.items():
        assert name in found, f"Policy {name!r} missing on storage.objects"
        actual_cmd, roles = found[name]
        assert actual_cmd == cmd, (
            f"Policy {name!r}: expected cmd={cmd}, got {actual_cmd}"
        )
        assert role in roles, (
            f"Policy {name!r}: expected role {role!r} in roles, got {roles!r}"
        )


def test_update_policy_denies_via_false_predicate(db_conn):
    """UPDATE policy has `... AND false` → effectively deny-all."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT qual FROM pg_policies "
            "WHERE schemaname = 'storage' AND tablename = 'objects' "
            "  AND policyname = 'journey_attachments_no_update'"
        )
        row = cur.fetchone()
    assert row is not None
    # Normalise whitespace for a loose match — `false` literal is what matters.
    qual = (row[0] or "").lower()
    assert "false" in qual, f"UPDATE policy must deny via false literal: {qual!r}"


def test_delete_policy_denies_via_false_predicate(db_conn):
    """DELETE policy mirrors UPDATE — append-only semantics."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT qual FROM pg_policies "
            "WHERE schemaname = 'storage' AND tablename = 'objects' "
            "  AND policyname = 'journey_attachments_no_delete'"
        )
        row = cur.fetchone()
    assert row is not None
    qual = (row[0] or "").lower()
    assert "false" in qual, f"DELETE policy must deny via false literal: {qual!r}"


def test_insert_policy_checks_qa_roles(db_conn):
    """INSERT policy must reference the three QA-writer role slugs."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT with_check FROM pg_policies "
            "WHERE schemaname = 'storage' AND tablename = 'objects' "
            "  AND policyname = 'journey_attachments_insert_qa'"
        )
        row = cur.fetchone()
    assert row is not None
    check = (row[0] or "").lower()
    # Policy body includes user_has_role(...) calls for each writer role.
    assert "user_has_role" in check
    assert "admin" in check
    assert "quote_controller" in check
    assert "spec_controller" in check


def test_select_policy_checks_org_membership(db_conn):
    """SELECT policy must restrict to active organization_members rows."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT qual FROM pg_policies "
            "WHERE schemaname = 'storage' AND tablename = 'objects' "
            "  AND policyname = 'journey_attachments_select_authenticated'"
        )
        row = cur.fetchone()
    assert row is not None
    qual = (row[0] or "").lower()
    assert "organization_members" in qual
    assert "auth.uid()" in qual


# ---------------------------------------------------------------------------
# Migration registration
# ---------------------------------------------------------------------------


def test_migration_registered(db_conn):
    """Migration 503 must record itself in kvota.migrations."""
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT filename FROM kvota.migrations WHERE id = 503"
        )
        row = cur.fetchone()
    assert row is not None, "Migration 503 not registered in kvota.migrations"
    assert row[0] == "503_journey_verification_attachments.sql"
