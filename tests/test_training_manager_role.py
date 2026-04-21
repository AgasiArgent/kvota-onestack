"""
Tests for training_manager role feature (TDD - tests first).

Feature: training_manager role -- read-only viewer with impersonation access
for training managers who need to demo the system across all roles.

Requirements:
1. ROLE_LABELS_RU contains "training_manager" entry
2. sidebar() shows impersonation dropdown for training_manager (not just admin)
3. sidebar() shows full operational menu for training_manager
4. sidebar() does NOT show "Администрирование" section for training_manager
5. /admin/impersonate route allows training_manager role (not just admin)
6. Training page shows no edit/delete buttons for training_manager

Tests are written to FAIL against current code (TDD -- implementation comes later).
"""

# Phase 6C-3 (2026-04-21): FastHTML shell retired; main.py is now a 22-line stub.
# These tests parse main.py source or access removed attributes to validate
# archived FastHTML code. Skipping keeps the suite green while a follow-up PR
# decides whether to delete, rewrite against legacy-fasthtml/, or port to
# Next.js E2E tests.
import pytest
pytest.skip(
    "Tests validate archived FastHTML code in main.py (Phase 6C-3). "
    "Follow-up: delete or retarget to legacy-fasthtml/.",
    allow_module_level=True,
)


import pytest
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_py():
    """Read main.py source code."""
    with open(MAIN_PY) as f:
        return f.read()


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def training_manager_session():
    """Session dict for a user with only training_manager role."""
    return {
        "user": {
            "id": "tm-user-001",
            "email": "trainer@kvotaflow.ru",
            "user_metadata": {"full_name": "Training Manager"},
            "org_id": "org-001",
            "organization_id": "org-001",
            "roles": ["training_manager"],
        },
    }


@pytest.fixture
def admin_session():
    """Session dict for a user with admin role."""
    return {
        "user": {
            "id": "admin-user-001",
            "email": "admin@kvotaflow.ru",
            "user_metadata": {"full_name": "Admin User"},
            "org_id": "org-001",
            "organization_id": "org-001",
            "roles": ["admin"],
        },
    }


@pytest.fixture
def sales_session():
    """Session dict for a user with only sales role."""
    return {
        "user": {
            "id": "sales-user-001",
            "email": "sales@kvotaflow.ru",
            "user_metadata": {"full_name": "Sales User"},
            "org_id": "org-001",
            "organization_id": "org-001",
            "roles": ["sales"],
        },
    }


@pytest.fixture
def training_manager_impersonating_sales_session():
    """Session for training_manager impersonating sales role."""
    return {
        "user": {
            "id": "tm-user-001",
            "email": "trainer@kvotaflow.ru",
            "user_metadata": {"full_name": "Training Manager"},
            "org_id": "org-001",
            "organization_id": "org-001",
            "roles": ["training_manager"],
        },
        "impersonated_role": "sales",
    }


# =============================================================================
# TEST 1: ROLE_LABELS_RU contains training_manager
# =============================================================================

class TestRoleLabelsContainTrainingManager:
    """ROLE_LABELS_RU dict must include training_manager entry."""

    def test_role_labels_has_training_manager_key(self):
        """ROLE_LABELS_RU should have 'training_manager' key."""
        import main
        assert "training_manager" in main.ROLE_LABELS_RU, (
            "ROLE_LABELS_RU is missing 'training_manager' entry"
        )

    def test_role_labels_training_manager_is_russian(self):
        """ROLE_LABELS_RU['training_manager'] should be a non-empty Russian label."""
        import main
        label = main.ROLE_LABELS_RU.get("training_manager")
        assert label is not None, "training_manager label is None"
        assert len(label) > 0, "training_manager label is empty"
        # Should contain Cyrillic characters (Russian label)
        assert any('\u0400' <= ch <= '\u04FF' for ch in label), (
            f"training_manager label '{label}' does not contain Cyrillic characters"
        )


# =============================================================================
# TEST 2: sidebar() shows impersonation dropdown for training_manager
# =============================================================================

class TestSidebarImpersonationForTrainingManager:
    """sidebar() must render impersonation dropdown for training_manager, not just admin."""

    def test_sidebar_source_allows_training_manager_impersonation(self):
        """The sidebar code should check for training_manager when deciding to show
        impersonation dropdown, not just 'admin' via is_real_admin."""
        source = _read_main_py()

        # Find the sidebar function and the impersonation dropdown gate
        # Currently: `if is_real_admin:` around impersonation_select
        # After fix: should use `can_impersonate` or equivalent that includes training_manager
        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function in main.py"
        sidebar_body = sidebar_match.group(1)

        # The sidebar must reference "training_manager" somewhere in the impersonation logic
        assert "training_manager" in sidebar_body, (
            "sidebar() does not reference 'training_manager' -- "
            "impersonation dropdown is still admin-only"
        )

    def test_sidebar_has_can_impersonate_or_equivalent(self):
        """sidebar() should have a variable (can_impersonate or similar) that
        includes training_manager for impersonation access."""
        source = _read_main_py()

        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function"
        sidebar_body = sidebar_match.group(1)

        # Should have either:
        # - can_impersonate = is_real_admin or is_training_manager (or similar)
        # - "training_manager" in the condition that gates impersonation_select
        has_can_impersonate = "can_impersonate" in sidebar_body
        has_training_in_impersonation_gate = re.search(
            r'if\s+.*training_manager.*:.*\n.*impersonation',
            sidebar_body,
            re.DOTALL
        )

        assert has_can_impersonate or has_training_in_impersonation_gate, (
            "sidebar() lacks a 'can_impersonate' variable or equivalent that "
            "allows training_manager to access impersonation dropdown"
        )


# =============================================================================
# TEST 3: sidebar() shows full operational menu for training_manager
# =============================================================================

class TestSidebarFullMenuForTrainingManager:
    """training_manager should see all operational menu sections like admin does."""

    def test_sidebar_treats_training_manager_as_full_access_for_menu(self):
        """The sidebar is_admin variable (used for menu visibility) should be True
        for training_manager users, not just actual admins."""
        source = _read_main_py()

        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function"
        sidebar_body = sidebar_match.group(1)

        # When no impersonation is active, is_admin should include training_manager
        # Look for pattern like: is_admin = is_real_admin or is_training_manager
        # or: is_admin = is_real_admin or "training_manager" in real_roles
        has_training_manager_admin = re.search(
            r'is_admin\s*=\s*.*training_manager',
            sidebar_body
        )
        has_is_training_variable = "is_training_manager" in sidebar_body

        assert has_training_manager_admin or has_is_training_variable, (
            "sidebar() does not give training_manager full menu visibility -- "
            "is_admin calculation does not include training_manager"
        )


# =============================================================================
# TEST 4: sidebar() does NOT show Администрирование for training_manager
# =============================================================================

class TestSidebarHidesAdminSectionForTrainingManager:
    """The 'Администрирование' section must be gated by is_real_admin, not is_admin,
    so training_manager does not see admin-only items."""

    def test_admin_section_uses_is_real_admin_not_is_admin(self):
        """The '=== ADMIN SECTION ===' block in sidebar should be gated by
        is_real_admin (which excludes training_manager), not is_admin (which includes it)."""
        source = _read_main_py()

        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function"
        sidebar_body = sidebar_match.group(1)

        # Find the admin section gate
        # Currently (before implementation): `if is_admin:` around admin items
        # After implementation: should be `if is_real_admin:`
        admin_section_match = re.search(
            r'# ===\s*ADMIN SECTION\s*===.*?\n\s*(if\s+\w+:)',
            sidebar_body
        )
        assert admin_section_match, (
            "Could not find '# === ADMIN SECTION ===' comment with if-guard in sidebar"
        )

        guard_line = admin_section_match.group(1)
        assert "is_real_admin" in guard_line, (
            f"Admin section gate is '{guard_line}', expected 'if is_real_admin:'. "
            "training_manager should NOT see Администрирование."
        )

    def test_company_registries_uses_is_real_admin(self):
        """The 'Юрлица' menu item should be gated by is_real_admin, not is_admin,
        so training_manager cannot see company registry admin items."""
        source = _read_main_py()

        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function"
        sidebar_body = sidebar_match.group(1)

        # Find the company registries gate
        # Look for Юрлица or "Company registries" comment near an if guard
        registries_match = re.search(
            r'(?:Company registries|Юрлица).*?\n\s*(if\s+\w+:)',
            sidebar_body
        )

        if registries_match:
            guard_line = registries_match.group(1)
            assert "is_real_admin" in guard_line, (
                f"Company registries gate is '{guard_line}', expected 'if is_real_admin:'. "
                "training_manager should NOT see Юрлица."
            )
        else:
            # If pattern not found, check that the Юрлица line has is_real_admin nearby
            yurlitsa_idx = sidebar_body.find("Юрлица")
            if yurlitsa_idx == -1:
                yurlitsa_idx = sidebar_body.find("Company registries")
            if yurlitsa_idx != -1:
                context = sidebar_body[max(0, yurlitsa_idx - 200):yurlitsa_idx]
                assert "is_real_admin" in context, (
                    "Юрлица/Company registries section is not gated by is_real_admin"
                )


# =============================================================================
# TEST 5 (deleted) — covered /admin/impersonate route guard training_manager
# access; route archived to legacy-fasthtml/admin_cluster.py in Phase 6C-2B
# Mega-E (2026-04-20). The training_manager role itself remains alive; this
# test section probed the now-archived @rt("/admin/impersonate") source and
# is no longer applicable.
# =============================================================================


# =============================================================================
# TEST 6 (deleted) — covered /training page role gates; routes archived to
# legacy-fasthtml/training.py in Phase 6C-2B-5 (2026-04-20). The
# training_manager role itself remains alive; this test section probed the
# now-archived @rt("/training") + @rt("/training/new-form") source and is
# no longer applicable.
# =============================================================================


# =============================================================================
# TEST 7: user_has_any_role works correctly with training_manager
# =============================================================================

class TestUserHasAnyRoleWithTrainingManager:
    """user_has_any_role should correctly handle training_manager role."""

    def test_user_has_any_role_with_training_manager_in_list(self):
        """user_has_any_role should return True when training_manager is in the
        check list and the user has that role."""
        import main
        session = {
            "user": {
                "id": "tm-001",
                "roles": ["training_manager"],
            }
        }
        result = main.user_has_any_role(session, ["admin", "training_manager"])
        assert result is True, (
            "user_has_any_role should return True for training_manager"
        )

    def test_user_has_any_role_training_manager_not_in_admin_list(self):
        """user_has_any_role should return False when checking ['admin'] for
        a training_manager user (they are NOT admin)."""
        import main
        session = {
            "user": {
                "id": "tm-001",
                "roles": ["training_manager"],
            }
        }
        result = main.user_has_any_role(session, ["admin"])
        assert result is False, (
            "training_manager should NOT pass admin-only role checks"
        )

    def test_user_has_any_role_training_manager_not_sales(self):
        """training_manager should not pass sales role check."""
        import main
        session = {
            "user": {
                "id": "tm-001",
                "roles": ["training_manager"],
            }
        }
        result = main.user_has_any_role(session, ["sales", "sales_manager"])
        assert result is False, (
            "training_manager should NOT pass sales role checks"
        )

    def test_user_has_any_role_respects_impersonation_for_training_manager(self):
        """When training_manager impersonates sales, user_has_any_role should
        check against the impersonated role."""
        import main
        session = {
            "user": {
                "id": "tm-001",
                "roles": ["training_manager"],
            },
            "impersonated_role": "sales",
        }
        # Should match sales (impersonated), not training_manager (real)
        assert main.user_has_any_role(session, ["sales"]) is True
        assert main.user_has_any_role(session, ["training_manager"]) is False


# =============================================================================
# TEST 8: Edge cases
# =============================================================================

class TestTrainingManagerEdgeCases:
    """Edge cases for training_manager role."""

    # test_admin_badge_colors_include_training_manager (deleted) — tested the
    # badge_class dict in the /admin users-table rendering, which was archived
    # to legacy-fasthtml/admin_cluster.py in Phase 6C-2B Mega-E (2026-04-20).
    # No live surface renders training_manager badges in the Python app.

    def test_impersonation_dropdown_label_for_training_manager(self):
        """The impersonation dropdown default label should differ for training_manager
        vs admin. Admin sees 'Администратор (все права)', training_manager sees
        something different like 'Менеджер обучения (все разделы)'."""
        source = _read_main_py()

        sidebar_match = re.search(
            r'def sidebar\(session.*?\n(.*?)(?=\ndef |\nclass |\n@rt)',
            source,
            re.DOTALL
        )
        assert sidebar_match, "Could not find sidebar function"
        sidebar_body = sidebar_match.group(1)

        # There should be differentiated labels for admin vs training_manager
        # Look for conditional logic around the default option label
        has_differentiated_label = (
            "Менеджер обучения" in sidebar_body
            or "training_manager" in sidebar_body
        )
        assert has_differentiated_label, (
            "sidebar() does not have differentiated impersonation dropdown label "
            "for training_manager"
        )

    def test_training_manager_user_with_dual_roles(self):
        """A user with both admin and training_manager roles should work as admin."""
        import main
        session = {
            "user": {
                "id": "dual-001",
                "roles": ["admin", "training_manager"],
            }
        }
        # Should pass admin check
        assert main.user_has_any_role(session, ["admin"]) is True
        # Should also pass training_manager check
        assert main.user_has_any_role(session, ["training_manager"]) is True


# =============================================================================
# TEST 9 (deleted) — covered VALID_IMPERSONATION_ROLES privilege-escalation
# invariants; constant moved alongside /admin/impersonate route to
# legacy-fasthtml/admin_cluster.py in Phase 6C-2B Mega-E (2026-04-20).
# The security invariant is preserved in the archive (admin + training_manager
# not in the frozenset); no live Python surface consumes it anymore.
# =============================================================================
