"""
Regression tests for route audit cleanup (2026-02-08).

Verifies:
1. /spec-control route exists and is referenced correctly (not /specifications)
2. Removed routes are actually gone (start-negotiation, items POST, locations/search/json)
3. Kept routes still exist (telegram webhook POST, documents DELETE)
4. (removed) /customers route consolidation — archived in Phase 6C-2B-1 (2026-04-20)
5. (removed) /profile/{user_id} route consolidation — archived in Phase 6C-2B-4 (2026-04-20)
6. No dangling href="/specifications" links remain
"""

import os
import re


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
# TEST 1: /spec-control route audit — REMOVED
# ============================================================================
# TestSpecControlRouteExists class removed in Phase 6C-2B Mega-B — the
# /spec-control routes were archived to legacy-fasthtml/control_flow.py.
# The sidebar `href="/spec-control"` nav link remains (dead link post-Caddy
# cutover, safe) and its presence is still implicitly exercised by
# TestNoOrphanedReferences.test_spec_control_links_are_consistent below.


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


# ============================================================================
# TEST 3: Kept routes still exist
# ============================================================================

class TestKeptRoutesStillExist:
    """Verify routes that should have been kept are still present."""

    def test_telegram_webhook_route_exists(self):
        """POST /api/telegram/webhook must still be registered on the FastAPI sub-app.

        Phase 6B-8: the @rt("/api/telegram/webhook") decorator was removed from
        main.py and the endpoint was extracted to api.routers.integrations.
        The route must still be reachable via the /api mount.
        """
        from api.routers.integrations import router as integrations_router

        paths = {route.path for route in integrations_router.routes}
        assert "/telegram/webhook" in paths, (
            "Missing /telegram/webhook on integrations router — "
            "should be registered at /api/telegram/webhook after Phase 6B-8 extraction"
        )

    def test_documents_delete_route_exists(self):
        """DELETE /api/documents/{document_id} must still be registered.

        Phase 6B-9: moved from a main.py ``@rt`` decorator to the FastAPI
        sub-app (``api.routers.documents``). Verify it's reachable via the
        /api mount.
        """
        from api.routers.documents import router as documents_router

        routes_with_methods = {
            (route.path, method)
            for route in documents_router.routes
            for method in getattr(route, "methods", set())
        }
        assert ("/{document_id}", "DELETE") in routes_with_methods, (
            "Missing DELETE /{document_id} on documents router — "
            "should be registered at /api/documents/{document_id} after "
            "Phase 6B-9 extraction"
        )

    def test_telegram_webhook_handler_is_async(self):
        """Telegram webhook handler should be async (it processes request body).

        Phase 6B-8: handler moved to api.integrations.telegram_webhook.
        """
        import inspect

        from api.integrations import telegram_webhook

        assert inspect.iscoroutinefunction(telegram_webhook), \
            "api.integrations.telegram_webhook must be async (handles request body)"


# ============================================================================
# TEST 4: /customers route consolidation — REMOVED
# ============================================================================
# The /customers FastHTML route was archived to legacy-fasthtml/customers.py
# in Phase 6C-2B-1 (2026-04-20). The Next.js app now serves /customers.


# ============================================================================
# TEST 5: /profile/{user_id} route consolidation — REMOVED
# ============================================================================
# The /profile + /profile/{user_id} FastHTML routes were archived to
# legacy-fasthtml/settings_profile.py in Phase 6C-2B-4 (2026-04-20). The
# Next.js app now serves /profile.


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
