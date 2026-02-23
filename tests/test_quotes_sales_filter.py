"""
Tests for [86afmrkh9] Quotes registry for sales users with created_by filtering.

Two changes expected in main.py:
1. Sidebar: "Коммерческие предложения" link in Реестры section for sales/sales_manager/admin
2. GET /quotes: sales users see only quotes where created_by = their user_id;
   admin and top_manager see ALL org quotes (no filter)

Tests MUST FAIL before the feature is implemented (TDD).
"""

import os
import re

import pytest

# ---------------------------------------------------------------------------
# Helpers - read main.py source once
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(PROJECT_ROOT, "main.py")


@pytest.fixture(scope="module")
def main_source():
    """Read main.py source as a single string."""
    with open(MAIN_PY, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def main_lines():
    """Read main.py as list of lines (0-indexed)."""
    with open(MAIN_PY, "r") as f:
        return f.readlines()


def _find_registries_section(source: str):
    """
    Extract the registries section code block from sidebar builder.
    Returns the substring from '# === REGISTRIES SECTION' to the next
    '# ===' section marker (or end of function).
    """
    start = source.find("# === REGISTRIES SECTION")
    if start == -1:
        return ""
    # Find next section marker or a reasonable boundary
    next_section = source.find("# ===", start + 10)
    if next_section == -1:
        next_section = start + 2000  # fallback
    return source[start:next_section]


def _find_quotes_route_body(source: str):
    """
    Extract the GET /quotes handler body.
    Looks for @rt("/quotes") followed by def get(session) and grabs
    everything up to the next @rt( decorator.
    """
    # Find the @rt("/quotes") line followed by def get
    pattern = re.compile(
        r'@rt\("/quotes"\)\s*\ndef get\(session\)',
        re.MULTILINE,
    )
    match = pattern.search(source)
    if not match:
        return ""
    start = match.start()
    # Find next route decorator after start
    next_rt = re.search(r'\n@rt\(', source[start + 10:])
    if next_rt:
        end = start + 10 + next_rt.start()
    else:
        end = len(source)
    return source[start:end]


# ===========================================================================
# TEST CLASS 1: Sidebar - "Коммерческие предложения" in Реестры
# ===========================================================================

class TestSidebarQuotesRegistryLink:
    """
    Verify sidebar includes a "Коммерческие предложения" link
    in the Реестры section, visible to sales/sales_manager/admin roles.
    """

    def test_sidebar_has_quotes_registry_label(self, main_source):
        """
        The registries section must contain an item with label
        'Коммерческие предложения' pointing to /quotes.
        """
        registries = _find_registries_section(main_source)
        assert "Коммерческие предложения" in registries, (
            "Sidebar Реестры section does not contain "
            "'Коммерческие предложения' menu item. "
            "Expected a registries_items.append(...) with this label."
        )

    def test_sidebar_quotes_link_href(self, main_source):
        """
        The "Коммерческие предложения" sidebar item must link to /quotes.
        """
        registries = _find_registries_section(main_source)
        # Look for href pointing to /quotes near the label
        # Pattern: both label and href in the same append() call
        kp_block_pattern = re.compile(
            r'registries_items\.append\(\{[^}]*"label":\s*"Коммерческие предложения"[^}]*"href":\s*"/quotes"',
            re.DOTALL,
        )
        alt_pattern = re.compile(
            r'registries_items\.append\(\{[^}]*"href":\s*"/quotes"[^}]*"label":\s*"Коммерческие предложения"',
            re.DOTALL,
        )
        assert kp_block_pattern.search(registries) or alt_pattern.search(registries), (
            "Sidebar 'Коммерческие предложения' item does not have href='/quotes'. "
            f"Registries section excerpt:\n{registries[:500]}"
        )

    def test_sidebar_quotes_visible_for_sales_role(self, main_source):
        """
        The menu item guard must allow sales role.
        Expected: `if is_admin or any(r in roles for r in ["sales", "sales_manager"]):`
        immediately before the append of "Коммерческие предложения".
        """
        registries = _find_registries_section(main_source)
        # The guard should mention "sales" in the condition around the KP item
        # Check that sales is in the roles list for the KP item
        assert re.search(
            r'"roles":\s*\[.*"sales".*\].*"Коммерческие предложения"'
            r'|'
            r'"Коммерческие предложения".*"roles":\s*\[.*"sales".*\]',
            registries,
            re.DOTALL,
        ), (
            "Sidebar 'Коммерческие предложения' item does not list 'sales' in roles. "
            "Sales users must see this link."
        )

    def test_sidebar_quotes_visible_for_sales_manager_role(self, main_source):
        """
        The menu item must also be visible for sales_manager role.
        """
        registries = _find_registries_section(main_source)
        assert re.search(
            r'"roles":\s*\[.*"sales_manager".*\].*"Коммерческие предложения"'
            r'|'
            r'"Коммерческие предложения".*"roles":\s*\[.*"sales_manager".*\]',
            registries,
            re.DOTALL,
        ), (
            "Sidebar 'Коммерческие предложения' item does not list 'sales_manager' in roles."
        )

    def test_sidebar_quotes_not_visible_for_procurement_only(self, main_source):
        """
        Procurement-only users must NOT see the 'Коммерческие предложения' link.
        Verify the guard condition does NOT include 'procurement' as an allowed role.
        """
        registries = _find_registries_section(main_source)
        # Find the specific append block for KP
        kp_match = re.search(
            r'registries_items\.append\(\{[^}]*"Коммерческие предложения"[^}]*\}',
            registries,
            re.DOTALL,
        )
        if kp_match:
            kp_block = kp_match.group(0)
            assert "procurement" not in kp_block, (
                "Sidebar 'Коммерческие предложения' should NOT list 'procurement' in roles. "
                "Procurement-only users must not see this link."
            )
        else:
            pytest.fail(
                "Cannot find 'Коммерческие предложения' append block to verify "
                "procurement exclusion."
            )


# ===========================================================================
# TEST CLASS 2: GET /quotes - created_by filter for sales users
# ===========================================================================

class TestQuotesRouteCreatedByFilter:
    """
    Verify GET /quotes filters by created_by for sales users
    while admin/top_manager see all quotes.
    """

    def test_quotes_route_extracts_roles(self, main_source):
        """
        The /quotes GET handler must extract roles from user dict:
        `roles = user.get("roles", [])` or similar.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler in main.py"
        assert re.search(
            r'roles\s*=\s*user\.get\(\s*["\']roles["\']\s*,\s*\[\]\s*\)',
            route_body,
        ), (
            "GET /quotes handler does not extract roles from user dict. "
            "Expected: roles = user.get('roles', [])"
        )

    def test_quotes_route_determines_privileged_status(self, main_source):
        """
        The handler must determine if user is privileged (admin or top_manager)
        to decide whether to apply created_by filter.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for privileged check that includes both admin and top_manager
        assert re.search(
            r'(is_privileged|is_admin|privileged|see_all)',
            route_body,
        ), (
            "GET /quotes handler does not determine privileged/admin status. "
            "Expected a variable like is_privileged checking for admin/top_manager."
        )

    def test_quotes_route_applies_created_by_filter(self, main_source):
        """
        The handler must apply .eq("created_by", ...) filter for
        non-privileged (sales-only) users.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert '.eq("created_by"' in route_body or ".eq('created_by'" in route_body, (
            "GET /quotes handler does not apply .eq('created_by', ...) filter. "
            "Sales users should only see their own quotes."
        )

    def test_quotes_route_filter_uses_user_id(self, main_source):
        """
        The created_by filter must use the current user's ID.
        Expected: .eq("created_by", user["id"])
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'\.eq\(\s*["\']created_by["\']\s*,\s*user\[.id.\]',
            route_body,
        ), (
            "GET /quotes created_by filter does not use user['id']. "
            'Expected: .eq("created_by", user["id"])'
        )

    def test_quotes_route_filter_is_conditional(self, main_source):
        """
        The created_by filter must be conditional (only for non-privileged users).
        It should be inside an `if not is_privileged:` or similar guard.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # The filter should be conditional, not unconditional
        assert re.search(
            r'if\s+not\s+(is_privileged|is_admin|privileged|see_all)',
            route_body,
        ), (
            "GET /quotes created_by filter is not conditional. "
            "Expected: `if not is_privileged:` guard before .eq('created_by', ...). "
            "Admin and top_manager must see all quotes without filtering."
        )

    def test_quotes_route_privileged_includes_admin(self, main_source):
        """
        The privileged check must include 'admin' role so admins see all quotes.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for admin in the privileged determination
        assert re.search(
            r'["\'](admin)["\'].*(?:is_privileged|privileged|see_all)'
            r'|'
            r'(?:is_privileged|privileged|see_all).*["\'](admin)["\']',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes privileged check does not include 'admin' role. "
            "Admins must see all org quotes."
        )

    def test_quotes_route_privileged_includes_top_manager(self, main_source):
        """
        The privileged check must include 'top_manager' role.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'["\'](top_manager)["\'].*(?:is_privileged|privileged|see_all)'
            r'|'
            r'(?:is_privileged|privileged|see_all).*["\'](top_manager)["\']',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes privileged check does not include 'top_manager' role. "
            "Top managers must see all org quotes."
        )


# ===========================================================================
# TEST CLASS 3: Edge Cases
# ===========================================================================

class TestQuotesFilterEdgeCases:
    """
    Edge case verification via source code analysis.
    """

    def test_quotes_route_still_filters_by_org(self, main_source):
        """
        The organization_id filter must still be present regardless of
        the new created_by filter. All users should only see their own org's quotes.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert '.eq("organization_id"' in route_body or ".eq('organization_id'" in route_body, (
            "GET /quotes handler lost the organization_id filter. "
            "All users must still be scoped to their organization."
        )

    def test_quotes_route_query_is_built_before_conditional_filter(self, main_source):
        """
        The query should be built in stages: base query first, then conditional
        .eq("created_by") appended only for non-privileged users.
        This ensures admin/top_manager never have the filter applied.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # The org filter should come before the created_by conditional
        org_pos = route_body.find('.eq("organization_id"')
        if org_pos == -1:
            org_pos = route_body.find(".eq('organization_id'")
        created_pos = route_body.find('.eq("created_by"')
        if created_pos == -1:
            created_pos = route_body.find(".eq('created_by'")

        assert org_pos > 0, "organization_id filter not found in /quotes route"
        assert created_pos > 0, "created_by filter not found in /quotes route"
        assert org_pos < created_pos, (
            "organization_id filter must come before created_by filter in /quotes route. "
            "Base query (with org filter) is built first, then created_by is conditionally appended."
        )

    def test_dual_role_sales_admin_sees_all_quotes(self, main_source):
        """
        A user with both 'sales' and 'admin' roles should see all quotes
        because admin is privileged. Verify the privileged check uses
        `any(r in roles for r in ...)` pattern which will match admin
        even when sales is also present.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # The privileged check should be based on roles list, not exclusive match
        # It should use `any(... in roles ...)` or `"admin" in roles` pattern
        assert re.search(
            r'any\(.*["\']admin["\'].*roles'
            r'|'
            r'["\']admin["\']\s+in\s+roles',
            route_body,
        ), (
            "GET /quotes privileged check may not handle dual-role users correctly. "
            "Expected `any(r in roles for r in ['admin', 'top_manager'])` or "
            "`'admin' in roles` pattern that works when user has both sales and admin."
        )
