"""
Tests for migration 307: grant head_of_procurement DELETE on kvota.documents.

Bug context (РОЗ-83, 2026-05-05):
    head_of_procurement (chislova.e@masterbearing.ru) tried to delete a КП
    document attachment from a quote and got a "мало прав" error.

    Root cause: documents_delete_policy from migration 143 hardcoded role
    allowlist excluded head_of_procurement. The API layer
    (api/documents.py:131) already accepts head_of_procurement, so the request
    reaches Supabase and is silently dropped by RLS at the DB level.

    Migration 301 widened INSERT/UPDATE for chat attachments but explicitly
    left DELETE alone. Migration 307 adds head_of_procurement to the existing
    allowlist (keeping role-gated stance, NOT going full org-scope, since
    DELETE is destructive).

These tests assert the SQL contract of the migration file. Live RLS behaviour
is verified in production after `scripts/apply-migrations.sh` runs — pytest
runs without a live PG connection in CI.
"""

from __future__ import annotations

import glob
import os
import re

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MIGRATIONS_DIR = os.path.join(_PROJECT_ROOT, "migrations")


def _find_migration_307() -> str | None:
    pattern = os.path.join(
        _MIGRATIONS_DIR, "307_grant_head_of_procurement_documents_delete.sql"
    )
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def _read_migration_307() -> str:
    path = _find_migration_307()
    if path is None:
        pytest.fail(
            "Migration 307 file does not exist. Expected "
            "migrations/307_grant_head_of_procurement_documents_delete.sql"
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _extract_delete_policy_role_list(sql: str) -> list[str]:
    """Pull the role slug list from the documents_delete_policy CREATE POLICY.

    Returns the list of slug strings inside the `r.slug IN (...)` clause.
    Fails the test if the policy block can't be located.
    """
    # CREATE POLICY documents_delete_policy ... USING ( ... r.slug IN (...) )
    create_match = re.search(
        r"CREATE\s+POLICY\s+documents_delete_policy"
        r".*?r\.slug\s+IN\s*\(([^)]*)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not create_match:
        pytest.fail(
            "Migration 307 must contain a CREATE POLICY documents_delete_policy "
            "block with `r.slug IN (...)`."
        )
    raw_list = create_match.group(1)
    return [
        m.group(1)
        for m in re.finditer(r"'([a-z_]+)'", raw_list)
    ]


# ----------------------------------------------------------------------------
# File existence + structure
# ----------------------------------------------------------------------------


class TestMigration307Exists:
    """Migration 307 must exist as a .sql file in migrations/."""

    def test_migration_file_exists(self) -> None:
        assert _find_migration_307() is not None, (
            "Expected migrations/307_grant_head_of_procurement_documents_delete.sql"
        )

    def test_migration_is_sql_file(self) -> None:
        path = _find_migration_307()
        assert path is not None
        assert path.endswith(".sql"), f"Migration 307 must be .sql, got {path}"


# ----------------------------------------------------------------------------
# Role allowlist contract (the actual fix)
# ----------------------------------------------------------------------------


class TestDocumentsDeletePolicyRoleAllowlist:
    """Assert DELETE policy includes head_of_procurement and keeps prior roles.

    These are the assertions that fail BEFORE the migration is written and
    pass AFTER — protecting against accidental policy regressions in future
    migrations.
    """

    def test_drops_existing_policy_first(self) -> None:
        """Migration must DROP the old policy to avoid duplicate-name errors."""
        sql = _read_migration_307()
        assert re.search(
            r"DROP\s+POLICY\s+IF\s+EXISTS\s+documents_delete_policy",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 307 must DROP POLICY IF EXISTS documents_delete_policy "
            "before recreating it."
        )

    def test_creates_delete_policy_for_documents(self) -> None:
        """Migration must CREATE POLICY ... FOR DELETE on kvota.documents."""
        sql = _read_migration_307()
        # Cover both `ON kvota.documents` and bare `ON documents` (after BEGIN
        # with search_path) for resilience against minor formatting changes.
        assert re.search(
            r"CREATE\s+POLICY\s+documents_delete_policy\s+ON\s+(?:kvota\.)?documents"
            r"\s+FOR\s+DELETE",
            sql,
            flags=re.IGNORECASE,
        ), (
            "Migration 307 must CREATE POLICY documents_delete_policy ON "
            "kvota.documents FOR DELETE."
        )

    def test_head_of_procurement_in_allowlist(self) -> None:
        """The fix: head_of_procurement is now permitted to DELETE."""
        roles = _extract_delete_policy_role_list(_read_migration_307())
        assert "head_of_procurement" in roles, (
            "Migration 307 must add 'head_of_procurement' to the "
            "documents_delete_policy role allowlist. Got: " + str(roles)
        )

    def test_existing_roles_preserved(self) -> None:
        """Migration must NOT drop any role that was permitted before.

        Migration 143 allowlist: admin, sales_manager, quote_controller, finance.
        All four must still be present after migration 307.
        """
        roles = _extract_delete_policy_role_list(_read_migration_307())
        for legacy_role in ("admin", "sales_manager", "quote_controller", "finance"):
            assert legacy_role in roles, (
                f"Migration 307 must preserve '{legacy_role}' from migration 143's "
                f"allowlist. Got: {roles}"
            )

    def test_regular_procurement_not_in_allowlist(self) -> None:
        """Regression guard: DELETE stays role-gated, NOT org-scope.

        Spec says we keep destructive-action gating: only head_of_procurement
        is added, not regular `procurement` (МОЗ). If a future migration wants
        to widen further, it should be its own decision and update this test.
        """
        roles = _extract_delete_policy_role_list(_read_migration_307())
        assert "procurement" not in roles, (
            "Migration 307 spec: DELETE remains role-gated. Plain 'procurement' "
            "(МОЗ) must NOT be in the allowlist — only 'head_of_procurement'. "
            f"Got: {roles}"
        )

    def test_other_heads_not_in_allowlist(self) -> None:
        """Regression guard: head_of_sales / head_of_logistics not added here.

        Spec explicitly says other heads can be considered separately. If a
        future migration adds them, that migration owns the change — this
        test catches accidental scope creep in 307.
        """
        roles = _extract_delete_policy_role_list(_read_migration_307())
        for unintended_role in ("head_of_sales", "head_of_logistics"):
            assert unintended_role not in roles, (
                f"Migration 307 spec: only 'head_of_procurement' added. "
                f"'{unintended_role}' should be considered in a separate "
                f"migration. Got: {roles}"
            )


# ----------------------------------------------------------------------------
# Transactional safety
# ----------------------------------------------------------------------------


class TestMigration307IsTransactional:
    """Migration must run inside a single BEGIN/COMMIT transaction."""

    def test_wrapped_in_begin_commit(self) -> None:
        sql = _read_migration_307()
        assert re.search(r"\bBEGIN\b", sql, flags=re.IGNORECASE), (
            "Migration 307 must start with BEGIN."
        )
        assert re.search(r"\bCOMMIT\b", sql, flags=re.IGNORECASE), (
            "Migration 307 must end with COMMIT."
        )
