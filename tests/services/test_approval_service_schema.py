"""Schema-drift regression tests for ``services/approval_service.py``.

Phase 2c hotfix:

* ``process_approval_decision`` selected ``customer_name`` from ``kvota.quotes``
  (the column lives on ``customers``, not ``quotes``). The fix uses a
  PostgREST embed: ``customer:customers(name)``.
* ``apply_modifications_to_quote`` read AND wrote a ``variables`` JSONB
  column on ``kvota.quotes`` that no longer exists. The new home is
  ``quote_versions.input_variables`` (Phase 5d migration). The fix merges
  ``margin_percent`` + ``manager_modified`` into the latest version's
  ``input_variables`` JSONB.

These tests assert that every Supabase ``.select(...)`` literal sits
inside the canonical column set, and that the writes target the right
table.
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
VALID_QUOTE_VERSIONS_COLS = SCHEMA["quote_versions"]


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


# --- Tests for process_approval_decision quote-fetch SELECT ---------------


def _make_recording_supabase(table_data: dict[str, list[dict]]):
    """Mock supabase that records each SELECT literal per table and returns
    pre-canned data on ``.execute()``.
    """
    state = {"recorded": {}, "table": None}

    sb = MagicMock()

    def _table(name: str):
        state["table"] = name
        state["recorded"].setdefault(name, [])

        chain = MagicMock()

        def _select(literal: str):
            state["recorded"][name].append(literal)
            sub = MagicMock()
            sub.eq.return_value = sub
            sub.order.return_value = sub
            sub.limit.return_value = sub
            sub.in_.return_value = sub
            sub.neq.return_value = sub
            sub.gte.return_value = sub
            sub.execute.return_value = MagicMock(data=table_data.get(name, []))
            return sub

        chain.select.side_effect = _select
        # Update path: not recorded, just succeeds.
        upd = MagicMock()
        upd.eq.return_value = upd
        upd.execute.return_value = MagicMock(data=[{"ok": True}])
        chain.update.return_value = upd
        return chain

    sb.table.side_effect = _table
    return sb, state["recorded"]


def test_process_approval_decision_quote_select_is_clean():
    """The SELECT in process_approval_decision must use only real
    ``kvota.quotes`` columns + a customer embed.
    """
    from services import approval_service
    from services.approval_service import Approval
    from datetime import datetime, timezone

    # Build a pending approval so we proceed past the early-return guards.
    mock_approval = Approval(
        id="approval-1",
        quote_id="quote-1",
        requested_by="u-1",
        approver_id="u-2",
        approval_type="top_manager",
        reason="Test",
        status="pending",
        decision_comment=None,
        requested_at=datetime.now(timezone.utc),
        decided_at=None,
    )

    sb, recorded = _make_recording_supabase(
        {
            "quotes": [
                {
                    "idn": "Q-1",
                    "created_by": "creator-1",
                    "customer": {"name": "Acme"},
                }
            ]
        }
    )

    # Patch get_supabase + get_approval + workflow helpers so the function
    # reaches the SELECT we care about and then short-circuits cleanly.
    # ``transition_quote_status`` and ``get_quote_workflow_status`` are
    # imported locally inside ``process_approval_decision`` from
    # ``services.workflow_service``, so we patch them at their origin.
    from services import workflow_service as _ws

    with patch.object(approval_service, "get_supabase", return_value=sb), \
         patch.object(approval_service, "get_approval", return_value=mock_approval), \
         patch.object(approval_service, "update_approval_status", return_value=mock_approval), \
         patch.object(_ws, "get_quote_workflow_status",
                      return_value=_ws.WorkflowStatus.PENDING_APPROVAL), \
         patch.object(_ws, "transition_quote_status",
                      return_value=MagicMock(success=False, error_message="stub-stop")):
        approval_service.process_approval_decision(
            approval_id="approval-1",
            decision="approved",
        )

    quote_selects = recorded.get("quotes", [])
    assert quote_selects, f"No SELECT recorded on quotes; got {recorded!r}"
    for lit in quote_selects:
        cols = _strip_embeds(lit)
        diff = cols - VALID_QUOTES_COLS
        assert not diff, (
            f"Schema drift on kvota.quotes: {diff} not in canonical column set. "
            f"Literal was: {lit!r}"
        )


# --- Tests for apply_modifications_to_quote variables flow ----------------


def test_apply_modifications_writes_margin_to_quote_versions_not_quotes():
    """``margin_percent`` must merge into ``quote_versions.input_variables``
    rather than touching the dropped ``quotes.variables`` column.
    """
    from services import approval_service

    state: dict[str, list] = {"quote_versions_select": [], "quote_versions_update": []}

    sb = MagicMock()

    def _table(name: str):
        chain = MagicMock()

        if name == "quote_versions":
            def _select(literal: str):
                state["quote_versions_select"].append(literal)
                sub = MagicMock()
                sub.eq.return_value = sub
                sub.order.return_value = sub
                sub.limit.return_value = sub
                sub.execute.return_value = MagicMock(
                    data=[{"id": "ver-1", "input_variables": {"existing": True}}]
                )
                return sub

            chain.select.side_effect = _select

            def _update(payload):
                state["quote_versions_update"].append(payload)
                upd = MagicMock()
                upd.eq.return_value = upd
                upd.execute.return_value = MagicMock(data=[{"ok": True}])
                return upd

            chain.update.side_effect = _update
        else:
            # quotes table — accept any update, return empty for any select.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.execute.return_value = MagicMock(data=[])
            chain.select.return_value = sel
            upd = MagicMock()
            upd.eq.return_value = upd
            upd.execute.return_value = MagicMock(data=[{"ok": True}])
            chain.update.return_value = upd

        return chain

    sb.table.side_effect = _table

    with patch.object(approval_service, "get_supabase", return_value=sb):
        result = approval_service.apply_modifications_to_quote(
            quote_id="q-1",
            modifications={"margin_percent": 12.5},
        )

    # SELECT on quote_versions.input_variables must have happened.
    assert state["quote_versions_select"], (
        "Expected SELECT on quote_versions; margin_percent flow did not "
        f"reach quote_versions. Result: {result!r}"
    )
    for lit in state["quote_versions_select"]:
        cols = _strip_embeds(lit)
        diff = cols - VALID_QUOTE_VERSIONS_COLS
        assert not diff, (
            f"Schema drift on kvota.quote_versions: {diff}. Literal: {lit!r}"
        )

    # UPDATE payload merged into input_variables (not into a top-level
    # `variables` column).
    assert state["quote_versions_update"], "Expected UPDATE on quote_versions"
    update_payload = state["quote_versions_update"][0]
    assert "input_variables" in update_payload
    assert "variables" not in update_payload
    iv = update_payload["input_variables"]
    assert iv["margin_percent"] == 12.5
    assert iv["manager_modified"] is True
    assert iv.get("existing") is True  # preserved existing keys

    assert "margin_percent" in result.fields_updated


def test_apply_modifications_no_margin_does_not_touch_quote_versions():
    """When margin_percent is not in modifications, no quote_versions write."""
    from services import approval_service

    state = {"quote_versions_calls": 0}

    sb = MagicMock()

    def _table(name: str):
        if name == "quote_versions":
            state["quote_versions_calls"] += 1
        chain = MagicMock()
        sel = MagicMock()
        sel.eq.return_value = sel
        sel.execute.return_value = MagicMock(data=[])
        chain.select.return_value = sel
        upd = MagicMock()
        upd.eq.return_value = upd
        upd.execute.return_value = MagicMock(data=[{"ok": True}])
        chain.update.return_value = upd
        return chain

    sb.table.side_effect = _table

    with patch.object(approval_service, "get_supabase", return_value=sb):
        approval_service.apply_modifications_to_quote(
            quote_id="q-1",
            modifications={"payment_terms": "net 30"},
        )

    assert state["quote_versions_calls"] == 0, (
        "quote_versions was touched even though margin_percent was not "
        "in modifications."
    )
