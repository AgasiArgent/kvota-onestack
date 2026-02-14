"""
Tests for Download Button Visibility on Quote Detail Page

Task [86afdkuva]: Download buttons should be visible/hidden based on workflow status.

Visibility rules:
- Validation Excel (MOP) -> visible during preparation stages (draft through pending_quote_control)
- KP PDF -> visible only AFTER Quote Control passed (pending_spec_control and later)
- Invoice PDF -> visible only AFTER Spec Control passed (deal stage)
- Specification DOC -> visible only AFTER Spec Control passed (deal stage)

Status progression:
draft -> pending_procurement -> pending_logistics -> pending_customs ->
pending_sales_review -> pending_quote_control -> pending_approval -> approved ->
sent_to_client -> pending_spec_control -> pending_signature -> deal

TDD: These tests are written BEFORE the implementation.
The visibility functions (show_validation_excel, show_quote_pdf, show_invoice_and_spec)
will be added to services/workflow_service.py.
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.workflow_service import WorkflowStatus

# Import the visibility functions that will be implemented.
# These should be added to services/workflow_service.py.
# Using try/except so tests can be collected and fail with clear assertion errors
# rather than a single ImportError blocking the entire file.
try:
    from services.workflow_service import (
        show_validation_excel,
        show_quote_pdf,
        show_invoice_and_spec,
    )
    _FUNCTIONS_AVAILABLE = True
except ImportError:
    _FUNCTIONS_AVAILABLE = False

    def show_validation_excel(status):
        raise NotImplementedError("show_validation_excel not yet implemented in workflow_service.py")

    def show_quote_pdf(status):
        raise NotImplementedError("show_quote_pdf not yet implemented in workflow_service.py")

    def show_invoice_and_spec(status):
        raise NotImplementedError("show_invoice_and_spec not yet implemented in workflow_service.py")


# Marker applied to all tests -- they will fail until functions are implemented
not_implemented = pytest.mark.xfail(
    not _FUNCTIONS_AVAILABLE,
    reason="Visibility functions not yet implemented in workflow_service.py",
    raises=NotImplementedError,
    strict=True,
)


# =============================================================================
# STATUS GROUPS (for parameterized tests)
# =============================================================================

# All statuses in workflow order
ALL_STATUSES = [s.value for s in WorkflowStatus]

# Preparation stages: draft through pending_quote_control
PREPARATION_STATUSES = [
    WorkflowStatus.DRAFT.value,
    WorkflowStatus.PENDING_PROCUREMENT.value,
    WorkflowStatus.PENDING_LOGISTICS.value,
    WorkflowStatus.PENDING_CUSTOMS.value,
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value,
    WorkflowStatus.PENDING_SALES_REVIEW.value,
    WorkflowStatus.PENDING_QUOTE_CONTROL.value,
]

# Post-quote-control statuses: after quote control passed
POST_QUOTE_CONTROL_STATUSES = [
    WorkflowStatus.PENDING_APPROVAL.value,
    WorkflowStatus.APPROVED.value,
    WorkflowStatus.SENT_TO_CLIENT.value,
    WorkflowStatus.PENDING_SPEC_CONTROL.value,
    WorkflowStatus.PENDING_SIGNATURE.value,
    WorkflowStatus.DEAL.value,
]

# Statuses where KP PDF should be visible (from approved onward)
KP_PDF_VISIBLE_STATUSES = [
    WorkflowStatus.APPROVED.value,
    WorkflowStatus.SENT_TO_CLIENT.value,
    WorkflowStatus.PENDING_SPEC_CONTROL.value,
    WorkflowStatus.PENDING_SIGNATURE.value,
    WorkflowStatus.DEAL.value,
]

# Statuses where KP PDF should be hidden
KP_PDF_HIDDEN_STATUSES = [
    WorkflowStatus.DRAFT.value,
    WorkflowStatus.PENDING_PROCUREMENT.value,
    WorkflowStatus.PENDING_LOGISTICS.value,
    WorkflowStatus.PENDING_CUSTOMS.value,
    WorkflowStatus.PENDING_LOGISTICS_AND_CUSTOMS.value,
    WorkflowStatus.PENDING_SALES_REVIEW.value,
    WorkflowStatus.PENDING_QUOTE_CONTROL.value,
    WorkflowStatus.PENDING_APPROVAL.value,
]

# Deal stage only (for invoice PDF and spec DOC)
DEAL_STATUSES = [
    WorkflowStatus.DEAL.value,
]

# All statuses that are NOT deal
NON_DEAL_STATUSES = [s.value for s in WorkflowStatus if s != WorkflowStatus.DEAL]

# Terminal/rejected/cancelled statuses
TERMINAL_NEGATIVE_STATUSES = [
    WorkflowStatus.REJECTED.value,
    WorkflowStatus.CANCELLED.value,
]


# =============================================================================
# VALIDATION EXCEL (MOP) - VISIBILITY TESTS
# =============================================================================

@not_implemented
class TestShowValidationExcel:
    """Tests for show_validation_excel() - visible during preparation stages."""

    @pytest.mark.parametrize("status", PREPARATION_STATUSES)
    def test_visible_during_preparation_stages(self, status):
        """Validation Excel should be visible during all preparation stages."""
        assert show_validation_excel(status) is True, (
            f"Validation Excel should be visible for status '{status}'"
        )

    def test_visible_in_draft(self):
        """Validation Excel should be visible in draft status."""
        assert show_validation_excel("draft") is True

    def test_visible_in_pending_procurement(self):
        """Validation Excel should be visible when procurement is reviewing."""
        assert show_validation_excel("pending_procurement") is True

    def test_visible_in_pending_logistics(self):
        """Validation Excel should be visible when logistics is reviewing."""
        assert show_validation_excel("pending_logistics") is True

    def test_visible_in_pending_customs(self):
        """Validation Excel should be visible when customs is reviewing."""
        assert show_validation_excel("pending_customs") is True

    def test_visible_in_pending_logistics_and_customs(self):
        """Validation Excel should be visible during parallel logistics+customs."""
        assert show_validation_excel("pending_logistics_and_customs") is True

    def test_visible_in_pending_sales_review(self):
        """Validation Excel should be visible during sales review."""
        assert show_validation_excel("pending_sales_review") is True

    def test_visible_in_pending_quote_control(self):
        """Validation Excel should be visible during quote control (last preparation stage)."""
        assert show_validation_excel("pending_quote_control") is True

    @pytest.mark.parametrize("status", POST_QUOTE_CONTROL_STATUSES)
    def test_hidden_after_quote_control(self, status):
        """Validation Excel should be hidden after quote control passes."""
        assert show_validation_excel(status) is False, (
            f"Validation Excel should be hidden for status '{status}'"
        )

    def test_hidden_in_pending_approval(self):
        """Validation Excel should be hidden during approval stage."""
        assert show_validation_excel("pending_approval") is False

    def test_hidden_in_approved(self):
        """Validation Excel should be hidden when quote is approved."""
        assert show_validation_excel("approved") is False

    def test_hidden_in_deal(self):
        """Validation Excel should be hidden in deal stage."""
        assert show_validation_excel("deal") is False

    def test_hidden_in_pending_spec_control(self):
        """Validation Excel should be hidden during spec control."""
        assert show_validation_excel("pending_spec_control") is False

    @pytest.mark.parametrize("status", TERMINAL_NEGATIVE_STATUSES)
    def test_hidden_in_terminal_negative_statuses(self, status):
        """Validation Excel should be hidden for rejected/cancelled quotes."""
        assert show_validation_excel(status) is False, (
            f"Validation Excel should be hidden for terminal status '{status}'"
        )

    def test_accepts_workflow_status_enum(self):
        """Function should accept WorkflowStatus enum directly."""
        assert show_validation_excel(WorkflowStatus.DRAFT) is True
        assert show_validation_excel(WorkflowStatus.DEAL) is False

    def test_returns_bool(self):
        """Function should return a boolean, not a truthy/falsy value."""
        result = show_validation_excel("draft")
        assert isinstance(result, bool)


# =============================================================================
# KP PDF - VISIBILITY TESTS
# =============================================================================

@not_implemented
class TestShowQuotePdf:
    """Tests for show_quote_pdf() - visible only after Quote Control passed."""

    @pytest.mark.parametrize("status", KP_PDF_VISIBLE_STATUSES)
    def test_visible_after_quote_control(self, status):
        """KP PDF should be visible after quote control passes."""
        assert show_quote_pdf(status) is True, (
            f"KP PDF should be visible for status '{status}'"
        )

    def test_visible_in_pending_spec_control(self):
        """KP PDF should be visible during spec control (first stage after QC)."""
        assert show_quote_pdf("pending_spec_control") is True

    def test_visible_in_pending_signature(self):
        """KP PDF should be visible during signature stage."""
        assert show_quote_pdf("pending_signature") is True

    def test_visible_in_deal(self):
        """KP PDF should be visible in deal stage."""
        assert show_quote_pdf("deal") is True

    @pytest.mark.parametrize("status", KP_PDF_HIDDEN_STATUSES)
    def test_hidden_before_spec_control(self, status):
        """KP PDF should be hidden before spec control stage."""
        assert show_quote_pdf(status) is False, (
            f"KP PDF should be hidden for status '{status}'"
        )

    def test_hidden_in_draft(self):
        """KP PDF should be hidden in draft status."""
        assert show_quote_pdf("draft") is False

    def test_hidden_in_pending_procurement(self):
        """KP PDF should be hidden during procurement review."""
        assert show_quote_pdf("pending_procurement") is False

    def test_hidden_in_pending_quote_control(self):
        """KP PDF should be hidden during quote control (QC not yet passed)."""
        assert show_quote_pdf("pending_quote_control") is False

    def test_hidden_in_pending_approval(self):
        """KP PDF should be hidden during approval (before spec control)."""
        assert show_quote_pdf("pending_approval") is False

    def test_visible_in_approved(self):
        """KP PDF should be visible when approved (after approval step)."""
        assert show_quote_pdf("approved") is True

    def test_visible_in_sent_to_client(self):
        """KP PDF should be visible when sent to client."""
        assert show_quote_pdf("sent_to_client") is True

    @pytest.mark.parametrize("status", TERMINAL_NEGATIVE_STATUSES)
    def test_hidden_in_terminal_negative_statuses(self, status):
        """KP PDF should be hidden for rejected/cancelled quotes."""
        assert show_quote_pdf(status) is False, (
            f"KP PDF should be hidden for terminal status '{status}'"
        )

    def test_accepts_workflow_status_enum(self):
        """Function should accept WorkflowStatus enum directly."""
        assert show_quote_pdf(WorkflowStatus.PENDING_SPEC_CONTROL) is True
        assert show_quote_pdf(WorkflowStatus.DRAFT) is False

    def test_returns_bool(self):
        """Function should return a boolean, not a truthy/falsy value."""
        result = show_quote_pdf("pending_spec_control")
        assert isinstance(result, bool)


# =============================================================================
# INVOICE PDF + SPECIFICATION DOC - VISIBILITY TESTS
# =============================================================================

@not_implemented
class TestShowInvoiceAndSpec:
    """Tests for show_invoice_and_spec() - visible only after Spec Control passed (deal stage)."""

    def test_visible_in_deal(self):
        """Invoice PDF and Spec DOC should be visible in deal stage."""
        assert show_invoice_and_spec("deal") is True

    @pytest.mark.parametrize("status", NON_DEAL_STATUSES)
    def test_hidden_in_all_non_deal_statuses(self, status):
        """Invoice PDF and Spec DOC should be hidden for all non-deal statuses."""
        assert show_invoice_and_spec(status) is False, (
            f"Invoice/Spec should be hidden for status '{status}'"
        )

    def test_hidden_in_draft(self):
        """Invoice PDF should be hidden in draft."""
        assert show_invoice_and_spec("draft") is False

    def test_hidden_in_pending_procurement(self):
        """Invoice PDF should be hidden during procurement."""
        assert show_invoice_and_spec("pending_procurement") is False

    def test_hidden_in_pending_spec_control(self):
        """Invoice PDF should be hidden during spec control (not yet passed)."""
        assert show_invoice_and_spec("pending_spec_control") is False

    def test_hidden_in_pending_signature(self):
        """Invoice PDF should be hidden during signature (spec control passed but not yet deal)."""
        assert show_invoice_and_spec("pending_signature") is False

    def test_hidden_in_approved(self):
        """Invoice PDF should be hidden when quote is approved."""
        assert show_invoice_and_spec("approved") is False

    def test_hidden_in_pending_quote_control(self):
        """Invoice PDF should be hidden during quote control."""
        assert show_invoice_and_spec("pending_quote_control") is False

    @pytest.mark.parametrize("status", TERMINAL_NEGATIVE_STATUSES)
    def test_hidden_in_terminal_negative_statuses(self, status):
        """Invoice/Spec should be hidden for rejected/cancelled quotes."""
        assert show_invoice_and_spec(status) is False, (
            f"Invoice/Spec should be hidden for terminal status '{status}'"
        )

    def test_accepts_workflow_status_enum(self):
        """Function should accept WorkflowStatus enum directly."""
        assert show_invoice_and_spec(WorkflowStatus.DEAL) is True
        assert show_invoice_and_spec(WorkflowStatus.PENDING_SPEC_CONTROL) is False

    def test_returns_bool(self):
        """Function should return a boolean, not a truthy/falsy value."""
        result = show_invoice_and_spec("deal")
        assert isinstance(result, bool)


# =============================================================================
# CROSS-CUTTING VISIBILITY TESTS
# =============================================================================

@not_implemented
class TestCrossCuttingVisibility:
    """Tests that verify the mutual exclusivity and completeness of visibility rules."""

    def test_draft_only_shows_validation_excel(self):
        """In draft status, only Validation Excel should be visible."""
        assert show_validation_excel("draft") is True
        assert show_quote_pdf("draft") is False
        assert show_invoice_and_spec("draft") is False

    def test_pending_procurement_only_shows_validation_excel(self):
        """In pending_procurement, only Validation Excel should be visible."""
        assert show_validation_excel("pending_procurement") is True
        assert show_quote_pdf("pending_procurement") is False
        assert show_invoice_and_spec("pending_procurement") is False

    def test_pending_quote_control_only_shows_validation_excel(self):
        """In pending_quote_control, only Validation Excel should be visible."""
        assert show_validation_excel("pending_quote_control") is True
        assert show_quote_pdf("pending_quote_control") is False
        assert show_invoice_and_spec("pending_quote_control") is False

    def test_pending_approval_shows_no_downloads(self):
        """In pending_approval (between QC and spec control), no download buttons visible."""
        assert show_validation_excel("pending_approval") is False
        assert show_quote_pdf("pending_approval") is False
        assert show_invoice_and_spec("pending_approval") is False

    def test_approved_shows_kp_pdf_only(self):
        """In approved status, only KP PDF is visible."""
        assert show_validation_excel("approved") is False
        assert show_quote_pdf("approved") is True
        assert show_invoice_and_spec("approved") is False

    def test_sent_to_client_shows_kp_pdf_only(self):
        """In sent_to_client, only KP PDF is visible."""
        assert show_validation_excel("sent_to_client") is False
        assert show_quote_pdf("sent_to_client") is True
        assert show_invoice_and_spec("sent_to_client") is False

    def test_pending_spec_control_only_shows_kp_pdf(self):
        """In pending_spec_control, only KP PDF should be visible."""
        assert show_validation_excel("pending_spec_control") is False
        assert show_quote_pdf("pending_spec_control") is True
        assert show_invoice_and_spec("pending_spec_control") is False

    def test_pending_signature_only_shows_kp_pdf(self):
        """In pending_signature, only KP PDF should be visible."""
        assert show_validation_excel("pending_signature") is False
        assert show_quote_pdf("pending_signature") is True
        assert show_invoice_and_spec("pending_signature") is False

    def test_deal_shows_kp_pdf_and_invoice_and_spec(self):
        """In deal stage, KP PDF + Invoice PDF + Spec DOC should all be visible."""
        assert show_validation_excel("deal") is False
        assert show_quote_pdf("deal") is True
        assert show_invoice_and_spec("deal") is True

    def test_rejected_shows_no_downloads(self):
        """Rejected quotes should show no download buttons."""
        assert show_validation_excel("rejected") is False
        assert show_quote_pdf("rejected") is False
        assert show_invoice_and_spec("rejected") is False

    def test_cancelled_shows_no_downloads(self):
        """Cancelled quotes should show no download buttons."""
        assert show_validation_excel("cancelled") is False
        assert show_quote_pdf("cancelled") is False
        assert show_invoice_and_spec("cancelled") is False

    def test_client_negotiation_shows_no_downloads(self):
        """Client negotiation should show no download buttons (not in main flow)."""
        assert show_validation_excel("client_negotiation") is False
        assert show_quote_pdf("client_negotiation") is False
        assert show_invoice_and_spec("client_negotiation") is False


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

@not_implemented
class TestEdgeCases:
    """Edge case tests for visibility functions."""

    def test_validation_excel_boundary_last_preparation_status(self):
        """Validation Excel should be visible at the boundary (pending_quote_control)."""
        assert show_validation_excel("pending_quote_control") is True

    def test_validation_excel_boundary_first_post_qc_status(self):
        """Validation Excel should be hidden at the boundary (pending_approval)."""
        assert show_validation_excel("pending_approval") is False

    def test_kp_pdf_boundary_last_hidden_status(self):
        """KP PDF should be visible at the boundary (sent_to_client)."""
        assert show_quote_pdf("sent_to_client") is True

    def test_kp_pdf_boundary_first_visible_status(self):
        """KP PDF should be visible at the boundary (pending_spec_control)."""
        assert show_quote_pdf("pending_spec_control") is True

    def test_invoice_spec_boundary_last_hidden_status(self):
        """Invoice/Spec should be hidden at the boundary (pending_signature)."""
        assert show_invoice_and_spec("pending_signature") is False

    def test_invoice_spec_boundary_first_visible_status(self):
        """Invoice/Spec should be visible at the boundary (deal)."""
        assert show_invoice_and_spec("deal") is True

    def test_every_status_has_at_least_one_function_defined(self):
        """Every valid workflow status should be handled by all three functions (no KeyError)."""
        for status in WorkflowStatus:
            # Should not raise any exceptions
            show_validation_excel(status.value)
            show_quote_pdf(status.value)
            show_invoice_and_spec(status.value)

    def test_functions_work_with_enum_values_and_strings(self):
        """Functions should work with both enum values and raw strings."""
        for status in WorkflowStatus:
            # String form
            result_str = show_validation_excel(status.value)
            # Enum form
            result_enum = show_validation_excel(status)
            # Both should return the same result
            assert result_str == result_enum, (
                f"Mismatch for status {status}: string={result_str}, enum={result_enum}"
            )


# =============================================================================
# FULL STATUS PROGRESSION TEST
# =============================================================================

@not_implemented
class TestFullStatusProgression:
    """Tests that verify visibility across the entire status progression."""

    def test_validation_excel_visibility_across_full_progression(self):
        """Validation Excel: visible for first 7 statuses, hidden after."""
        progression = [
            ("draft", True),
            ("pending_procurement", True),
            ("pending_logistics", True),
            ("pending_customs", True),
            ("pending_sales_review", True),
            ("pending_quote_control", True),
            ("pending_approval", False),
            ("approved", False),
            ("sent_to_client", False),
            ("pending_spec_control", False),
            ("pending_signature", False),
            ("deal", False),
        ]
        for status, expected in progression:
            actual = show_validation_excel(status)
            assert actual == expected, (
                f"Validation Excel for '{status}': expected {expected}, got {actual}"
            )

    def test_kp_pdf_visibility_across_full_progression(self):
        """KP PDF: hidden until approved, then visible."""
        progression = [
            ("draft", False),
            ("pending_procurement", False),
            ("pending_logistics", False),
            ("pending_customs", False),
            ("pending_sales_review", False),
            ("pending_quote_control", False),
            ("pending_approval", False),
            ("approved", True),
            ("sent_to_client", True),
            ("pending_spec_control", True),
            ("pending_signature", True),
            ("deal", True),
        ]
        for status, expected in progression:
            actual = show_quote_pdf(status)
            assert actual == expected, (
                f"KP PDF for '{status}': expected {expected}, got {actual}"
            )

    def test_invoice_spec_visibility_across_full_progression(self):
        """Invoice PDF + Spec DOC: hidden until deal stage."""
        progression = [
            ("draft", False),
            ("pending_procurement", False),
            ("pending_logistics", False),
            ("pending_customs", False),
            ("pending_sales_review", False),
            ("pending_quote_control", False),
            ("pending_approval", False),
            ("approved", False),
            ("sent_to_client", False),
            ("pending_spec_control", False),
            ("pending_signature", False),
            ("deal", True),
        ]
        for status, expected in progression:
            actual = show_invoice_and_spec(status)
            assert actual == expected, (
                f"Invoice/Spec for '{status}': expected {expected}, got {actual}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
