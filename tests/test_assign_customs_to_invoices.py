"""
Tests for assign_customs_to_invoices (Wave 1 Task 7.2).

Least-loaded customs assignment via RPC `kvota.assign_customs_invoices_for_quote`.
Per-org advisory lock inside the RPC serialises concurrent transitions.

Pattern mirrors test_logistics_invoice_assignment.py — unittest.mock for
supabase client, no live DB required.

Integration / concurrency test for the DB function itself lives in
test_migration_286_advisory_lock.py (skipped without DATABASE_URL).
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workflow_service import assign_customs_to_invoices  # noqa: E402


QUOTE_ID = "11111111-1111-1111-1111-111111111111"
INVOICE_1 = "11111111-1111-1111-1111-000000000001"
INVOICE_2 = "11111111-1111-1111-1111-000000000002"
USER_OLEG = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
USER_ALEYNA = "aaaaaaaa-aaaa-aaaa-aaaa-000000000002"


def _rpc_response(rows):
    """Build a supabase-py response shape with given .data rows."""
    resp = MagicMock()
    resp.data = rows
    return resp


def _mock_supabase_rpc(rows):
    """Build a supabase client mock whose .rpc().execute() returns rows."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value = _rpc_response(rows)
    return client


def test_all_matched_success():
    """Every invoice matched — success with assigned_invoices populated."""
    client = _mock_supabase_rpc([
        {"invoice_id": INVOICE_1, "assigned_user_id": USER_OLEG, "matched": True},
        {"invoice_id": INVOICE_2, "assigned_user_id": USER_ALEYNA, "matched": True},
    ])

    with patch("services.workflow_service.get_supabase", return_value=client):
        result = assign_customs_to_invoices(QUOTE_ID)

    assert result["success"] is True
    assert len(result["assigned_invoices"]) == 2
    assert {a["invoice_id"] for a in result["assigned_invoices"]} == {INVOICE_1, INVOICE_2}
    assert result["unmatched_invoice_ids"] == []
    assert result["error_message"] is None

    # RPC called with correct args
    client.rpc.assert_called_once_with(
        "assign_customs_invoices_for_quote", {"p_quote_id": QUOTE_ID}
    )


def test_partial_match_returns_unmatched():
    """Some invoices matched, others not (no customs user in org)."""
    client = _mock_supabase_rpc([
        {"invoice_id": INVOICE_1, "assigned_user_id": USER_OLEG, "matched": True},
        {"invoice_id": INVOICE_2, "assigned_user_id": None, "matched": False},
    ])

    with patch("services.workflow_service.get_supabase", return_value=client):
        result = assign_customs_to_invoices(QUOTE_ID)

    assert result["success"] is True
    assert len(result["assigned_invoices"]) == 1
    assert result["assigned_invoices"][0]["invoice_id"] == INVOICE_1
    assert result["unmatched_invoice_ids"] == [INVOICE_2]


def test_no_invoices_empty_result():
    """Quote has no invoices — function returns success with empty lists."""
    client = _mock_supabase_rpc([])

    with patch("services.workflow_service.get_supabase", return_value=client):
        result = assign_customs_to_invoices(QUOTE_ID)

    assert result["success"] is True
    assert result["assigned_invoices"] == []
    assert result["unmatched_invoice_ids"] == []


def test_rpc_exception_returns_failure():
    """RPC raises → function returns {success: False, error_message: ...}."""
    client = MagicMock()
    client.rpc.side_effect = Exception("DB unavailable")

    with patch("services.workflow_service.get_supabase", return_value=client):
        result = assign_customs_to_invoices(QUOTE_ID)

    assert result["success"] is False
    assert result["error_message"] == "DB unavailable"
    assert result["assigned_invoices"] == []
    assert result["unmatched_invoice_ids"] == []


def test_non_list_data_treated_as_empty():
    """Guard: RPC returns unexpected shape (e.g. None) — no crash."""
    client = MagicMock()
    client.rpc.return_value.execute.return_value.data = None

    with patch("services.workflow_service.get_supabase", return_value=client):
        result = assign_customs_to_invoices(QUOTE_ID)

    assert result["success"] is True
    assert result["assigned_invoices"] == []
    assert result["unmatched_invoice_ids"] == []


def test_rpc_wrapper_passes_quote_id_as_uuid_string():
    """RPC param name is p_quote_id (matches function signature in migration 286)."""
    client = _mock_supabase_rpc([])

    with patch("services.workflow_service.get_supabase", return_value=client):
        assign_customs_to_invoices(QUOTE_ID)

    call_args = client.rpc.call_args
    assert call_args[0][0] == "assign_customs_invoices_for_quote"
    assert call_args[0][1] == {"p_quote_id": QUOTE_ID}
