"""
TDD Tests for P2.7+P2.8: Logistics -> Finance Page Integration

TASK: Move logistics feature from /deals/{deal_id} to /finance/{deal_id}.
HTMX endpoints need URL prefix change from /deals/ to /finance/.

Current state (pre-fix):
  - /deals/{deal_id} renders logistics tab with _deals_logistics_tab()
  - HTMX POST endpoints use /deals/{deal_id}/stages/... URLs
  - Form actions in _deals_logistics_tab() use /deals/ prefix
  - /finance/{deal_id} has NO logistics section

Target state (post-fix):
  1. /finance/{deal_id} renders a "LOGISTIKA" section with 7-stage accordion
  2. HTMX POST endpoints use /finance/{deal_id}/stages/... URLs
  3. /deals/{deal_id} redirects (301/303) to /finance/{deal_id}
  4. Form actions in _deals_logistics_tab() use /finance/ prefix

All tests MUST FAIL until the fix is implemented.
"""

import pytest
import re
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY) as f:
        return f.read()


def _find_function_body(source, func_name, max_chars=5000):
    """Find a function body in source code by name.

    Returns the function body text or None if not found.
    """
    pattern = rf'def {func_name}\(.*?\).*?:\s*\n(.*?)(?=\ndef |\nclass |\n@rt\(|\Z)'
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1)[:max_chars]
    return None


def _find_route_handler_body(source, route_pattern, method="get", max_chars=5000):
    """Find a route handler body by route pattern and HTTP method.

    Returns the handler body text or None.
    """
    escaped = re.escape(route_pattern).replace(r'\{', '{').replace(r'\}', '}')
    pattern = (
        rf'@rt\(\s*["\']'
        + escaped
        + rf'["\']\s*\)\s*\ndef {method}\(.*?\).*?:\s*\n(.*?)(?=\n@rt\(|\ndef [a-z]|\Z)'
    )
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1)[:max_chars]
    return None


# ==============================================================================
# PART 1: Finance page must render LOGISTIKA section
# ==============================================================================

class TestFinancePageRendersLogistics:
    """The /finance/{deal_id} page must show a logistics section."""

    def test_finance_page_contains_logistics_heading(self):
        """Finance page must contain the text 'LOGISTIKA' or 'Логистика' heading."""
        source = _read_main_source()
        # Find the finance/{deal_id} GET handler
        handler = _find_route_handler_body(source, "/finance/{deal_id}", "get")
        assert handler is not None, "GET /finance/{deal_id} handler not found"
        has_logistics = (
            "ЛОГИСТИКА" in handler
            or "Логистика" in handler
            or "_deals_logistics_tab" in handler
            or "logistics_tab" in handler
        )
        assert has_logistics, (
            "GET /finance/{deal_id} must render a logistics section "
            "(ЛОГИСТИКА heading or call _deals_logistics_tab). "
            "Currently only shows plan-fact table."
        )

    def test_finance_page_calls_logistics_tab_renderer(self):
        """Finance page must call _deals_logistics_tab() or equivalent."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/finance/{deal_id}", "get")
        assert handler is not None, "GET /finance/{deal_id} handler not found"
        has_call = (
            "_deals_logistics_tab" in handler
            or "get_stages_for_deal" in handler
            or "logistics_stages" in handler
        )
        assert has_call, (
            "GET /finance/{deal_id} must call _deals_logistics_tab() or "
            "get_stages_for_deal() to render the 7-stage logistics accordion."
        )

    def test_finance_page_renders_seven_stage_accordion(self):
        """Finance page handler or its helpers must reference logistics stage rendering."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/finance/{deal_id}", "get")
        assert handler is not None, "GET /finance/{deal_id} handler not found"
        # Check for stage-related rendering in the finance page handler
        has_stages = (
            "stage_cards" in handler
            or "stage_items" in handler
            or "STAGE_NAMES" in handler
            or "_deals_logistics_tab" in handler
        )
        assert has_stages, (
            "GET /finance/{deal_id} must render the 7-stage logistics accordion "
            "(either directly or via _deals_logistics_tab helper)."
        )


# ==============================================================================
# PART 2: HTMX POST endpoints must use /finance/ prefix
# ==============================================================================

class TestFinanceStageStatusRoute:
    """POST route for stage status must exist at /finance/{deal_id}/stages/{stage_id}/status."""

    def test_finance_stage_status_route_exists(self):
        """POST /finance/{deal_id}/stages/{stage_id}/status route must be defined."""
        source = _read_main_source()
        has_route = '/finance/{deal_id}/stages/{stage_id}/status' in source
        assert has_route, (
            "POST /finance/{deal_id}/stages/{stage_id}/status route must exist. "
            "Currently only /deals/{deal_id}/stages/{stage_id}/status exists."
        )

    def test_finance_stage_status_is_post_handler(self):
        """The finance stage status route must be a POST handler."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*["\']\/finance\/\{deal_id\}\/stages\/\{stage_id\}\/status["\']\s*\)\s*\ndef post\(',
            source,
            re.DOTALL,
        )
        assert match, (
            "POST handler at /finance/{deal_id}/stages/{stage_id}/status not found. "
            "Route must be defined with 'def post(' after @rt decorator."
        )


class TestFinanceStageExpensesRoute:
    """POST route for expenses must exist at /finance/{deal_id}/stages/{stage_id}/expenses."""

    def test_finance_stage_expenses_route_exists(self):
        """POST /finance/{deal_id}/stages/{stage_id}/expenses route must be defined."""
        source = _read_main_source()
        has_route = '/finance/{deal_id}/stages/{stage_id}/expenses' in source
        assert has_route, (
            "POST /finance/{deal_id}/stages/{stage_id}/expenses route must exist. "
            "Currently only /deals/{deal_id}/stages/{stage_id}/expenses exists."
        )

    def test_finance_stage_expenses_is_post_handler(self):
        """The finance stage expenses route must be a POST handler."""
        source = _read_main_source()
        match = re.search(
            r'@rt\(\s*["\']\/finance\/\{deal_id\}\/stages\/\{stage_id\}\/expenses["\']\s*\)\s*\ndef post\(',
            source,
            re.DOTALL,
        )
        assert match, (
            "POST handler at /finance/{deal_id}/stages/{stage_id}/expenses not found. "
            "Route must be defined with 'def post(' after @rt decorator."
        )


# ==============================================================================
# PART 3: /deals/{deal_id} must redirect to /finance/{deal_id}
# ==============================================================================

class TestDealsRedirectsToFinance:
    """GET /deals/{deal_id} must redirect to /finance/{deal_id}."""

    def test_deals_detail_redirects_to_finance(self):
        """GET /deals/{deal_id} handler must issue a redirect to /finance/{deal_id}."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/deals/{deal_id}", "get")
        assert handler is not None, "GET /deals/{deal_id} handler not found"
        has_redirect = (
            'RedirectResponse(f"/finance/{deal_id}"' in handler
            or "RedirectResponse(f'/finance/{deal_id}'" in handler
            or 'redirect.*finance.*deal_id' in handler.lower()
        )
        assert has_redirect, (
            "GET /deals/{deal_id} must redirect to /finance/{deal_id} "
            "(301 or 303). Currently it renders its own detail page with tabs."
        )

    def test_deals_detail_no_longer_renders_tabs(self):
        """GET /deals/{deal_id} must NOT render tab navigation (moved to finance)."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/deals/{deal_id}", "get")
        # If handler doesn't exist, that's fine -- route was fully replaced
        if handler is None:
            return
        has_tab_rendering = (
            'tab_items' in handler
            and 'tab_content' in handler
            and '_deals_logistics_tab' in handler
        )
        assert not has_tab_rendering, (
            "GET /deals/{deal_id} should no longer render tab navigation. "
            "It should redirect to /finance/{deal_id} instead."
        )

    def test_deals_detail_redirect_uses_correct_status_code(self):
        """Redirect from /deals/{deal_id} must use 301 or 303 status code."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/deals/{deal_id}", "get")
        if handler is None:
            return  # Route removed entirely is acceptable
        # Check for redirect with appropriate status code
        has_proper_redirect = (
            'status_code=301' in handler
            or 'status_code=303' in handler
        )
        # Must also reference /finance/
        references_finance = '/finance/' in handler
        assert has_proper_redirect and references_finance, (
            "GET /deals/{deal_id} redirect to /finance/ must use "
            "status_code=301 (permanent) or status_code=303 (see other)."
        )


# ==============================================================================
# PART 4: Form actions in _deals_logistics_tab must use /finance/ prefix
# ==============================================================================

class TestLogisticsTabFormActions:
    """Form actions inside _deals_logistics_tab() must use /finance/ prefix."""

    def test_status_form_action_uses_finance_prefix(self):
        """Status update form action must point to /finance/{deal_id}/stages/...."""
        source = _read_main_source()
        body = _find_function_body(source, "_deals_logistics_tab")
        assert body is not None, "_deals_logistics_tab function not found"
        # Check that the status form action uses /finance/ prefix
        has_finance_action = (
            'action=f"/finance/{deal_id}/stages/' in body
            or "action=f'/finance/{deal_id}/stages/" in body
        )
        assert has_finance_action, (
            "_deals_logistics_tab status form action must use /finance/ prefix. "
            "Currently uses: action=f\"/deals/{deal_id}/stages/{stage.id}/status\""
        )

    def test_no_inline_expense_form_in_logistics_tab(self):
        """Inline expense forms were removed — expenses are added via plan-fact tab."""
        source = _read_main_source()
        body = _find_function_body(source, "_deals_logistics_tab")
        assert body is not None, "_deals_logistics_tab function not found"
        # Inline expense forms were removed in favor of unified plan-fact interface
        has_inline_expense_form = (
            '/expenses' in body
            and 'action=' in body
        )
        assert not has_inline_expense_form, (
            "_deals_logistics_tab should NOT have inline expense forms. "
            "Expenses are now added via the plan-fact tab."
        )

    def test_no_deals_prefix_in_form_actions(self):
        """No form actions in _deals_logistics_tab should use /deals/ prefix."""
        source = _read_main_source()
        body = _find_function_body(source, "_deals_logistics_tab")
        assert body is not None, "_deals_logistics_tab function not found"
        has_deals_action = (
            'action=f"/deals/{deal_id}/stages/' in body
            or "action=f'/deals/{deal_id}/stages/" in body
        )
        assert not has_deals_action, (
            "_deals_logistics_tab still contains form actions with /deals/ prefix. "
            "All form actions must use /finance/ prefix instead."
        )


# ==============================================================================
# PART 5: Old /deals/ logistics HTMX routes removed or redirected
# ==============================================================================

class TestOldDealsLogisticsRoutesRemoved:
    """Old /deals/{deal_id}/tab/logistics and stage HTMX routes should be removed."""

    def test_old_deals_tab_logistics_removed(self):
        """GET /deals/{deal_id}/tab/logistics route should be removed or redirect."""
        source = _read_main_source()
        # Check if old route still exists as a full handler
        has_old_handler = bool(re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}\/tab\/logistics["\']\s*\)\s*\ndef get\(',
            source,
        ))
        if has_old_handler:
            # If it still exists, it must redirect to finance
            handler = _find_route_handler_body(
                source, "/deals/{deal_id}/tab/logistics", "get"
            )
            if handler:
                has_redirect = '/finance/' in handler and 'Redirect' in handler
                assert has_redirect, (
                    "GET /deals/{deal_id}/tab/logistics still exists as a full handler. "
                    "It should either be removed or redirect to /finance/{deal_id}."
                )
            else:
                pytest.fail(
                    "GET /deals/{deal_id}/tab/logistics route exists but handler body not found."
                )
        # If route doesn't exist at all, that's the desired state -- pass

    def test_old_deals_stage_expenses_route_removed(self):
        """POST /deals/{deal_id}/stages/{stage_id}/expenses should be removed or redirect."""
        source = _read_main_source()
        has_old_route = bool(re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}\/stages\/\{stage_id\}\/expenses["\']\s*\)\s*\ndef post\(',
            source,
        ))
        if has_old_route:
            # Old route still exists -- check if it redirects
            idx = source.find('/deals/{deal_id}/stages/{stage_id}/expenses')
            nearby = source[idx:idx + 1500]
            has_redirect = '/finance/' in nearby and 'Redirect' in nearby
            assert has_redirect, (
                "POST /deals/{deal_id}/stages/{stage_id}/expenses still exists. "
                "It should be removed or redirect to /finance/ equivalent."
            )

    def test_old_deals_stage_status_route_removed(self):
        """POST /deals/{deal_id}/stages/{stage_id}/status should be removed or redirect."""
        source = _read_main_source()
        has_old_route = bool(re.search(
            r'@rt\(\s*["\']\/deals\/\{deal_id\}\/stages\/\{stage_id\}\/status["\']\s*\)\s*\ndef post\(',
            source,
        ))
        if has_old_route:
            # Old route still exists -- check if it redirects
            idx = source.find('/deals/{deal_id}/stages/{stage_id}/status')
            nearby = source[idx:idx + 1500]
            has_redirect = '/finance/' in nearby and 'Redirect' in nearby
            assert has_redirect, (
                "POST /deals/{deal_id}/stages/{stage_id}/status still exists. "
                "It should be removed or redirect to /finance/ equivalent."
            )


# ==============================================================================
# PART 6: Redirect destinations in expense/status handlers use /finance/
# ==============================================================================

class TestExpenseStatusHandlerRedirects:
    """Expense and status POST handlers must redirect to /finance/ not /deals/."""

    def test_expense_handler_redirects_to_finance(self):
        """After adding expense, redirect must go to /finance/{deal_id}."""
        source = _read_main_source()
        # Look for the expense POST handler (could be under /finance/ or /deals/)
        # The redirects after processing must use /finance/ prefix
        expense_handlers = []
        for match in re.finditer(
            r'@rt\(\s*["\'].*?/stages/\{stage_id\}/expenses["\']\s*\)\s*\ndef post\(.*?\n(.*?)(?=\n@rt\(|\Z)',
            source,
            re.DOTALL,
        ):
            expense_handlers.append(match.group(1))

        assert expense_handlers, "No expense POST handler found"

        # At least one handler must redirect to /finance/ (not /deals/)
        any_finance_redirect = any(
            '/finance/{deal_id}' in h or "/finance/{deal_id}" in h
            for h in expense_handlers
        )
        assert any_finance_redirect, (
            "Expense POST handler must redirect to /finance/{deal_id} after processing. "
            "Currently redirects to /deals/{deal_id}?tab=logistics."
        )

    def test_status_handler_redirects_to_finance(self):
        """After updating status, redirect must go to /finance/{deal_id}."""
        source = _read_main_source()
        status_handlers = []
        for match in re.finditer(
            r'@rt\(\s*["\'].*?/stages/\{stage_id\}/status["\']\s*\)\s*\ndef post\(.*?\n(.*?)(?=\n@rt\(|\Z)',
            source,
            re.DOTALL,
        ):
            status_handlers.append(match.group(1))

        assert status_handlers, "No status POST handler found"

        any_finance_redirect = any(
            '/finance/{deal_id}' in h or "/finance/{deal_id}" in h
            for h in status_handlers
        )
        assert any_finance_redirect, (
            "Status POST handler must redirect to /finance/{deal_id} after processing. "
            "Currently redirects to /deals/{deal_id}?tab=logistics."
        )


# ==============================================================================
# PART 7: Tab links in _deals_logistics_tab use /finance/ prefix
# ==============================================================================

class TestDealsDetailTabLinks:
    """If /deals/{deal_id} still renders tabs, tab hrefs must use /finance/."""

    def test_tab_links_no_longer_point_to_deals(self):
        """Tab navigation links should not point to /deals/{deal_id}?tab=..."""
        source = _read_main_source()
        handler = _find_route_handler_body(source, "/deals/{deal_id}", "get")
        if handler is None:
            # Route removed entirely -- acceptable
            return
        has_deals_tab_links = (
            'href=f"/deals/{deal_id}?tab=' in handler
            or "href=f'/deals/{deal_id}?tab=" in handler
        )
        assert not has_deals_tab_links, (
            "Tab navigation links in /deals/{deal_id} handler still use /deals/ prefix. "
            "They should either be removed (redirect only) or point to /finance/."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
