"""
Regression guard for logistics-customs-kanban REQ-3 — auto-distribution removed.

Auto-assignment of logisticians/customs officers used to run inside
``complete_procurement``. The kanban redesign replaces it with manual
pull/assign, so ``complete_procurement`` must NO LONGER invoke the assigners.

Pattern check over services/workflow_service.py source: verifies the
auto-distribution call sites are gone from ``complete_procurement``.
"""

from __future__ import annotations

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_SRC = os.path.join(PROJECT_ROOT, "services", "workflow_service.py")


def _read_source() -> str:
    with open(WORKFLOW_SRC, "r") as f:
        return f.read()


def _complete_procurement_body() -> str:
    """Extract the ``complete_procurement`` function body (col-0 to col-0)."""
    src = _read_source()
    match = re.search(
        r"^def complete_procurement\(.+?(?=^def )",
        src,
        re.M | re.S,
    )
    assert match, "complete_procurement function not found"
    return match.group(0)


def test_complete_procurement_does_not_auto_assign_logistics():
    """complete_procurement must NOT call assign_logistics_to_invoices (REQ-3)."""
    body = _complete_procurement_body()
    assert "assign_logistics_to_invoices(quote_id)" not in body, (
        "complete_procurement must NOT auto-assign logistics — assignment is "
        "now manual via the workspace kanban (logistics-customs-kanban REQ-3)"
    )


def test_complete_procurement_does_not_auto_assign_customs():
    """complete_procurement must NOT call assign_customs_to_invoices (REQ-3)."""
    body = _complete_procurement_body()
    assert "assign_customs_to_invoices(quote_id)" not in body, (
        "complete_procurement must NOT auto-assign customs — assignment is "
        "now manual via the workspace kanban (logistics-customs-kanban REQ-3)"
    )


def test_complete_procurement_still_advances_workflow():
    """The transition itself must remain: procurement → logistics+customs stage."""
    body = _complete_procurement_body()
    assert "PENDING_LOGISTICS_AND_CUSTOMS" in body, (
        "complete_procurement must still advance the quote to the "
        "pending_logistics_and_customs stage"
    )
