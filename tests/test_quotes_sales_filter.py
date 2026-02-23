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


# ===========================================================================
# TEST CLASS 2: GET /quotes handler signature — query params
# ===========================================================================

class TestQuotesRouteSignature:
    """
    Verify the GET /quotes handler accepts filter query parameters.
    """

    def test_handler_accepts_status_param(self, main_source):
        """
        GET /quotes handler must accept a `status` query parameter.
        Expected: def get(session, status: str = "", ...)
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Check for 'status: str' in the function signature
        sig_match = re.search(r'def get\([^)]*status\s*:\s*str\s*=\s*["\']["\']', route_body)
        assert sig_match, (
            "GET /quotes handler does not accept 'status: str = \"\"' parameter. "
            "Iteration 2 requires filter query params in the handler signature."
        )

    def test_handler_accepts_customer_id_param(self, main_source):
        """
        GET /quotes handler must accept a `customer_id` query parameter.
        Expected: def get(session, ..., customer_id: str = "", ...)
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sig_match = re.search(r'def get\([^)]*customer_id\s*:\s*str\s*=\s*["\']["\']', route_body)
        assert sig_match, (
            "GET /quotes handler does not accept 'customer_id: str = \"\"' parameter."
        )

    def test_handler_accepts_manager_id_param(self, main_source):
        """
        GET /quotes handler must accept a `manager_id` query parameter.
        Expected: def get(session, ..., manager_id: str = "", ...)
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sig_match = re.search(r'def get\([^)]*manager_id\s*:\s*str\s*=\s*["\']["\']', route_body)
        assert sig_match, (
            "GET /quotes handler does not accept 'manager_id: str = \"\"' parameter."
        )


# ===========================================================================
# TEST CLASS 3: is_sales_only logic replaces is_privileged
# ===========================================================================

class TestSalesOnlyDetection:
    """
    Verify the handler uses is_sales_only instead of is_privileged.
    sales-only = user's roles are a subset of {"sales", "sales_manager"}.
    Implemented as: bool(roles) and set(roles).issubset({"sales", "sales_manager"})
    """

    def test_handler_defines_is_sales_only(self, main_source):
        """
        The handler must define an is_sales_only variable (not is_privileged).
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(r'is_sales_only\s*=', route_body), (
            "GET /quotes handler does not define 'is_sales_only' variable. "
            "Iteration 2 replaces is_privileged with is_sales_only detection."
        )

    def test_sales_only_checks_sales_role(self, main_source):
        """
        is_sales_only must check for sales or sales_manager role presence.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # The is_sales_only calculation should reference "sales"
        # Find the line/block where is_sales_only is defined
        sales_only_match = re.search(r'is_sales_only\s*=\s*(.+)', route_body)
        assert sales_only_match, "Cannot find is_sales_only assignment"
        # The assignment or surrounding code should mention "sales"
        sales_only_context = route_body[
            max(0, sales_only_match.start() - 200):sales_only_match.end() + 200
        ]
        assert '"sales"' in sales_only_context or "'sales'" in sales_only_context, (
            "is_sales_only does not check for 'sales' role."
        )

    def test_sales_only_excludes_admin(self, main_source):
        """
        is_sales_only must be False when user has admin role (even with sales).
        The issubset({"sales", "sales_manager"}) pattern ensures that any role
        outside this set (like admin) makes is_sales_only False.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sales_only_match = re.search(r'is_sales_only\s*=\s*(.+)', route_body)
        assert sales_only_match, "Cannot find is_sales_only assignment"
        # Context around the assignment
        sales_only_context = route_body[
            max(0, sales_only_match.start() - 300):sales_only_match.end() + 300
        ]
        # The issubset pattern with {"sales", "sales_manager"} inherently excludes admin:
        # set(["sales", "admin"]).issubset({"sales", "sales_manager"}) == False
        assert "issubset" in sales_only_context, (
            "is_sales_only definition does not use issubset pattern. "
            "Expected: set(roles).issubset({\"sales\", \"sales_manager\"}) which "
            "inherently excludes admin (and all other non-sales roles)."
        )
        assert '"sales_manager"' in sales_only_context or "'sales_manager'" in sales_only_context, (
            "is_sales_only issubset does not include 'sales_manager' in the allowed set."
        )

    def test_sales_only_excludes_procurement(self, main_source):
        """
        is_sales_only must be False for procurement users.
        Procurement sees all quotes, not filtered by created_by.
        The issubset({"sales", "sales_manager"}) pattern ensures "procurement"
        is not in the allowed set, so a procurement user is never sales_only.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sales_only_match = re.search(r'is_sales_only\s*=\s*(.+)', route_body)
        assert sales_only_match, "Cannot find is_sales_only assignment"
        sales_only_context = route_body[
            max(0, sales_only_match.start() - 300):sales_only_match.end() + 300
        ]
        # The issubset pattern with only "sales" and "sales_manager" inherently
        # excludes procurement: set(["procurement"]).issubset({"sales", "sales_manager"}) == False
        assert "issubset" in sales_only_context, (
            "is_sales_only definition does not use issubset pattern. "
            "Expected: set(roles).issubset({\"sales\", \"sales_manager\"}) which "
            "inherently excludes procurement."
        )
        assert ('"sales"' in sales_only_context or "'sales'" in sales_only_context), (
            "is_sales_only issubset does not include 'sales' in the allowed set."
        )

    def test_sales_only_excludes_top_manager(self, main_source):
        """
        is_sales_only must be False for top_manager.
        The issubset({"sales", "sales_manager"}) pattern ensures "top_manager"
        is not in the allowed set, so a top_manager user is never sales_only.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sales_only_match = re.search(r'is_sales_only\s*=\s*(.+)', route_body)
        assert sales_only_match, "Cannot find is_sales_only assignment"
        sales_only_context = route_body[
            max(0, sales_only_match.start() - 300):sales_only_match.end() + 300
        ]
        # Verify the issubset pattern is used with the correct allowed set
        assert "issubset" in sales_only_context, (
            "is_sales_only definition does not use issubset pattern. "
            "Expected: set(roles).issubset({\"sales\", \"sales_manager\"}) which "
            "inherently excludes top_manager."
        )
        # Verify the allowed set contains exactly sales and sales_manager
        assert ('"sales_manager"' in sales_only_context or "'sales_manager'" in sales_only_context), (
            "is_sales_only issubset allowed set does not include 'sales_manager'."
        )

    def test_created_by_filter_uses_is_sales_only(self, main_source):
        """
        The created_by filter must be guarded by is_sales_only (not is_privileged).
        Expected: `if is_sales_only:` before .eq("created_by", ...)
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'if\s+is_sales_only\s*:',
            route_body,
        ), (
            "GET /quotes created_by filter is not guarded by 'if is_sales_only:'. "
            "Iteration 2 replaces 'if not is_privileged:' with 'if is_sales_only:'."
        )

    def test_no_is_privileged_variable(self, main_source):
        """
        Iteration 2: is_privileged should no longer be used in the /quotes handler.
        It was replaced by is_sales_only.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert not re.search(r'is_privileged\s*=', route_body), (
            "GET /quotes handler still uses 'is_privileged'. "
            "Iteration 2 replaces it with 'is_sales_only'."
        )


# ===========================================================================
# TEST CLASS 4: SELECT string includes created_by
# ===========================================================================

class TestSelectIncludesCreatedBy:
    """
    The Supabase SELECT string must include 'created_by' so that
    manager dropdown can be populated and manager_id filter can work.
    """

    def test_select_includes_created_by(self, main_source):
        """
        The .select(...) call in GET /quotes must include 'created_by'.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Find the .select() call
        select_match = re.search(r'\.select\(\s*["\']([^"\']+)["\']', route_body)
        assert select_match, "Cannot find .select() call in GET /quotes handler"
        select_string = select_match.group(1)
        assert "created_by" in select_string, (
            f"The .select() string does not include 'created_by'. "
            f"Found: .select(\"{select_string[:100]}...\"). "
            "created_by is needed for manager dropdown population and filtering."
        )


# ===========================================================================
# TEST CLASS 5: Filter bar UI
# ===========================================================================

class TestFilterBarUI:
    """
    Verify the filter bar is rendered in the /quotes page HTML output.
    """

    def test_filter_form_exists(self, main_source):
        """
        The handler must render a Form with method="get" and action="/quotes"
        for the filter bar.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for Form(..., method="get", action="/quotes") pattern
        assert re.search(
            r'Form\(',
            route_body,
        ), (
            "GET /quotes handler does not render a Form element for filters."
        )
        assert re.search(
            r'method\s*=\s*["\']get["\']',
            route_body,
        ), (
            "Filter form does not use method='get'."
        )
        assert re.search(
            r'action\s*=\s*["\']/?quotes["\']',
            route_body,
        ), (
            "Filter form does not have action='/quotes'."
        )

    def test_status_dropdown_exists(self, main_source):
        """
        The filter bar must include a Select element for status filtering.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for Select with name="status" or name containing status
        assert re.search(
            r'Select\([^)]*name\s*=\s*["\']status["\']',
            route_body,
            re.DOTALL,
        ) or re.search(
            r'name\s*=\s*["\']status["\'].*Select',
            route_body,
            re.DOTALL,
        ), (
            "Filter bar does not include a Select dropdown for 'status'."
        )

    def test_customer_dropdown_exists(self, main_source):
        """
        The filter bar must include a Select element for customer filtering.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'Select\([^)]*name\s*=\s*["\']customer_id["\']',
            route_body,
            re.DOTALL,
        ) or re.search(
            r'name\s*=\s*["\']customer_id["\'].*Select',
            route_body,
            re.DOTALL,
        ), (
            "Filter bar does not include a Select dropdown for 'customer_id'."
        )

    def test_manager_dropdown_exists(self, main_source):
        """
        The filter bar must include a Select element for manager filtering
        (only shown to non-sales-only users, but the code must exist).
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'Select\([^)]*name\s*=\s*["\']manager_id["\']',
            route_body,
            re.DOTALL,
        ) or re.search(
            r'name\s*=\s*["\']manager_id["\'].*Select',
            route_body,
            re.DOTALL,
        ), (
            "Filter bar does not include a Select dropdown for 'manager_id'."
        )

    def test_manager_dropdown_hidden_for_sales_only(self, main_source):
        """
        The manager dropdown must be conditionally shown — hidden for
        is_sales_only users. Expected: `if not is_sales_only:` or
        `None if is_sales_only` guard around manager Select.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Find manager_id Select and check for is_sales_only guard nearby
        manager_pos = route_body.find('manager_id')
        assert manager_pos > 0, "manager_id not found in route body"

        # Look for is_sales_only condition near the manager_id dropdown
        context = route_body[max(0, manager_pos - 300):manager_pos + 300]
        assert re.search(
            r'is_sales_only|not\s+is_sales_only',
            context,
        ), (
            "Manager dropdown is not conditionally hidden for sales-only users. "
            "Expected is_sales_only check near the manager_id Select."
        )


# ===========================================================================
# TEST CLASS 6: Python-side filtering logic
# ===========================================================================

class TestPythonSideFiltering:
    """
    Verify that filtered_quotes is built from quotes using the filter params.
    """

    def test_filtered_quotes_variable_exists(self, main_source):
        """
        The handler must create a filtered_quotes variable by applying
        status, customer_id, and manager_id filters to the quotes list.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert "filtered_quotes" in route_body, (
            "GET /quotes handler does not define 'filtered_quotes'. "
            "Python-side filtering must create filtered_quotes from the quotes list."
        )

    def test_status_filter_applied(self, main_source):
        """
        When status param is set, filtered_quotes must filter by workflow_status.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for status filtering logic
        assert re.search(
            r'(workflow_status|status).*status.*filtered|filtered.*status.*workflow_status'
            r'|'
            r'if\s+status\s*:.*workflow_status'
            r'|'
            r'workflow_status.*==.*status',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes handler does not filter by status parameter. "
            "Expected: filtering quotes by workflow_status when status param is set."
        )

    def test_customer_id_filter_applied(self, main_source):
        """
        When customer_id param is set, filtered_quotes must filter by customer_id.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'customer_id.*filtered|filtered.*customer_id'
            r'|'
            r'if\s+customer_id\s*:'
            r'|'
            r'customer_id.*==.*customer_id',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes handler does not filter by customer_id parameter."
        )

    def test_manager_id_filter_applied(self, main_source):
        """
        When manager_id param is set, filtered_quotes must filter by created_by.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert re.search(
            r'manager_id.*filtered|filtered.*manager_id'
            r'|'
            r'if\s+manager_id\s*:'
            r'|'
            r'created_by.*==.*manager_id',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes handler does not filter by manager_id parameter."
        )

    def test_reset_link_when_filters_active(self, main_source):
        """
        When any filter is active, a reset link/button should appear
        that clears all filters (links to /quotes without params).
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for a reset/clear link that appears conditionally
        assert re.search(
            r'(href\s*=\s*["\']/?quotes["\'].*[Сс]брос|[Сс]брос.*href\s*=\s*["\']/?quotes["\'])'
            r'|'
            r'([Rr]eset|[Сс]бросить|[Оо]чистить).*/?quotes'
            r'|'
            r'/?quotes["\'].*([Rr]eset|[Сс]бросить|[Оо]чистить|[Сс]брос)',
            route_body,
            re.DOTALL,
        ), (
            "GET /quotes handler does not show a reset/clear link when filters are active. "
            "Expected: a link to /quotes (without params) labeled 'Сбросить' or similar."
        )


# ===========================================================================
# TEST CLASS 7: Edge cases
# ===========================================================================

class TestQuotesFilterEdgeCases:
    """
    Edge case verification via source code analysis.
    """

    def test_quotes_route_still_filters_by_org(self, main_source):
        """
        The organization_id filter must still be present regardless of
        new filters. All users should only see their own org's quotes.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert '.eq("organization_id"' in route_body or ".eq('organization_id'" in route_body, (
            "GET /quotes handler lost the organization_id filter. "
            "All users must still be scoped to their organization."
        )

    def test_quotes_route_created_by_still_present(self, main_source):
        """
        The created_by filter (.eq) must still be applied for sales-only users.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        assert '.eq("created_by"' in route_body or ".eq('created_by'" in route_body, (
            "GET /quotes handler does not apply .eq('created_by', ...) filter. "
            "Sales-only users should only see their own quotes."
        )

    def test_dual_role_sales_admin_not_sales_only(self, main_source):
        """
        A user with both 'sales' and 'admin' roles should NOT be is_sales_only.
        The issubset pattern handles this correctly:
        set(["sales", "admin"]).issubset({"sales", "sales_manager"}) == False
        because "admin" is not in the allowed set.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        sales_only_match = re.search(r'is_sales_only\s*=\s*(.+)', route_body)
        assert sales_only_match, "Cannot find is_sales_only assignment"
        assignment_context = route_body[
            max(0, sales_only_match.start() - 100):sales_only_match.end() + 200
        ]
        # The issubset pattern ensures dual-role users (e.g. sales+admin) are NOT
        # sales_only, because set(["sales", "admin"]) is NOT a subset of
        # {"sales", "sales_manager"}
        assert "issubset" in assignment_context, (
            "is_sales_only does not use issubset pattern. "
            "Expected: set(roles).issubset({\"sales\", \"sales_manager\"}) "
            "which correctly handles dual-role users like sales+admin."
        )
        # Verify the allowed set is exactly {"sales", "sales_manager"}
        assert ('"sales"' in assignment_context or "'sales'" in assignment_context), (
            "is_sales_only issubset allowed set missing 'sales'."
        )
        assert ('"sales_manager"' in assignment_context or "'sales_manager'" in assignment_context), (
            "is_sales_only issubset allowed set missing 'sales_manager'."
        )

    def test_manager_dropdown_populated_from_created_by(self, main_source):
        """
        The manager dropdown options must be populated dynamically from
        the created_by values in the quotes (not hardcoded).
        There must be code that collects unique creator IDs/names from quotes
        to populate the manager_id Select options.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Must have BOTH: something collecting creators AND a manager_id Select
        has_creator_collection = re.search(
            r'set\(.*created_by|unique.*created_by|creators\s*=|manager_options|managers\s*=\s*\[',
            route_body,
        )
        has_manager_select = re.search(
            r'name\s*=\s*["\']manager_id["\']',
            route_body,
        )
        assert has_creator_collection and has_manager_select, (
            "Manager dropdown options are not populated from created_by values. "
            "Expected: (1) code collecting unique creators from quotes AND "
            "(2) a Select with name='manager_id' using those options."
        )

    def test_combined_filters_use_intersection(self, main_source):
        """
        When multiple filters are active, they must be applied as AND (intersection),
        not OR. Each filter narrows the result further.
        """
        route_body = _find_quotes_route_body(main_source)
        assert route_body, "Could not find GET /quotes route handler"
        # Look for sequential filtering pattern (each filter applied to previous result)
        # This is typically done with sequential list comprehensions or chained conditions
        has_sequential = re.search(
            r'filtered_quotes\s*=.*\n.*filtered_quotes\s*=',
            route_body,
        )
        has_chained_conditions = re.search(
            r'if\s+.*status.*and.*customer_id'
            r'|'
            r'if\s+.*customer_id.*and.*status',
            route_body,
        )
        has_multi_filter = re.search(
            r'if\s+status\s*:.*\n.*if\s+customer_id\s*:'
            r'|'
            r'if\s+customer_id\s*:.*\n.*if\s+status\s*:',
            route_body,
            re.DOTALL,
        )
        assert has_sequential or has_chained_conditions or has_multi_filter, (
            "Filters do not appear to be applied as AND (intersection). "
            "Each filter must narrow the result set further (sequential filtering)."
        )
