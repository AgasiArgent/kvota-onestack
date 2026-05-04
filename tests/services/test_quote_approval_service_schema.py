"""Schema-drift regression test for ``services/quote_approval_service.py``.

Phase 2c hotfix: ``get_quotes_pending_approval`` selected ``customer_name``
directly from ``kvota.quotes`` — the column lives on ``customers``, not
``quotes``. The fix uses a PostgREST embed (``customer:customers(name)``)
and flattens the embedded value back onto each row so existing consumers
that look up ``quote['customer_name']`` keep working.
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
VALID_QUOTES_COLS = SCHEMA["quotes"]


def _strip_embeds(literal: str) -> set[str]:
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


def _make_recording_supabase(rows: list[dict]):
    captured: list[str] = []

    sb = MagicMock()
    chain = MagicMock()

    def _select(literal: str):
        captured.append(literal)
        sub = MagicMock()
        sub.eq.return_value = sub
        sub.in_.return_value = sub
        sub.order.return_value = sub
        sub.limit.return_value = sub
        sub.execute.return_value = MagicMock(data=rows)
        return sub

    chain.select.side_effect = _select
    sb.table.return_value = chain
    return sb, captured


def test_get_quotes_pending_approval_select_is_clean():
    """The SELECT issued by get_quotes_pending_approval contains only real
    ``kvota.quotes`` top-level columns (the embedded ``customers(name)``
    sub-select is not validated against the parent table).
    """
    from services import quote_approval_service

    sb, captured = _make_recording_supabase([])
    with patch.object(quote_approval_service, "get_supabase", return_value=sb):
        # 'procurement' is one of the valid DEPARTMENTS values.
        quote_approval_service.get_quotes_pending_approval(
            organization_id="org-1",
            department="procurement",
        )

    assert captured, "get_quotes_pending_approval did not issue any SELECT"
    cols = _strip_embeds(captured[0])
    diff = cols - VALID_QUOTES_COLS
    assert not diff, (
        f"Schema drift on kvota.quotes: {diff} not in canonical column set. "
        f"Literal was: {captured[0]!r}"
    )


def test_get_quotes_pending_approval_flattens_customer_name():
    """The function flattens ``quote.customer.name`` onto ``quote.customer_name``
    so downstream consumers continue to work without code changes.
    """
    from services import quote_approval_service

    rows = [
        {
            "id": "q-1",
            "idn_quote": "Q-2026-001",
            "total_amount": 1000.00,
            "currency": "RUB",
            "status": "pending_procurement",
            # No prior procurement approval → can_department_approve('procurement') is True.
            "approvals": {},
            "created_at": "2026-05-01T10:00:00+00:00",
            "customer": {"name": "Acme Corp"},
        }
    ]

    sb, _ = _make_recording_supabase(rows)
    with patch.object(quote_approval_service, "get_supabase", return_value=sb):
        result = quote_approval_service.get_quotes_pending_approval(
            organization_id="org-1",
            department="procurement",
        )

    assert len(result) == 1
    quote = result[0]
    assert quote["customer_name"] == "Acme Corp"
    assert quote["department"] == "procurement"


def test_get_quotes_pending_approval_handles_null_customer_embed():
    """When the customer FK is null (e.g. orphan quote), the flattened
    ``customer_name`` should be None, not raise.
    """
    from services import quote_approval_service

    rows = [
        {
            "id": "q-2",
            "idn_quote": "Q-2026-002",
            "total_amount": 500.00,
            "currency": "RUB",
            "status": "pending_procurement",
            "approvals": {},
            "created_at": "2026-05-02T10:00:00+00:00",
            "customer": None,  # PostgREST returns None when FK is null
        }
    ]

    sb, _ = _make_recording_supabase(rows)
    with patch.object(quote_approval_service, "get_supabase", return_value=sb):
        result = quote_approval_service.get_quotes_pending_approval(
            organization_id="org-1",
            department="procurement",
        )

    assert len(result) == 1
    assert result[0]["customer_name"] is None
