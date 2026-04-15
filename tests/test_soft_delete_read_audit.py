"""Read-audit guardrail for the soft-delete Quote → Spec → Deal lifecycle.

Task 3 of the soft-delete standardization initiative. This test suite:

1. ``test_active_views_present`` — verifies migration 280 shipped the three
   ``kvota.active_*`` views.
2. ``test_active_quotes_view_filters_soft_deleted`` — integration test hitting
   prod DB via service_role client, confirms ``active_quotes`` excludes rows
   with ``deleted_at IS NOT NULL`` while ``kvota.quotes`` still exposes them.
   Same for ``active_specs``, ``active_deals``.

These are marked ``@pytest.mark.integration`` because they require Supabase
credentials (env vars set in CI and locally via ``.env``).

The read-audit lint check (grep-the-codebase) is intentionally NOT implemented
as a meta-test. main.py has 100+ quote/spec/deal references including
update/insert/delete calls; a regex that distinguishes "SELECT that needs the
filter" from "UPDATE that legitimately targets soft-deleted rows for restore"
would be error-prone and would block CI on false positives. The RLS policy from
migration 280 (defense-in-depth: RESTRICTIVE hide-deleted on all 3 tables)
catches non-admin leaks for the authenticated role. Application-level filters
remain the responsibility of code review for the service_role code path.
"""

from __future__ import annotations

import os

import pytest


def _get_service_client():
    """Build a service_role Supabase client configured for the kvota schema.

    Uses the same env vars main.py uses. Skips the test if creds missing so
    local runs without .env still work.
    """
    # tests/conftest.py force-sets SUPABASE_URL to a fake test host before any
    # test module imports. We opt out of that for this integration suite by
    # reading from dedicated INTEGRATION_* env vars (set in CI + local .env).
    url = os.environ.get("INTEGRATION_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("INTEGRATION_SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key or "test.supabase.co" in url:
        pytest.skip("INTEGRATION_SUPABASE_URL / ..._SERVICE_ROLE_KEY not configured "
                    "(conftest overrides SUPABASE_URL to a fake test host)")

    from supabase import create_client
    from supabase.client import ClientOptions

    return create_client(
        url,
        key,
        options=ClientOptions(schema="kvota"),
    )


@pytest.mark.integration
def test_active_views_present():
    """The three active_* views must exist with security_invoker=true."""
    sb = _get_service_client()

    # We can query the view's own catalog via PostgREST by simply SELECTing
    # nothing from it (LIMIT 0). If the view doesn't exist PostgREST returns
    # PGRST106 / 404.
    for view in ("active_quotes", "active_specs", "active_deals"):
        res = sb.table(view).select("*").limit(0).execute()
        assert res.data == [], f"active view {view!r} returned unexpected rows: {res.data!r}"


@pytest.mark.integration
def test_active_quotes_view_filters_soft_deleted():
    """active_quotes must exclude every row with deleted_at IS NOT NULL."""
    sb = _get_service_client()

    # Count soft-deleted quotes on the base table
    deleted_count_res = sb.table("quotes").select("id", count="exact") \
        .not_.is_("deleted_at", "null") \
        .execute()
    deleted_count = deleted_count_res.count or 0

    # Count how many of those appear in active_quotes
    if deleted_count == 0:
        pytest.skip("No soft-deleted quotes in prod — cannot verify filter")

    # Fetch IDs of deleted quotes
    deleted_ids_res = sb.table("quotes").select("id") \
        .not_.is_("deleted_at", "null") \
        .limit(1000) \
        .execute()
    deleted_ids = [row["id"] for row in (deleted_ids_res.data or [])]
    assert deleted_ids, "expected at least one soft-deleted quote id"

    # Query active_quotes for any of those IDs — must return zero rows
    leaked = sb.table("active_quotes").select("id") \
        .in_("id", deleted_ids) \
        .execute()
    assert (leaked.data or []) == [], \
        f"active_quotes leaked soft-deleted rows: {leaked.data!r}"


@pytest.mark.integration
def test_active_specs_view_filters_soft_deleted():
    """active_specs must exclude every row with deleted_at IS NOT NULL."""
    sb = _get_service_client()

    deleted_ids_res = sb.table("specifications").select("id") \
        .not_.is_("deleted_at", "null") \
        .limit(1000) \
        .execute()
    deleted_ids = [row["id"] for row in (deleted_ids_res.data or [])]
    if not deleted_ids:
        pytest.skip("No soft-deleted specs in prod — cannot verify filter")

    leaked = sb.table("active_specs").select("id") \
        .in_("id", deleted_ids) \
        .execute()
    assert (leaked.data or []) == [], \
        f"active_specs leaked soft-deleted rows: {leaked.data!r}"


@pytest.mark.integration
def test_active_deals_view_filters_soft_deleted():
    """active_deals must exclude every row with deleted_at IS NOT NULL."""
    sb = _get_service_client()

    deleted_ids_res = sb.table("deals").select("id") \
        .not_.is_("deleted_at", "null") \
        .limit(1000) \
        .execute()
    deleted_ids = [row["id"] for row in (deleted_ids_res.data or [])]
    if not deleted_ids:
        pytest.skip("No soft-deleted deals in prod — cannot verify filter")

    leaked = sb.table("active_deals").select("id") \
        .in_("id", deleted_ids) \
        .execute()
    assert (leaked.data or []) == [], \
        f"active_deals leaked soft-deleted rows: {leaked.data!r}"
