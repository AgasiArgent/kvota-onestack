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


def _find_function_body(source, func_name, max_chars=15000):
    """Find a function body in source code by name.

    Returns the function body text or None if not found.
    """
    pattern = rf'def {func_name}\(.*?\).*?:\s*\n(.*?)(?=\ndef |\nclass |\n@rt\(|\Z)'
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1)[:max_chars]
    return None


def _find_route_handler_body(source, route_pattern, method="get", max_chars=15000):
    """Find a route handler body by route pattern and HTTP method.

    Returns the handler body text or None.
    """
    escaped = re.escape(route_pattern).replace(r'\{', '{').replace(r'\}', '}')
    pattern = (
        r'@rt\(\s*["\']'
        + escaped
        + rf'["\']\s*\)\s*\ndef {method}\(.*?\).*?:\s*\n(.*?)(?=\n@rt\(|\ndef [a-z]|\Z)'
    )
    match = re.search(pattern, source, re.DOTALL)
    if match:
        return match.group(1)[:max_chars]
    return None



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



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
