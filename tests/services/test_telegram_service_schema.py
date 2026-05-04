"""Schema-drift regression tests for ``services/telegram_service.py``.

Phase 2c hotfix (see ``docs/plans/2026-05-04-customs-phase-b-hotfix-plan.md``)
removed three SELECTs that referenced the non-existent ``full_name`` column
on ``kvota.organization_members``. The fix routes the query through
``kvota.user_profiles`` (the canonical home for display names — already
used at line ~1451 of the same file).

These unit tests assert that every Supabase ``.select(...)`` literal issued
by the three notifier helpers consists exclusively of column names that
exist in the corresponding ``kvota.<table>`` row schema (lifted from
``frontend/src/shared/types/database.types.ts``).

The tests intentionally bypass real Telegram I/O — the helpers are async
and pre-empted by a missing-bot guard before any real send happens. We
care here only about which DB queries reach Supabase.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch


# --- Schema source-of-truth -------------------------------------------------


def _load_schema() -> dict[str, set[str]]:
    """Lift kvota schema column sets from database.types.ts via the project's lint."""
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from tools.check_select_columns import find_types_file, parse_database_types

    return parse_database_types(find_types_file())


SCHEMA = _load_schema()
VALID_USER_PROFILES_COLS = SCHEMA["user_profiles"]
VALID_QUOTES_COLS = SCHEMA["quotes"]


# --- Helpers ---------------------------------------------------------------


def _strip_embeds(literal: str) -> set[str]:
    """Top-level columns only (mirror what tools/check_select_columns.py does).

    Skips ``alias:fk(...)`` and other embed-style sub-selects.
    """
    out: set[str] = set()
    depth = 0
    buf = ""
    for ch in literal + ",":
        if ch == "(":
            depth += 1
            buf += ch
            continue
        if ch == ")":
            depth -= 1
            buf += ch
            continue
        if ch == "," and depth == 0:
            tok = buf.strip()
            buf = ""
            if not tok or tok == "*":
                continue
            if "(" in tok:
                continue
            if ":" in tok:
                tok = tok.split(":", 1)[1].strip()
            if not tok or "(" in tok:
                continue
            out.add(tok)
        else:
            buf += ch
    return out


def _assert_select_clean(
    recorded: dict[str, list[str]],
    table: str,
    valid: set[str],
) -> None:
    literals = recorded.get(table)
    assert literals, f"Expected at least one .select() call on {table!r}; got {recorded!r}"
    for lit in literals:
        cols = _strip_embeds(lit)
        diff = cols - valid
        assert not diff, f"Schema drift on {table}: {diff} not in valid columns. Literal: {lit!r}"


# --- Tests -----------------------------------------------------------------


def test_notify_quote_creator_of_status_change_quotes_select_clean():
    """The first SELECT (off ``quotes``) must contain only real columns."""
    from services import telegram_service

    recorded: dict[str, list[str]] = {}

    sb = MagicMock()

    def _table(name: str):
        recorded.setdefault(name, [])
        chain = MagicMock()

        def _select(literal: str):
            recorded[name].append(literal)
            sub = MagicMock()
            sub.eq.return_value = sub
            sub.execute.return_value = MagicMock(data=[])
            return sub

        chain.select.side_effect = _select
        return chain

    sb.table.side_effect = _table

    with patch.object(telegram_service, "get_supabase", return_value=sb):
        asyncio.run(
            telegram_service.notify_quote_creator_of_status_change(
                quote_id="q-1",
                old_status="draft",
                new_status="approved",
                actor_id="u-1",
            )
        )

    _assert_select_clean(recorded, "quotes", VALID_QUOTES_COLS)


def test_notify_quote_creator_of_status_change_actor_lookup_uses_user_profiles():
    """When actor_name is unset and the quote exists, the helper falls
    through to the actor-name fetch — must hit ``user_profiles`` not
    ``organization_members``.
    """
    from services import telegram_service

    recorded: dict[str, list[str]] = {}

    sb = MagicMock()

    def _table(name: str):
        recorded.setdefault(name, [])
        chain = MagicMock()

        def _select(literal: str):
            recorded[name].append(literal)
            sub = MagicMock()
            sub.eq.return_value = sub
            if name == "quotes":
                sub.execute.return_value = MagicMock(
                    data=[
                        {
                            "id": "q-1",
                            "idn": "Q-2026-1",
                            "created_by": "creator-id",
                            "organization_id": "org-1",
                            "customer": {"name": "Acme"},
                        }
                    ]
                )
            else:
                sub.execute.return_value = MagicMock(data=[])
            return sub

        chain.select.side_effect = _select
        return chain

    sb.table.side_effect = _table

    with patch.object(telegram_service, "get_supabase", return_value=sb):
        asyncio.run(
            telegram_service.notify_quote_creator_of_status_change(
                quote_id="q-1",
                old_status="draft",
                new_status="approved",
                actor_id="actor-not-creator",
            )
        )

    assert "user_profiles" in recorded, (
        f"Actor name lookup did not hit user_profiles. Recorded tables: "
        f"{list(recorded.keys())}"
    )
    assert "organization_members" not in recorded, (
        "Regression: actor name lookup still hits organization_members "
        "(which has no full_name column)."
    )
    _assert_select_clean(recorded, "user_profiles", VALID_USER_PROFILES_COLS)


def test_notify_creator_of_return_uses_user_profiles_for_actor_name():
    """The return-for-revision notifier — same shape as the status-change
    notifier — must also avoid ``organization_members.full_name``.
    """
    from services import telegram_service

    recorded: dict[str, list[str]] = {}

    sb = MagicMock()

    def _table(name: str):
        recorded.setdefault(name, [])
        chain = MagicMock()

        def _select(literal: str):
            recorded[name].append(literal)
            sub = MagicMock()
            sub.eq.return_value = sub
            if name == "quotes":
                sub.execute.return_value = MagicMock(
                    data=[
                        {
                            "id": "q-1",
                            "idn": "Q-2026-2",
                            "created_by": "creator-id",
                            "organization_id": "org-1",
                            "customer": {"name": "Acme"},
                        }
                    ]
                )
            else:
                sub.execute.return_value = MagicMock(data=[])
            return sub

        chain.select.side_effect = _select
        return chain

    sb.table.side_effect = _table

    with patch.object(telegram_service, "get_supabase", return_value=sb):
        asyncio.run(
            telegram_service.notify_creator_of_return(
                quote_id="q-1",
                actor_id="ctrl-1",
                comment="Please revise margin",
            )
        )

    assert "user_profiles" in recorded
    assert "organization_members" not in recorded
    _assert_select_clean(recorded, "user_profiles", VALID_USER_PROFILES_COLS)
