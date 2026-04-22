"""
Regression guard for Wave 1 Task 7.3 — assign_customs_to_invoices wired
into complete_procurement() alongside assign_logistics_to_invoices.

Pattern check over services/workflow_service.py source: verifies both
best-effort assignment calls sit inside complete_procurement and that the
result's error_message aggregates both warnings.
"""

from __future__ import annotations

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW_SRC = os.path.join(PROJECT_ROOT, "services", "workflow_service.py")


def _read_source() -> str:
    with open(WORKFLOW_SRC, "r") as f:
        return f.read()


def test_assign_customs_to_invoices_function_defined():
    """Public function must be defined at module level."""
    src = _read_source()
    assert re.search(r"^def assign_customs_to_invoices\(quote_id: str\)", src, re.M), (
        "assign_customs_to_invoices(quote_id) must be defined in workflow_service.py"
    )


def test_complete_procurement_calls_both_assignments():
    """complete_procurement invokes both logistics and customs assignment."""
    src = _read_source()

    # Extract complete_procurement body (between `def complete_procurement` and
    # the next `def ` at column 0)
    match = re.search(
        r"^def complete_procurement\(.+?(?=^def )",
        src,
        re.M | re.S,
    )
    assert match, "complete_procurement function not found"
    body = match.group(0)

    assert "assign_logistics_to_invoices(quote_id)" in body, (
        "complete_procurement must call assign_logistics_to_invoices(quote_id)"
    )
    assert "assign_customs_to_invoices(quote_id)" in body, (
        "complete_procurement must call assign_customs_to_invoices(quote_id) "
        "(wired by Wave 1 Task 7.3)"
    )


def test_both_warnings_aggregated_into_result_error():
    """Final error_message combines logistics_warning + customs_warning."""
    src = _read_source()

    match = re.search(
        r"^def complete_procurement\(.+?(?=^def )",
        src,
        re.M | re.S,
    )
    assert match
    body = match.group(0)

    # Both warning variables must be referenced in the aggregation step
    assert "logistics_warning" in body
    assert "customs_warning" in body

    # Aggregation pattern: both collected into `warnings` list OR
    # concatenated into result_error
    has_aggregation = (
        ("logistics_warning" in body and "customs_warning" in body)
        and (
            "warnings" in body  # list-based aggregation
            or (
                "result_error" in body
                and body.count("result_error") >= 2
            )
        )
    )
    assert has_aggregation, (
        "Both logistics_warning and customs_warning must be aggregated "
        "into the TransitionResult error_message"
    )


def test_customs_best_effort_try_except_isolation():
    """Customs assignment failure must not break the transition.

    Like logistics, customs auto-assignment is wrapped in try/except so a
    transient DB/RPC error still lets the quote reach
    pending_logistics_and_customs.
    """
    src = _read_source()

    match = re.search(
        r"^def complete_procurement\(.+?(?=^def )",
        src,
        re.M | re.S,
    )
    assert match
    body = match.group(0)

    # Find where assign_customs_to_invoices is called
    customs_call_match = re.search(
        r"assign_customs_to_invoices\(quote_id\)", body
    )
    assert customs_call_match, "assign_customs_to_invoices call not found"

    # Look ~30 lines before the call for a `try:` keyword
    call_position = customs_call_match.start()
    pre_context = body[max(0, call_position - 2000) : call_position]
    assert "try:" in pre_context, (
        "assign_customs_to_invoices must be inside a try/except block "
        "(best-effort, should not break workflow transition)"
    )
