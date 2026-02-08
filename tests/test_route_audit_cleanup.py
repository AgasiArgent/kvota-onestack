"""
Regression tests for route audit cleanup (2026-02-08).

Verifies:
1. /spec-control route exists and is referenced correctly (not /specifications)
2. Removed routes are actually gone (start-negotiation, items POST, locations/search/json)
3. Kept routes still exist (telegram webhook POST, documents DELETE)
4. v3.0 /customers GET at ~line 29861 is the only /customers handler
5. Enhanced /profile/{user_id} at ~line 31928 is the canonical GET handler
6. No dangling href="/specifications" links remain
"""

import os
import re

import pytest


# ============================================================================
# HELPER: Read main.py source
# ============================================================================

def _read_main_source():
    """Read main.py source as a string."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.read()


def _read_main_lines():
    """Read main.py source as a list of lines (1-indexed via enumerate)."""
    source_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
    with open(source_path, "r") as f:
        return f.readlines()


def _find_route_decorators(source, route_pattern):
    """Find all @rt() decorators matching a route pattern.

    Returns list of (line_number, line_text) tuples.
    """
    results = []
    for i, line in enumerate(source.splitlines(), 1):
        if re.search(route_pattern, line):
            results.append((i, line.strip()))
    return results


# ============================================================================
# TEST 1: /spec-control route exists and /specifications is gone
# ============================================================================

class TestSpecControlRouteExists:
    """Verify /spec-control is the canonical route, /specifications is gone."""

    def test_spec_control_route_is_registered(self):
        """At least one @rt('/spec-control') decorator must exist."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/spec-control"')
        assert len(decorators) >= 1, \
            "No @rt('/spec-control') route found in main.py"

    def test_spec_control_sub_routes_exist(self):
        """Sub-routes like /spec-control/create and /spec-control/{spec_id} must exist."""
        source = _read_main_source()
        create_routes = _find_route_decorators(source, r'@rt\("/spec-control/create/')
        detail_routes = _find_route_decorators(source, r'@rt\("/spec-control/\{spec_id\}"')
        assert len(create_routes) >= 1, "Missing /spec-control/create/{quote_id} route"
        assert len(detail_routes) >= 1, "Missing /spec-control/{spec_id} route"

    def test_no_specifications_route_registered(self):
        """No @rt('/specifications') route should exist (was renamed to /spec-control)."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/specifications"')
        assert len(decorators) == 0, \
            f"Found legacy @rt('/specifications') route at lines: {decorators}"

    def test_no_href_to_specifications(self):
        """No href='/specifications' or href="/specifications" links should remain."""
        source = _read_main_source()
        matches = re.findall(r'href=["\']\/specifications["\'/]', source)
        assert len(matches) == 0, \
            f"Found {len(matches)} dangling href to /specifications: {matches}"

    def test_nav_links_use_spec_control(self):
        """Navigation links should reference /spec-control, not /specifications."""
        source = _read_main_source()
        assert 'href="/spec-control"' in source, \
            "No navigation link to /spec-control found"


# ============================================================================
# TEST 2: Removed routes are actually gone
# ============================================================================

class TestRemovedRoutesAreGone:
    """Verify that dead/removed routes no longer exist in main.py."""

    def test_no_start_negotiation_route(self):
        """Route /quotes/{id}/start-negotiation was removed."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'start.negotiation')
        assert len(decorators) == 0, \
            f"Found start-negotiation route at: {decorators}"
        # Also check there are no references at all
        assert "start-negotiation" not in source, \
            "Found dangling reference to start-negotiation"

    def test_no_quotes_items_post_route(self):
        """Route POST /quotes/{id}/items was removed (only PATCH and bulk remain)."""
        source = _read_main_source()
        # Look for @rt("/quotes/{quote_id}/items") without /bulk or /{item_id}
        # The PATCH route /quotes/{quote_id}/items/{item_id} and /items/bulk should still exist
        pattern = r'@rt\("/quotes/\{quote_id\}/items"\)'
        decorators = _find_route_decorators(source, pattern)
        assert len(decorators) == 0, \
            f"Found bare /quotes/{{quote_id}}/items route (should be removed): {decorators}"

    def test_no_api_locations_search_json_route(self):
        """Route /api/locations/search/json was removed."""
        source = _read_main_source()
        assert "api/locations/search/json" not in source, \
            "Found dangling reference to /api/locations/search/json"

    def test_quotes_items_patch_still_exists(self):
        """PATCH /quotes/{quote_id}/items/{item_id} should still exist (not removed)."""
        source = _read_main_source()
        decorators = _find_route_decorators(
            source, r'@rt\("/quotes/\{quote_id\}/items/\{item_id\}".*PATCH'
        )
        assert len(decorators) >= 1, \
            "PATCH /quotes/{quote_id}/items/{item_id} is missing - should not have been removed"

    def test_quotes_items_bulk_still_exists(self):
        """POST /quotes/{quote_id}/items/bulk should still exist (not removed)."""
        source = _read_main_source()
        decorators = _find_route_decorators(
            source, r'@rt\("/quotes/\{quote_id\}/items/bulk"'
        )
        assert len(decorators) >= 1, \
            "POST /quotes/{quote_id}/items/bulk is missing - should not have been removed"


# ============================================================================
# TEST 3: Kept routes still exist
# ============================================================================

class TestKeptRoutesStillExist:
    """Verify routes that should have been kept are still present."""

    def test_telegram_webhook_route_exists(self):
        """POST /api/telegram/webhook must still exist."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/api/telegram/webhook"\)')
        assert len(decorators) >= 1, \
            "Missing /api/telegram/webhook route - it should not have been removed"

    def test_documents_delete_route_exists(self):
        """DELETE /api/documents/{document_id} must still exist."""
        source = _read_main_source()
        decorators = _find_route_decorators(
            source, r'@rt\("/api/documents/\{document_id\}".*DELETE'
        )
        assert len(decorators) >= 1, \
            "Missing DELETE /api/documents/{document_id} route"

    def test_telegram_webhook_handler_is_async(self):
        """Telegram webhook handler should be async (it processes request body)."""
        source = _read_main_source()
        idx = source.find('@rt("/api/telegram/webhook")')
        assert idx > 0
        handler_start = source[idx:idx + 300]
        assert "async def" in handler_start, \
            "Telegram webhook handler should be async"


# ============================================================================
# TEST 4: v3.0 /customers GET is the only handler
# ============================================================================

class TestCustomersRouteConsolidation:
    """Verify there is exactly one /customers GET handler (v3.0)."""

    def test_single_customers_route(self):
        """There should be exactly one @rt('/customers') decorator."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/customers"\)$')
        assert len(decorators) == 1, \
            f"Expected exactly 1 @rt('/customers'), found {len(decorators)}: {decorators}"

    def test_customers_route_is_v3(self):
        """The /customers handler should be the v3.0 version (after line 25000)."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/customers"\)$')
        assert len(decorators) == 1
        line_no = decorators[0][0]
        # v3.0 should be well past the midpoint of the file (~35k lines)
        assert line_no > 25000, \
            f"@rt('/customers') at line {line_no} seems too early - expected v3.0 version (>25000)"

    def test_customers_handler_has_search_params(self):
        """v3.0 customers handler supports q (search) and status filter params."""
        source = _read_main_source()
        idx = source.find('@rt("/customers")')
        assert idx > 0
        handler_sig = source[idx:idx + 300]
        assert "q: str" in handler_sig, "Customers handler missing search param 'q'"
        assert "status: str" in handler_sig, "Customers handler missing 'status' filter param"


# ============================================================================
# TEST 5: Enhanced /profile/{user_id} GET is canonical
# ============================================================================

class TestProfileRouteConsolidation:
    """Verify the enhanced /profile/{user_id} GET handler exists."""

    def test_profile_route_exists(self):
        """At least one @rt('/profile/{user_id}') must exist."""
        source = _read_main_source()
        decorators = _find_route_decorators(source, r'@rt\("/profile/\{user_id\}"\)$')
        assert len(decorators) >= 1, \
            "No @rt('/profile/{user_id}') route found"

    def test_profile_get_handler_has_tab_support(self):
        """The profile GET handler should support tab parameter."""
        source = _read_main_source()
        # Find the GET handler (has tab parameter)
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if '@rt("/profile/{user_id}")' in line:
                # Check next few lines for the function signature
                handler_area = "\n".join(lines[i:i + 5])
                if "tab:" in handler_area and "def get" in handler_area:
                    return  # Found the enhanced handler
        pytest.fail("No profile GET handler with tab support found")

    def test_profile_edit_field_routes_exist(self):
        """Profile edit-field and update-field sub-routes should exist."""
        source = _read_main_source()
        edit_routes = _find_route_decorators(
            source, r'@rt\("/profile/\{user_id\}/edit-field/'
        )
        update_routes = _find_route_decorators(
            source, r'@rt\("/profile/\{user_id\}/update-field/'
        )
        assert len(edit_routes) >= 1, "Missing /profile/{user_id}/edit-field route"
        assert len(update_routes) >= 1, "Missing /profile/{user_id}/update-field route"


# ============================================================================
# TEST 6: No orphaned route references in navigation/links
# ============================================================================

class TestNoOrphanedReferences:
    """Verify no links point to routes that no longer exist."""

    def test_no_href_start_negotiation(self):
        """No links should reference start-negotiation."""
        source = _read_main_source()
        matches = re.findall(r'href=["\'][^"\']*start-negotiation[^"\']*["\']', source)
        assert len(matches) == 0, \
            f"Found {len(matches)} links to start-negotiation: {matches}"

    def test_no_href_locations_search_json(self):
        """No links should reference /api/locations/search/json."""
        source = _read_main_source()
        assert "/api/locations/search/json" not in source, \
            "Found reference to removed /api/locations/search/json"

    def test_spec_control_links_are_consistent(self):
        """All spec-control hrefs should use the /spec-control prefix."""
        source = _read_main_source()
        # Find all spec-related hrefs
        spec_hrefs = re.findall(r'href="(/spec[^"]*)"', source)
        for href in spec_hrefs:
            assert href.startswith("/spec-control"), \
                f"Found non-standard spec href: {href}"
