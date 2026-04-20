"""
Tests for design audit bug C7.

C7: Admin FIO column shows UUIDs instead of names -- the admin users table
    column header says "FIO" but the code sets email_display = member_user_id[:8] + "..."
    instead of querying user_profiles for full_name.  Other code paths (e.g.,
    quote detail creator name, activity log) DO query user_profiles.full_name.
    Fix: query user_profiles table for each member to get their actual full_name.

These tests are written BEFORE the fix (TDD).
All tests MUST FAIL until the bugs are fixed.

Note: Former C6 tests (dashboard procurement error handling) were removed
during Phase 6C-2B-7 archive of /dashboard + /tasks (2026-04-20).
"""

import os
import re

# Path constants
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(_PROJECT_ROOT, "main.py")


def _read_main_source():
    """Read main.py source code without importing it."""
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        return f.read()


def _extract_admin_get_handler(source: str = None) -> str:
    """Extract the /admin GET handler source.

    The handler is defined as:
        @rt("/admin")
        def get(session):
    and runs until the next @rt or top-level def.
    """
    if source is None:
        source = _read_main_source()
    # Find the @rt("/admin") handler
    pattern = re.compile(
        r'(@rt\("/admin"\)\s*def get\(session\).*?)(?=\n@rt\(|\Z)',
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match, '/admin GET handler not found in main.py'
    return match.group(1)


# ==============================================================================
# C7: Admin FIO column shows UUIDs instead of names
# ==============================================================================

class TestC7AdminFIOShowsRealNames:
    """Admin users table must show actual user names from user_profiles,
    not truncated UUIDs.

    Current code (line ~27407):
        email_display = member_user_id[:8] + "..."

    The table header says "FIO" but displays "138311f7..." instead of
    the person's full_name from user_profiles table.

    Fix: query user_profiles table for each member's full_name and use
    that as the display value (falling back to truncated UUID only if
    no profile exists).
    """

    def test_admin_handler_queries_user_profiles(self):
        """The /admin handler must query user_profiles to get full_name."""
        handler_source = _extract_admin_get_handler()

        assert "user_profiles" in handler_source, (
            "The /admin GET handler does not query user_profiles table. "
            "It should fetch full_name from user_profiles for each member "
            "instead of showing truncated UUID (member_user_id[:8] + '...')."
        )

    def test_admin_handler_selects_full_name(self):
        """The user_profiles query must select full_name."""
        handler_source = _extract_admin_get_handler()

        # Check that full_name is selected from user_profiles
        has_full_name_query = (
            "full_name" in handler_source
            and "user_profiles" in handler_source
        )

        assert has_full_name_query, (
            "The /admin handler does not select full_name from user_profiles. "
            "The FIO column currently shows truncated UUIDs like '138311f7...'. "
            "It must query user_profiles.full_name for proper name display."
        )

    def test_admin_handler_does_not_use_truncated_uuid_as_primary_display(self):
        """The email_display should NOT be just member_user_id[:8] without profile lookup.

        The current code has:
            email_display = member_user_id[:8] + "..."

        as the ONLY display value. After the fix, truncated UUID should only
        be a fallback when user_profiles has no full_name.
        """
        handler_source = _extract_admin_get_handler()

        # Find all lines that set email_display
        email_display_assignments = re.findall(
            r'email_display\s*=\s*(.+)',
            handler_source,
        )

        assert email_display_assignments, (
            "Could not find email_display assignment in /admin handler."
        )

        # The primary (or only) assignment should NOT be just the truncated UUID
        # After the fix, there should be a profile lookup BEFORE the truncated fallback
        # Check that the FIRST assignment is NOT the truncated UUID pattern
        first_assignment = email_display_assignments[0].strip()
        is_only_truncated = (
            "[:8]" in first_assignment
            and "user_profiles" not in handler_source
        )

        # Also check: if truncated UUID is used, it must be guarded by profile lookup
        has_profile_before_truncation = False
        lines = handler_source.split('\n')
        for i, line in enumerate(lines):
            if 'user_profiles' in line:
                has_profile_before_truncation = True
            if '[:8]' in line and 'email_display' in line:
                break

        assert has_profile_before_truncation, (
            "email_display is set to truncated UUID (member_user_id[:8] + '...') "
            "without first querying user_profiles for full_name. "
            "The FIO column shows UUIDs like '138311f7...' instead of real names. "
            "Fix: query user_profiles.full_name BEFORE falling back to truncated UUID."
        )

    def test_admin_users_data_includes_full_name_field(self):
        """The users_data dict should include a name/full_name field from profiles."""
        handler_source = _extract_admin_get_handler()

        # The users_data.append({...}) should have a field sourced from profiles
        # Currently it only has "email": email_display which is a truncated UUID
        # After fix, it should have the profile name in the "email" field
        # or a dedicated "name"/"full_name" field

        # Check that between the user_profiles query and users_data.append,
        # the full_name value is used
        has_profile_name_in_data = (
            re.search(
                r'(?:full_name|profile.*name|name.*profile)',
                handler_source,
                re.IGNORECASE,
            )
            and "user_profiles" in handler_source
        )

        assert has_profile_name_in_data, (
            "users_data does not include full_name from user_profiles. "
            "The admin table FIO column displays truncated UUIDs because "
            "the code never fetches the user's actual name from profiles."
        )
