"""Tests for ``api.workspace._resolve_user_names`` — the 4-tier display-name
resolution chain backing the head-of-* analytics endpoints.

The function (api/workspace.py:135-201) mirrors the canonical pattern in
api/notes.py ``_resolve_author_profiles``. Resolution order:

  1. ``kvota.user_profiles.full_name``
  2. ``auth.users.user_metadata.full_name`` (via auth.admin.list_users)
  3. ``auth.users.user_metadata.name`` (via auth.admin.list_users)
  4. ``auth.users.email``
  5. ``"— Неизвестный логист"`` (localised fallback so the UI never renders
     a bare UUID for a head-of-*).

Errors in either lookup degrade gracefully — the function must never raise
or 500 the calling endpoint, and must log a warning instead. These tests
cover all five tiers + both error branches + the empty-input fast path.

Phase 5c — gap closure for pr-test-analyzer 5a review (2026-05-07).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from api.workspace import _UNKNOWN_USER_LABEL, _resolve_user_names


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_auth_user(
    uid: str,
    *,
    full_name: str | None = None,
    name: str | None = None,
    email: str | None = None,
) -> SimpleNamespace:
    """Build a stand-in for an ``auth.users`` row.

    Mirrors the duck-typed shape ``_resolve_user_names`` reads via
    ``getattr(u, "id", ...)`` etc. — id, user_metadata dict, and email.
    """
    metadata: dict[str, str] = {}
    if full_name is not None:
        metadata["full_name"] = full_name
    if name is not None:
        metadata["name"] = name
    return SimpleNamespace(id=uid, user_metadata=metadata, email=email)


def _make_sb(
    *,
    profile_rows: list[dict[str, Any]] | None = None,
    profile_error: Exception | None = None,
    auth_users: list[Any] | None = None,
    auth_error: Exception | None = None,
    list_users_returns_attr_users: bool = True,
) -> MagicMock:
    """Build a Supabase-shaped MagicMock with controllable behaviour.

    ``list_users_returns_attr_users`` toggles between the two iterable
    shapes the resolver tolerates: page object with a ``.users`` attribute
    (default, matches gotrue v2) vs. a bare iterable (older clients).
    """
    sb = MagicMock()

    # ----- sb.table("user_profiles").select(..).in_(..).execute() -----
    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "user_profiles":
            chain = tbl.select.return_value.in_.return_value
            if profile_error is not None:
                chain.execute.side_effect = profile_error
            else:
                chain.execute.return_value = SimpleNamespace(
                    data=profile_rows or []
                )
        else:  # pragma: no cover — we only mock user_profiles here
            raise AssertionError(f"unexpected table {name!r}")
        return tbl

    sb.table.side_effect = table_side_effect

    # ----- sb.auth.admin.list_users() -----
    if auth_error is not None:
        sb.auth.admin.list_users.side_effect = auth_error
    else:
        users = auth_users or []
        if list_users_returns_attr_users:
            sb.auth.admin.list_users.return_value = SimpleNamespace(users=users)
        else:
            sb.auth.admin.list_users.return_value = users

    return sb


# ---------------------------------------------------------------------------
# Resolution-order coverage (tier 1 → tier 5)
# ---------------------------------------------------------------------------


class TestResolutionOrder:
    """The 4-tier name chain must prefer profile → metadata.full_name →
    metadata.name → email → fallback, in that order."""

    def test_tier1_profile_full_name_wins(self):
        """When user_profiles.full_name is present, it wins regardless of
        what auth.users metadata or email say."""
        sb = _make_sb(
            profile_rows=[{"user_id": "u-1", "full_name": "Алиса Петрова"}],
            auth_users=[
                _make_auth_user(
                    "u-1",
                    full_name="Should Be Ignored",
                    email="ignored@example.com",
                )
            ],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "Алиса Петрова"}

    def test_tier2_falls_to_auth_metadata_full_name_when_profile_missing(self):
        """No user_profiles row → fall to user_metadata.full_name."""
        sb = _make_sb(
            profile_rows=[],
            auth_users=[
                _make_auth_user(
                    "u-1",
                    full_name="Метадата Имя",
                    email="meta@example.com",
                )
            ],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "Метадата Имя"}

    def test_tier3_falls_to_auth_metadata_name_when_full_name_missing(self):
        """No metadata.full_name but metadata.name present → use it."""
        sb = _make_sb(
            profile_rows=[],
            auth_users=[
                _make_auth_user(
                    "u-1",
                    name="Просто Имя",
                    email="meta@example.com",
                )
            ],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "Просто Имя"}

    def test_tier4_falls_to_email_when_no_metadata_names(self):
        """No metadata.full_name and no metadata.name → use email."""
        sb = _make_sb(
            profile_rows=[],
            auth_users=[_make_auth_user("u-1", email="user@example.com")],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "user@example.com"}

    def test_tier5_falls_to_unknown_label_when_user_missing_from_auth(self):
        """User not present in auth.users at all → Russian fallback label.

        Matches the head_of_* UX requirement that a stale UUID never leaks
        to the analytics dashboard (workspace.py docstring).
        """
        sb = _make_sb(profile_rows=[], auth_users=[])

        names = _resolve_user_names(sb, ["u-missing"])

        assert names == {"u-missing": _UNKNOWN_USER_LABEL}

    def test_blank_profile_full_name_skips_to_next_tier(self):
        """A user_profiles row whose full_name is just whitespace/empty
        must not block fallback to auth metadata — the implementation
        ``.strip()``s the value before accepting it."""
        sb = _make_sb(
            profile_rows=[{"user_id": "u-1", "full_name": "   "}],
            auth_users=[
                _make_auth_user(
                    "u-1",
                    full_name="From Auth Metadata",
                    email="x@example.com",
                )
            ],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "From Auth Metadata"}


# ---------------------------------------------------------------------------
# Edge cases & multi-user resolution
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_user_id_list_returns_empty_dict_without_calls(self):
        """Fast path: no input → no work done. Critically, neither the
        user_profiles nor auth.admin.list_users call must fire — that
        keeps batch endpoints with zero participants free of needless I/O.
        """
        sb = MagicMock()

        names = _resolve_user_names(sb, [])

        assert names == {}
        sb.table.assert_not_called()
        sb.auth.admin.list_users.assert_not_called()

    def test_resolves_mixed_tiers_across_multiple_users_in_one_call(self):
        """Single call resolves each user independently down their own
        tier — profile / metadata / email / fallback can coexist."""
        sb = _make_sb(
            profile_rows=[
                {"user_id": "u-prof", "full_name": "Профиль"}
            ],
            auth_users=[
                _make_auth_user("u-prof", email="prof@example.com"),
                _make_auth_user(
                    "u-meta", full_name="Метаданные", email="m@example.com"
                ),
                _make_auth_user("u-email", email="onlyemail@example.com"),
                # u-missing intentionally omitted from auth → fallback
            ],
        )

        names = _resolve_user_names(
            sb, ["u-prof", "u-meta", "u-email", "u-missing"]
        )

        assert names == {
            "u-prof": "Профиль",
            "u-meta": "Метаданные",
            "u-email": "onlyemail@example.com",
            "u-missing": _UNKNOWN_USER_LABEL,
        }

    def test_filters_auth_users_outside_the_requested_set(self):
        """list_users() typically returns the full org user table; the
        resolver must ignore users it wasn't asked about (avoid leaking
        names of users that aren't in the result)."""
        sb = _make_sb(
            profile_rows=[],
            auth_users=[
                _make_auth_user("u-asked", email="asked@example.com"),
                _make_auth_user("u-other", email="other@example.com"),
            ],
        )

        names = _resolve_user_names(sb, ["u-asked"])

        assert names == {"u-asked": "asked@example.com"}
        assert "u-other" not in names


# ---------------------------------------------------------------------------
# Failure modes — both lookups degrade gracefully + log warnings
# ---------------------------------------------------------------------------


class TestFailureModes:
    def test_profile_lookup_failure_falls_through_to_auth_and_logs(
        self, caplog: pytest.LogCaptureFixture
    ):
        """If user_profiles.execute() raises, the resolver must continue
        with the auth.users tier rather than 500 the request. The failure
        is observable through a logger.warning with the suffix of
        ``api.workspace``.
        """
        caplog.set_level(logging.WARNING, logger="api.workspace")

        sb = _make_sb(
            profile_error=RuntimeError("postgrest read failed"),
            auth_users=[
                _make_auth_user(
                    "u-1", full_name="Из Метаданных", email="x@example.com"
                )
            ],
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "Из Метаданных"}
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "user_profiles lookup failed" in r.getMessage()
        ]
        assert warnings, "expected user_profiles failure to be logged"

    def test_auth_list_users_failure_returns_unknown_label_and_logs(
        self, caplog: pytest.LogCaptureFixture
    ):
        """If auth.admin.list_users() raises, every user without a profile
        row degrades to the localised fallback. The failure is logged.
        Users WITH a profile row are unaffected.
        """
        caplog.set_level(logging.WARNING, logger="api.workspace")

        sb = _make_sb(
            profile_rows=[
                {"user_id": "u-with-profile", "full_name": "Профильный"}
            ],
            auth_error=RuntimeError("auth admin unavailable"),
        )

        names = _resolve_user_names(
            sb, ["u-with-profile", "u-no-profile"]
        )

        assert names == {
            "u-with-profile": "Профильный",
            "u-no-profile": _UNKNOWN_USER_LABEL,
        }
        warnings = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "failed to resolve user names" in r.getMessage()
        ]
        assert warnings, "expected auth.admin.list_users failure to be logged"

    def test_both_lookups_failing_returns_fallback_for_every_user(
        self, caplog: pytest.LogCaptureFixture
    ):
        """Total degradation path: profile and auth both fail. Every user
        must still resolve to the fallback (never raise), and both
        warnings must be logged."""
        caplog.set_level(logging.WARNING, logger="api.workspace")

        sb = _make_sb(
            profile_error=RuntimeError("db down"),
            auth_error=RuntimeError("auth down"),
        )

        names = _resolve_user_names(sb, ["u-a", "u-b"])

        assert names == {
            "u-a": _UNKNOWN_USER_LABEL,
            "u-b": _UNKNOWN_USER_LABEL,
        }
        messages = [r.getMessage() for r in caplog.records]
        assert any("user_profiles lookup failed" in m for m in messages)
        assert any("failed to resolve user names" in m for m in messages)


# ---------------------------------------------------------------------------
# Iterable-shape tolerance — defends the resolver's getattr(page, 'users')
# fallback chain.
# ---------------------------------------------------------------------------


class TestListUsersShapes:
    def test_handles_bare_iterable_shape_without_attr_users(self):
        """``list_users()`` may return either a paginated object exposing
        ``.users`` or, with older clients, a bare list. The resolver
        tolerates both via ``getattr(page, "users", None) or page or []``.
        """
        sb = _make_sb(
            profile_rows=[],
            auth_users=[_make_auth_user("u-1", email="x@example.com")],
            list_users_returns_attr_users=False,
        )

        names = _resolve_user_names(sb, ["u-1"])

        assert names == {"u-1": "x@example.com"}
