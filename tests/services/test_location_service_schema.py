"""Schema-drift regression tests for ``services/location_service.py``.

Phase 2c hotfix: ``get_location_stats`` selected ``is_hub`` and
``is_customs_point`` from ``kvota.locations`` — those columns were dropped
in migration 287 in favour of the ``location_type`` enum. The fix selects
``location_type`` instead and computes hub/customs counts by enum value.

These tests assert the SELECT literal stays inside the canonical
``kvota.locations`` column set (lifted from
``frontend/src/shared/types/database.types.ts``) and that the new code
correctly counts hubs / customs from ``location_type``.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


def _load_schema() -> dict[str, set[str]]:
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root))
    from tools.check_select_columns import find_types_file, parse_database_types

    return parse_database_types(find_types_file())


SCHEMA = _load_schema()
VALID_LOCATIONS_COLS = SCHEMA["locations"]


def _strip_embeds(literal: str) -> set[str]:
    """Top-level columns (skip embed sub-selects + alias prefixes)."""
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
            if not tok or tok == "*" or "(" in tok:
                continue
            if ":" in tok:
                tok = tok.split(":", 1)[1].strip()
            if not tok or "(" in tok:
                continue
            out.add(tok)
        else:
            buf += ch
    return out


def test_get_location_stats_select_is_clean():
    """The SELECT issued by get_location_stats hits only real columns."""
    from services import location_service

    captured: list[str] = []

    sb = MagicMock()

    def _select(literal: str):
        captured.append(literal)
        sub = MagicMock()
        sub.eq.return_value = sub
        sub.execute.return_value = MagicMock(data=[])
        return sub

    sb.table.return_value.select.side_effect = _select

    with patch.object(location_service, "_get_supabase", return_value=sb):
        location_service.get_location_stats("org-uuid-1")

    assert captured, "get_location_stats did not issue any SELECT"
    cols = _strip_embeds(captured[0])
    assert cols, f"Empty column set parsed from {captured[0]!r}"
    diff = cols - VALID_LOCATIONS_COLS
    assert not diff, (
        f"Schema drift on kvota.locations: {diff} not in canonical column set. "
        f"Literal was: {captured[0]!r}"
    )


def test_get_location_stats_counts_hubs_and_customs_from_location_type():
    """Verify the new count derivation: hubs == count(location_type='hub'),
    customs_points == count(location_type='customs').
    """
    from services import location_service

    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        MagicMock(
            data=[
                {"is_active": True, "location_type": "hub", "country": "Россия"},
                {"is_active": True, "location_type": "customs", "country": "Россия"},
                {"is_active": False, "location_type": "hub", "country": "Китай"},
                {"is_active": True, "location_type": "supplier", "country": "Китай"},
                {"is_active": True, "location_type": "client", "country": "Турция"},
            ]
        )
    )

    with patch.object(location_service, "_get_supabase", return_value=sb):
        stats = location_service.get_location_stats("org-uuid-1")

    assert stats["total"] == 5
    assert stats["active"] == 4
    assert stats["inactive"] == 1
    assert stats["hubs"] == 2
    assert stats["customs_points"] == 1
    assert stats["by_country"]["Россия"] == 2
    assert stats["by_country"]["Китай"] == 2
    assert stats["by_country"]["Турция"] == 1


def test_get_location_stats_handles_empty_dataset():
    """Empty data → zero-filled stats dict, no exceptions."""
    from services import location_service

    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        MagicMock(data=[])
    )

    with patch.object(location_service, "_get_supabase", return_value=sb):
        stats = location_service.get_location_stats("org-uuid-1")

    assert stats == {
        "total": 0,
        "active": 0,
        "inactive": 0,
        "hubs": 0,
        "customs_points": 0,
        "by_country": {},
    }
