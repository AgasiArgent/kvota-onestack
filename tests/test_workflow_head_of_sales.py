"""
Regression tests for G2 (РОП-24, 2026-05-05): head_of_sales must be allowed
to perform sales-owned workflow transitions on subordinates' quotes.

Bug context:
    kravtsova.e@masterbearing.ru (head_of_sales, Группа Кравцовой) opened a
    quote owned by a subordinate sales user, clicked «Отправить в закупку»
    (DRAFT → PENDING_PROCUREMENT), and got:
        "Ошибка перехода: You don't have permission to perform this
         transition. Required roles: sales, admin"

Root cause:
    services/workflow_service.py ALLOWED_TRANSITIONS hard-coded
    ["sales", "admin"] on every sales-owned transition. head_of_sales was
    introduced after this matrix and never wired in. Per access-control.md
    the GROUP tier (head_of_sales) is supposed to have full edit rights on
    its sales group's data, including triggering workflow transitions on
    subordinate quotes.

Fix:
    Widen all ["sales", "admin"] and ["sales", "sales_manager", "admin"]
    transitions to include "head_of_sales". This is the same pattern
    api/quotes.py cancel_roles already uses ({"sales", "head_of_sales",
    "admin"}).

These tests assert the in-memory ALLOWED_TRANSITIONS table — no DB needed.
"""

from __future__ import annotations

import pytest

from services.workflow_service import (
    ALLOWED_TRANSITIONS,
    WorkflowStatus,
    can_transition,
    get_roles_for_transition,
)


# ---------------------------------------------------------------------------
# G2 fix: head_of_sales can do every sales transition
# ---------------------------------------------------------------------------


class TestHeadOfSalesCanDoSalesTransitions:
    """Every transition that allows 'sales' must also allow 'head_of_sales'.

    This is the canonical regression for РОП-24 — once a transition gates
    on plain 'sales' but excludes 'head_of_sales', a РОП cannot drive a
    subordinate's quote forward at that step.
    """

    def test_head_of_sales_allowed_for_send_to_procurement(self) -> None:
        """The exact failure: DRAFT → PENDING_PROCUREMENT must accept РОП."""
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["head_of_sales"],
        )
        assert allowed is True, (
            "head_of_sales must be able to «Отправить в закупку» on a "
            "subordinate's draft quote (РОП-24). Error: " + str(error)
        )
        assert error is None

    def test_head_of_sales_in_every_sales_transition_role_list(self) -> None:
        """For every transition that lists 'sales' as allowed, 'head_of_sales'
        must be listed too. Catches future contributors who add a sales
        transition without remembering РОП.
        """
        offenders: list[tuple[str, str, list[str]]] = []
        for t in ALLOWED_TRANSITIONS:
            if "sales" in t.allowed_roles and "head_of_sales" not in t.allowed_roles:
                offenders.append(
                    (t.from_status.value, t.to_status.value, list(t.allowed_roles))
                )
        assert offenders == [], (
            "Every transition that includes 'sales' must also include "
            "'head_of_sales'. Offenders: " + repr(offenders)
        )

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            # Smoke a representative slice of the sales transitions widened
            # by the fix. The full coverage test above guards the rest.
            (WorkflowStatus.DRAFT, WorkflowStatus.PENDING_PROCUREMENT),
            (WorkflowStatus.DRAFT, WorkflowStatus.CANCELLED),
            (WorkflowStatus.PENDING_PROCUREMENT, WorkflowStatus.DRAFT),
            (WorkflowStatus.PENDING_PROCUREMENT, WorkflowStatus.CANCELLED),
            (WorkflowStatus.PENDING_SALES_REVIEW, WorkflowStatus.PENDING_QUOTE_CONTROL),
            (WorkflowStatus.PENDING_SALES_REVIEW, WorkflowStatus.PENDING_APPROVAL),
            (WorkflowStatus.APPROVED, WorkflowStatus.SENT_TO_CLIENT),
            (WorkflowStatus.SENT_TO_CLIENT, WorkflowStatus.CLIENT_NEGOTIATION),
            (WorkflowStatus.CLIENT_NEGOTIATION, WorkflowStatus.PENDING_SPEC_CONTROL),
            (WorkflowStatus.PENDING_SIGNATURE, WorkflowStatus.DEAL),
        ],
    )
    def test_head_of_sales_allowed_for_representative_transitions(
        self, from_status: WorkflowStatus, to_status: WorkflowStatus
    ) -> None:
        """Spot-check: РОП can drive each canonical sales-owned step."""
        allowed, error = can_transition(from_status, to_status, ["head_of_sales"])
        assert allowed is True, (
            f"head_of_sales must be allowed on "
            f"{from_status.value} → {to_status.value} "
            f"(transition listed sales). Error: {error}"
        )


# ---------------------------------------------------------------------------
# Regression guards: don't accidentally widen non-sales transitions
# ---------------------------------------------------------------------------


class TestHeadOfSalesDoesNotEscalateOtherDomains:
    """The fix only widens transitions that already allowed 'sales'. It must
    NOT add head_of_sales to procurement, logistics, customs, quote_control,
    spec_control, or top_manager-owned transitions.
    """

    @pytest.mark.parametrize(
        "from_status,to_status",
        [
            # Procurement-owned: only procurement/head_of_procurement/admin
            (WorkflowStatus.PENDING_PROCUREMENT, WorkflowStatus.PENDING_LOGISTICS),
            (WorkflowStatus.PENDING_PROCUREMENT, WorkflowStatus.PENDING_CUSTOMS),
            # Logistics-owned
            (WorkflowStatus.PENDING_LOGISTICS, WorkflowStatus.PENDING_SALES_REVIEW),
            # Customs-owned
            (WorkflowStatus.PENDING_CUSTOMS, WorkflowStatus.PENDING_SALES_REVIEW),
            # Quote controller stage
            (WorkflowStatus.PENDING_QUOTE_CONTROL, WorkflowStatus.APPROVED),
            (WorkflowStatus.PENDING_QUOTE_CONTROL, WorkflowStatus.PENDING_APPROVAL),
            # Top manager approval gate
            (WorkflowStatus.PENDING_APPROVAL, WorkflowStatus.APPROVED),
            (WorkflowStatus.PENDING_APPROVAL, WorkflowStatus.REJECTED),
            # Spec control
            (WorkflowStatus.PENDING_SPEC_CONTROL, WorkflowStatus.PENDING_SIGNATURE),
        ],
    )
    def test_head_of_sales_rejected_for_non_sales_transitions(
        self, from_status: WorkflowStatus, to_status: WorkflowStatus
    ) -> None:
        """Without an extra role, head_of_sales must NOT pass non-sales gates."""
        allowed, error = can_transition(from_status, to_status, ["head_of_sales"])
        assert allowed is False, (
            f"head_of_sales must NOT pass {from_status.value} → "
            f"{to_status.value} on its own — that's a different domain. "
            f"Got allowed={allowed}, error={error}"
        )

    def test_plain_sales_still_works(self) -> None:
        """The widening must not regress regular sales access."""
        allowed, _ = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["sales"],
        )
        assert allowed is True

    def test_admin_still_works(self) -> None:
        """The widening must not regress admin access."""
        allowed, _ = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["admin"],
        )
        assert allowed is True

    def test_unrelated_role_still_rejected(self) -> None:
        """A procurement role still cannot do a sales transition."""
        allowed, error = can_transition(
            WorkflowStatus.DRAFT,
            WorkflowStatus.PENDING_PROCUREMENT,
            ["procurement"],
        )
        assert allowed is False
        assert error is not None


# ---------------------------------------------------------------------------
# Cross-checks vs api/quotes.py cancel_roles (canonical РОП set)
# ---------------------------------------------------------------------------


class TestSalesAllowlistShape:
    """The widened sales allowlist should mirror the cancel_roles set already
    in api/quotes.py: {"sales", "head_of_sales", "admin"}.
    """

    def test_send_to_procurement_role_list_shape(self) -> None:
        """DRAFT → PENDING_PROCUREMENT lists exactly sales, head_of_sales, admin."""
        roles = get_roles_for_transition(
            WorkflowStatus.DRAFT, WorkflowStatus.PENDING_PROCUREMENT
        )
        assert set(roles) == {"sales", "head_of_sales", "admin"}, (
            "DRAFT → PENDING_PROCUREMENT must allow exactly the РОП-friendly "
            f"sales set. Got: {roles}"
        )

    def test_pending_approval_submission_role_list_shape(self) -> None:
        """PENDING_SALES_REVIEW → PENDING_APPROVAL is the only sales transition
        that historically also accepted sales_manager. The widened list must
        keep sales_manager AND add head_of_sales.
        """
        roles = get_roles_for_transition(
            WorkflowStatus.PENDING_SALES_REVIEW, WorkflowStatus.PENDING_APPROVAL
        )
        assert set(roles) == {"sales", "sales_manager", "head_of_sales", "admin"}, (
            "PENDING_SALES_REVIEW → PENDING_APPROVAL must keep sales_manager "
            f"and add head_of_sales. Got: {roles}"
        )
