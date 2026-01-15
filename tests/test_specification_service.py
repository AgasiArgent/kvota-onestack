"""
Tests for Specification Service - Specification lifecycle management

Tests for:
- SPEC-001: Specification creation service
- SPEC-002: Specification PDF generation (imports verification)
- SPEC-003: Signed scan upload and storage
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, date, timezone
from decimal import Decimal
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.specification_service import (
    # Data class
    Specification,
    CreateSpecFromQuoteResult,
    # Constants
    SPEC_STATUSES,
    SPEC_STATUS_NAMES,
    SPEC_STATUS_COLORS,
    SPEC_TRANSITIONS,
    # Status helpers
    get_spec_status_name,
    get_spec_status_color,
    can_transition_spec,
    get_allowed_spec_transitions,
    # Create operations
    create_specification,
    create_specification_from_quote,
    # Read operations
    get_specification,
    get_specification_by_quote,
    get_specifications_by_status,
    get_all_specifications,
    get_specifications_with_details,
    count_specifications_by_status,
    specification_exists_for_quote,
    # Update operations
    update_specification,
    update_specification_status,
    set_signed_scan_url,
    # Delete operations
    delete_specification,
    # Utility functions
    generate_specification_number,
    get_specification_stats,
    get_specifications_for_signing,
    get_recently_signed_specifications,
)


# =============================================================================
# SPECIFICATION DATA CLASS TESTS
# =============================================================================

class TestSpecificationDataClass:
    """Tests for Specification dataclass."""

    def test_specification_creation(self):
        """Specification should be creatable with required fields."""
        spec = Specification(
            id="spec-uuid",
            quote_id="quote-uuid",
            organization_id="org-uuid",
            quote_version_id="version-uuid",
            specification_number="SPEC-2026-001",
            proposal_idn=None,
            item_ind_sku=None,
            sign_date=None,
            validity_period="30 days",
            readiness_period=None,
            logistics_period=None,
            specification_currency="USD",
            exchange_rate_to_ruble=Decimal("90.5"),
            client_payment_term_after_upd=30,
            client_payment_terms="Net 30",
            cargo_pickup_country="China",
            goods_shipment_country="China",
            delivery_city_russia="Moscow",
            cargo_type="General",
            supplier_payment_country="China",
            our_legal_entity="ООО Квота",
            client_legal_entity="ООО Клиент",
            status="draft",
            signed_scan_url=None,
            created_by="user-uuid",
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        assert spec.id == "spec-uuid"
        assert spec.status == "draft"
        assert spec.exchange_rate_to_ruble == Decimal("90.5")

    def test_specification_from_dict(self):
        """Specification.from_dict should create from dictionary."""
        data = {
            "id": "spec-uuid",
            "quote_id": "quote-uuid",
            "organization_id": "org-uuid",
            "specification_number": "SPEC-001",
            "status": "draft",
            "created_by": "user-uuid",
            "created_at": "2026-01-15T12:00:00Z",
        }

        spec = Specification.from_dict(data)

        assert spec.id == "spec-uuid"
        assert spec.specification_number == "SPEC-001"

    def test_specification_to_dict(self):
        """Specification.to_dict should convert to dictionary."""
        spec = Specification(
            id="spec-uuid",
            quote_id="quote-uuid",
            organization_id="org-uuid",
            quote_version_id=None,
            specification_number="SPEC-001",
            proposal_idn=None,
            item_ind_sku=None,
            sign_date=date(2026, 1, 15),
            validity_period=None,
            readiness_period=None,
            logistics_period=None,
            specification_currency="USD",
            exchange_rate_to_ruble=Decimal("90.0"),
            client_payment_term_after_upd=None,
            client_payment_terms=None,
            cargo_pickup_country=None,
            goods_shipment_country=None,
            delivery_city_russia=None,
            cargo_type=None,
            supplier_payment_country=None,
            our_legal_entity=None,
            client_legal_entity=None,
            status="draft",
            signed_scan_url=None,
            created_by="user-uuid",
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )

        data = spec.to_dict()

        assert data["id"] == "spec-uuid"
        assert data["sign_date"] == "2026-01-15"
        assert data["exchange_rate_to_ruble"] == 90.0  # Converted to float


# =============================================================================
# STATUS CONSTANTS AND HELPERS TESTS
# =============================================================================

class TestStatusHelpers:
    """Tests for status constants and helper functions."""

    def test_spec_statuses_defined(self):
        """SPEC_STATUSES should contain valid statuses."""
        assert "draft" in SPEC_STATUSES
        assert "pending_review" in SPEC_STATUSES
        assert "approved" in SPEC_STATUSES
        assert "signed" in SPEC_STATUSES

    def test_spec_status_names_russian(self):
        """Status names should be in Russian."""
        assert SPEC_STATUS_NAMES["draft"] == "Черновик"
        assert "проверке" in SPEC_STATUS_NAMES["pending_review"].lower() or "проверка" in SPEC_STATUS_NAMES["pending_review"].lower()

    def test_spec_status_colors_defined(self):
        """Status colors should be defined."""
        for status in SPEC_STATUSES:
            assert status in SPEC_STATUS_COLORS
            # Colors can be hex codes or tailwind classes
            color = SPEC_STATUS_COLORS[status]
            assert color is not None
            assert len(color) > 0

    def test_get_spec_status_name(self):
        """get_spec_status_name should return correct name."""
        assert get_spec_status_name("draft") == "Черновик"

    def test_get_spec_status_color(self):
        """get_spec_status_color should return color."""
        color = get_spec_status_color("draft")
        assert color is not None
        assert len(color) > 0

    def test_can_transition_spec_valid(self):
        """can_transition_spec should allow valid transitions."""
        # draft -> pending_review
        assert can_transition_spec("draft", "pending_review") is True

    def test_can_transition_spec_invalid(self):
        """can_transition_spec should reject invalid transitions."""
        # Cannot go from draft directly to signed
        assert can_transition_spec("draft", "signed") is False

    def test_get_allowed_spec_transitions(self):
        """get_allowed_spec_transitions should return valid targets."""
        transitions = get_allowed_spec_transitions("draft")
        assert isinstance(transitions, list)
        assert "pending_review" in transitions


# =============================================================================
# CREATE OPERATIONS TESTS
# =============================================================================

class TestCreateOperations:
    """Tests for specification create operations."""

    @patch('services.specification_service.get_supabase')
    def test_create_specification_calls_insert(self, mock_supabase):
        """create_specification should insert with correct data."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "new-spec-uuid",
            "quote_id": "quote-uuid",
            "organization_id": "org-uuid",
            "status": "draft",
            "created_by": "user-uuid",
            "created_at": "2026-01-15T12:00:00Z",
        }]
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_response

        result = create_specification(
            quote_id="quote-uuid",
            organization_id="org-uuid",
            created_by="user-uuid",
            specification_currency="USD",
        )

        assert result is not None
        mock_client.table.assert_called_with("specifications")

    @patch('services.specification_service.get_supabase')
    def test_create_specification_error_handling(self, mock_supabase):
        """create_specification should return None on error."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception("DB Error")

        result = create_specification(
            quote_id="quote-uuid",
            organization_id="org-uuid",
            created_by="user-uuid",
        )

        assert result is None


# =============================================================================
# SPEC-001: CREATE FROM QUOTE TESTS
# =============================================================================

class TestCreateSpecificationFromQuote:
    """Tests for SPEC-001: create_specification_from_quote."""

    def test_create_spec_from_quote_result_class(self):
        """CreateSpecFromQuoteResult should be importable."""
        result = CreateSpecFromQuoteResult(
            success=True,
            specification=None,
            error=None,
            prefilled_fields={"currency": "USD"}
        )
        assert result.success is True
        assert result.prefilled_fields is not None

    @patch('services.specification_service.get_supabase')
    def test_create_spec_from_quote_import(self, mock_supabase):
        """create_specification_from_quote should be callable."""
        assert callable(create_specification_from_quote)


# =============================================================================
# READ OPERATIONS TESTS
# =============================================================================

class TestReadOperations:
    """Tests for specification read operations."""

    @patch('services.specification_service.get_supabase')
    def test_get_specification_found(self, mock_supabase):
        """get_specification should return spec when found."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "spec-uuid",
            "quote_id": "quote-uuid",
            "organization_id": "org-uuid",
            "status": "draft",
            "created_by": "user-uuid",
            "created_at": "2026-01-15T12:00:00Z",
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = get_specification("spec-uuid")

        assert result is not None

    @patch('services.specification_service.get_supabase')
    def test_specification_exists_for_quote(self, mock_supabase):
        """specification_exists_for_quote should check existence."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.count = 1
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        result = specification_exists_for_quote("quote-uuid")

        assert result is True


# =============================================================================
# UPDATE OPERATIONS TESTS
# =============================================================================

class TestUpdateOperations:
    """Tests for specification update operations."""

    @patch('services.specification_service.get_supabase')
    @patch('services.specification_service.get_specification')
    def test_update_specification_status(self, mock_get_spec, mock_supabase):
        """update_specification_status should update status."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock current spec with draft status
        mock_current = MagicMock()
        mock_current.status = "draft"
        mock_get_spec.return_value = mock_current

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "spec-uuid",
            "quote_id": "quote-uuid",
            "organization_id": "org-uuid",
            "status": "pending_review",
            "created_by": "user-uuid",
            "created_at": "2026-01-15T12:00:00Z",
        }]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        # Correct argument order: spec_id, organization_id, new_status
        result = update_specification_status("spec-uuid", "org-uuid", "pending_review")

        assert result is not None

    @patch('services.specification_service.get_supabase')
    def test_set_signed_scan_url(self, mock_supabase):
        """set_signed_scan_url should update scan URL."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = [{
            "id": "spec-uuid",
            "quote_id": "quote-uuid",
            "organization_id": "org-uuid",
            "status": "signed",
            "signed_scan_url": "https://storage.example.com/scans/signed.pdf",
            "created_by": "user-uuid",
            "created_at": "2026-01-15T12:00:00Z",
        }]
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = mock_response

        result = set_signed_scan_url(
            spec_id="spec-uuid",
            organization_id="org-uuid",
            signed_scan_url="https://storage.example.com/scans/signed.pdf"
        )

        assert result is not None

        # Verify update was called with signed_scan_url
        update_call = mock_client.table.return_value.update.call_args
        assert "signed_scan_url" in update_call[0][0]


# =============================================================================
# UTILITY FUNCTIONS TESTS
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    @patch('services.specification_service.get_supabase')
    def test_generate_specification_number(self, mock_supabase):
        """generate_specification_number should create formatted number."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # Mock no existing specs
        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.like.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        result = generate_specification_number("org-uuid", prefix="SPEC")

        assert result is not None
        assert result.startswith("SPEC-")

    @patch('services.specification_service.get_supabase')
    def test_get_specifications_for_signing(self, mock_supabase):
        """get_specifications_for_signing should return approved specs."""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_response = MagicMock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.order.return_value.limit.return_value.execute.return_value = mock_response

        result = get_specifications_for_signing("org-uuid")

        assert isinstance(result, list)


# =============================================================================
# SPEC-002: PDF GENERATION IMPORTS TEST
# =============================================================================

class TestPdfGenerationImports:
    """Tests for SPEC-002: Specification PDF generation imports."""

    def test_import_specification_export(self):
        """specification_export module should be importable."""
        from services.specification_export import (
            generate_specification_pdf,
            SpecificationData,
            fetch_specification_data,
            generate_spec_pdf_html,
            generate_spec_pdf_from_spec_id,
        )
        assert callable(generate_specification_pdf)
        assert callable(generate_spec_pdf_from_spec_id)

    def test_specification_data_class(self):
        """SpecificationData should be importable."""
        from services.specification_export import SpecificationData
        assert SpecificationData is not None


# =============================================================================
# IMPORT VERIFICATION TESTS
# =============================================================================

class TestImports:
    """Tests to verify all functions are importable."""

    def test_import_specification_dataclass(self):
        """Specification dataclass should be importable."""
        from services.specification_service import Specification
        assert Specification is not None

    def test_import_status_constants(self):
        """Status constants should be importable."""
        from services.specification_service import (
            SPEC_STATUSES,
            SPEC_STATUS_NAMES,
            SPEC_STATUS_COLORS,
            SPEC_TRANSITIONS
        )
        assert len(SPEC_STATUSES) > 0
        assert len(SPEC_STATUS_NAMES) > 0

    def test_import_status_helpers(self):
        """Status helper functions should be importable."""
        from services.specification_service import (
            get_spec_status_name,
            get_spec_status_color,
            can_transition_spec,
            get_allowed_spec_transitions
        )
        assert all(callable(f) for f in [
            get_spec_status_name,
            get_spec_status_color,
            can_transition_spec,
            get_allowed_spec_transitions
        ])

    def test_import_crud_operations(self):
        """CRUD operations should be importable."""
        from services.specification_service import (
            create_specification,
            get_specification,
            update_specification,
            delete_specification,
        )
        assert all(callable(f) for f in [
            create_specification,
            get_specification,
            update_specification,
            delete_specification,
        ])

    def test_import_from_services_init(self):
        """Functions should be exported from services/__init__.py."""
        from services import (
            Specification,
            create_specification,
            create_specification_from_quote,
            get_specification,
            set_signed_scan_url,
        )
        assert all([
            Specification is not None,
            callable(create_specification),
            callable(create_specification_from_quote),
            callable(get_specification),
            callable(set_signed_scan_url),
        ])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
