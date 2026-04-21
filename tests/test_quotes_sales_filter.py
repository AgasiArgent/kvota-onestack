"""
Tests for [86afmrkh9] Quotes registry — expanded with filter dropdowns and all-role access.

Iteration 2 changes (TDD — tests first, must FAIL before implementation):

1. Sidebar: "Коммерческие предложения" visible for ALL authenticated roles (not just sales/admin)
2. GET /quotes handler accepts query params: status, customer_id, manager_id (all str, default "")
3. is_sales_only logic replaces is_privileged:
   - sales-only = user's roles are a subset of {"sales", "sales_manager"}
   - implemented as: bool(roles) and set(roles).issubset({"sales", "sales_manager"})
   - sales-only users get created_by filter enforced server-side
4. Filter bar UI: Form with method="get" action="/quotes", Select dropdowns
5. Python-side filtering: filtered_quotes from quotes using status, customer_id, manager_id
6. created_by in Supabase SELECT string
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
    Looks for @rt("/quotes") followed by def get(...) and grabs
    everything up to the next @rt( decorator.
    """
    # Match handler with optional query params (iteration 2 adds status, customer_id, manager_id)
    pattern = re.compile(
        r'@rt\("/quotes"\)\s*\ndef get\(',
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
# TEST CLASS 1: Sidebar - "Коммерческие предложения" visible for ALL roles
# ===========================================================================

class TestSidebarQuotesAllRoles:
    """
    Iteration 2: Verify sidebar "Коммерческие предложения" link is visible
    for ALL authenticated roles, not just sales/sales_manager/admin.
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

    def test_sidebar_quotes_visible_for_all_roles(self, main_source):
        """
        Iteration 2: The KP item must be visible for ALL roles — not gated
        by a sales/sales_manager/admin condition. It should either have
        roles: None, no roles key, or be appended unconditionally
        (outside the `if is_admin or any(r in roles for r in ["sales"...])` block).
        """
        registries = _find_registries_section(main_source)
        # Find the KP append block
        kp_match = re.search(
            r'registries_items\.append\(\{[^}]*"Коммерческие предложения"[^}]*\}',
            registries,
            re.DOTALL,
        )
        assert kp_match, (
            "Cannot find 'Коммерческие предложения' append block in registries section."
        )
        kp_block = kp_match.group(0)

        # Option A: roles: None in the append dict
        has_roles_none = '"roles": None' in kp_block or "'roles': None" in kp_block
        # Option B: no "roles" key at all (visible to everyone)
        has_no_roles_key = '"roles"' not in kp_block and "'roles'" not in kp_block

        # Also check: the append must NOT be inside the sales-only if block.
        # Find where the KP append is relative to the sales-only guard.
        sales_guard = re.search(
            r'if\s+is_admin\s+or\s+any\(r\s+in\s+roles\s+for\s+r\s+in\s+\[.*"sales"',
            registries,
        )
        if sales_guard:
            # KP append should be AFTER this guard's block or at same indent level
            # (i.e., not indented under it).
            guard_end = sales_guard.end()
            kp_pos = registries.find("Коммерческие предложения")
            # Check indentation: if KP is at the same indent as the guard, it's outside
            guard_line_start = registries.rfind('\n', 0, sales_guard.start()) + 1
            guard_indent = len(registries[guard_line_start:sales_guard.start()])
            kp_line_start = registries.rfind('\n', 0, kp_pos) + 1
            kp_indent = len(registries[kp_line_start:kp_pos]) - len(registries[kp_line_start:kp_pos].lstrip())

            # If KP is more indented than the guard, it's inside the guard block
            is_inside_guard = kp_indent > guard_indent and kp_pos > sales_guard.start()
        else:
            # No sales guard found — that's fine, means KP is unconditional
            is_inside_guard = False

        assert has_roles_none or has_no_roles_key or not is_inside_guard, (
            "Sidebar 'Коммерческие предложения' is still gated by sales/admin roles. "
            "Iteration 2 requires it to be visible for ALL authenticated roles. "
            "Either set roles: None, remove the roles key, or move it outside the "
            "sales-only if block."
        )

    def test_sidebar_quotes_visible_for_procurement(self, main_source):
        """
        Iteration 2: Procurement users must now see the 'Коммерческие предложения' link.
        This is a change from iteration 1 where procurement was excluded.
        """
        registries = _find_registries_section(main_source)
        kp_match = re.search(
            r'registries_items\.append\(\{[^}]*"Коммерческие предложения"[^}]*\}',
            registries,
            re.DOTALL,
        )
        assert kp_match, (
            "Cannot find 'Коммерческие предложения' append block."
        )
        kp_block = kp_match.group(0)

        # Either roles includes procurement, OR roles is None, OR no roles key
        has_procurement = "procurement" in kp_block
        has_roles_none = '"roles": None' in kp_block or "'roles': None" in kp_block
        has_no_roles_key = '"roles"' not in kp_block and "'roles'" not in kp_block

        # Also check it's not inside a sales-only guard
        sales_guard_pattern = re.compile(
            r'if\s+is_admin\s+or\s+any\(r\s+in\s+roles\s+for\s+r\s+in\s+\[.*?"sales".*?\]\)',
            re.DOTALL,
        )
        kp_pos = registries.find("Коммерческие предложения")
        sales_guard = sales_guard_pattern.search(registries)
        outside_sales_guard = True
        if sales_guard and kp_pos > sales_guard.start():
            # Check if KP is indented under the guard (inside the block)
            guard_line_start = registries.rfind('\n', 0, sales_guard.start()) + 1
            kp_line_start = registries.rfind('\n', 0, kp_pos) + 1
            guard_indent = len(registries[guard_line_start:sales_guard.start()])
            kp_line = registries[kp_line_start:kp_pos]
            kp_indent = len(kp_line) - len(kp_line.lstrip())
            if kp_indent > guard_indent:
                outside_sales_guard = False

        assert has_procurement or has_roles_none or has_no_roles_key or outside_sales_guard, (
            "Sidebar 'Коммерческие предложения' does not allow procurement users. "
            "Iteration 2: ALL roles must see this link, including procurement."
        )

    def test_sidebar_quotes_visible_for_logistics(self, main_source):
        """
        Iteration 2: Logistics users must see the KP link.
        """
        registries = _find_registries_section(main_source)
        kp_match = re.search(
            r'registries_items\.append\(\{[^}]*"Коммерческие предложения"[^}]*\}',
            registries,
            re.DOTALL,
        )
        assert kp_match, "Cannot find KP append block."
        kp_block = kp_match.group(0)

        has_logistics = "logistics" in kp_block
        has_roles_none = '"roles": None' in kp_block or "'roles': None" in kp_block
        has_no_roles_key = '"roles"' not in kp_block and "'roles'" not in kp_block

        assert has_logistics or has_roles_none or has_no_roles_key, (
            "Sidebar 'Коммерческие предложения' does not allow logistics users. "
            "Iteration 2: ALL roles must see this link."
        )

    def test_sidebar_quotes_visible_for_finance(self, main_source):
        """
        Iteration 2: Finance users must see the KP link.
        """
        registries = _find_registries_section(main_source)
        kp_match = re.search(
            r'registries_items\.append\(\{[^}]*"Коммерческие предложения"[^}]*\}',
            registries,
            re.DOTALL,
        )
        assert kp_match, "Cannot find KP append block."
        kp_block = kp_match.group(0)

        has_finance = "finance" in kp_block
        has_roles_none = '"roles": None' in kp_block or "'roles': None" in kp_block
        has_no_roles_key = '"roles"' not in kp_block and "'roles'" not in kp_block

        assert has_finance or has_roles_none or has_no_roles_key, (
            "Sidebar 'Коммерческие предложения' does not allow finance users. "
            "Iteration 2: ALL roles must see this link."
        )


