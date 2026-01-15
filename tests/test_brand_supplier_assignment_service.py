"""
Tests for brand_supplier_assignment_service.py (Feature API-008)

Tests CRUD operations for brand-supplier assignments.
Note: These tests don't require database connection as they test
dataclass creation, parsing, and utility function logic.
"""

import pytest
from datetime import datetime
from services.brand_supplier_assignment_service import (
    # Data class
    BrandSupplierAssignment,
    # Parsing functions
    _parse_assignment,
    _parse_assignment_with_supplier,
    # Utility functions
    format_brand_supplier_for_display,
)


class TestBrandSupplierAssignmentDataclass:
    """Tests for BrandSupplierAssignment dataclass."""

    def test_create_assignment_minimal(self):
        """Test creating assignment with minimal fields."""
        assignment = BrandSupplierAssignment(
            id="test-uuid-123",
            organization_id="org-uuid",
            brand="BOSCH",
            supplier_id="supplier-uuid",
            is_primary=False,
        )

        assert assignment.id == "test-uuid-123"
        assert assignment.organization_id == "org-uuid"
        assert assignment.brand == "BOSCH"
        assert assignment.supplier_id == "supplier-uuid"
        assert assignment.is_primary is False
        assert assignment.notes is None
        assert assignment.supplier_name is None

    def test_create_assignment_full(self):
        """Test creating assignment with all fields."""
        now = datetime.now()
        assignment = BrandSupplierAssignment(
            id="test-uuid-123",
            organization_id="org-uuid",
            brand="SIEMENS",
            supplier_id="supplier-uuid",
            is_primary=True,
            notes="Preferred supplier for EU region",
            created_at=now,
            updated_at=now,
            created_by="admin-uuid",
            supplier_name="Germany Manufacturing GmbH",
            supplier_code="GMG",
            supplier_country="Germany",
        )

        assert assignment.brand == "SIEMENS"
        assert assignment.is_primary is True
        assert assignment.notes == "Preferred supplier for EU region"
        assert assignment.supplier_name == "Germany Manufacturing GmbH"
        assert assignment.supplier_code == "GMG"
        assert assignment.supplier_country == "Germany"

    def test_assignment_defaults(self):
        """Test that optional fields default to None."""
        assignment = BrandSupplierAssignment(
            id="id",
            organization_id="org",
            brand="BRAND",
            supplier_id="supplier",
            is_primary=False,
        )

        assert assignment.notes is None
        assert assignment.created_at is None
        assert assignment.updated_at is None
        assert assignment.created_by is None
        assert assignment.supplier_name is None
        assert assignment.supplier_code is None
        assert assignment.supplier_country is None


class TestParseAssignment:
    """Tests for _parse_assignment function."""

    def test_parse_minimal_data(self):
        """Test parsing minimal database row."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "ABB",
            "supplier_id": "supplier-uuid",
        }

        assignment = _parse_assignment(data)

        assert assignment.id == "uuid-123"
        assert assignment.brand == "ABB"
        assert assignment.is_primary is False  # default

    def test_parse_full_data(self):
        """Test parsing full database row."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "SCHNEIDER",
            "supplier_id": "supplier-uuid",
            "is_primary": True,
            "notes": "Primary for France",
            "created_at": "2026-01-15T12:00:00Z",
            "updated_at": "2026-01-15T13:00:00Z",
            "created_by": "admin-uuid",
        }

        assignment = _parse_assignment(data)

        assert assignment.brand == "SCHNEIDER"
        assert assignment.is_primary is True
        assert assignment.notes == "Primary for France"
        assert assignment.created_at is not None
        assert assignment.updated_at is not None
        assert assignment.created_by == "admin-uuid"

    def test_parse_with_iso_timestamp(self):
        """Test parsing ISO format timestamps."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "TEST",
            "supplier_id": "supplier-uuid",
            "created_at": "2026-01-15T12:30:45+00:00",
        }

        assignment = _parse_assignment(data)

        assert assignment.created_at is not None
        assert assignment.created_at.year == 2026
        assert assignment.created_at.month == 1
        assert assignment.created_at.day == 15


class TestParseAssignmentWithSupplier:
    """Tests for _parse_assignment_with_supplier function."""

    def test_parse_with_joined_supplier(self):
        """Test parsing row with joined supplier data."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "BOSCH",
            "supplier_id": "supplier-uuid",
            "is_primary": True,
            "suppliers": {
                "name": "China Manufacturing Ltd",
                "supplier_code": "CMT",
                "country": "China",
            },
        }

        assignment = _parse_assignment_with_supplier(data)

        assert assignment.brand == "BOSCH"
        assert assignment.supplier_name == "China Manufacturing Ltd"
        assert assignment.supplier_code == "CMT"
        assert assignment.supplier_country == "China"

    def test_parse_without_joined_supplier(self):
        """Test parsing row without supplier join."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "TEST",
            "supplier_id": "supplier-uuid",
            "is_primary": False,
        }

        assignment = _parse_assignment_with_supplier(data)

        assert assignment.brand == "TEST"
        assert assignment.supplier_name is None
        assert assignment.supplier_code is None
        assert assignment.supplier_country is None

    def test_parse_with_empty_supplier(self):
        """Test parsing row with empty supplier join."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "TEST",
            "supplier_id": "supplier-uuid",
            "is_primary": False,
            "suppliers": None,
        }

        assignment = _parse_assignment_with_supplier(data)

        assert assignment.supplier_name is None

    def test_parse_with_partial_supplier(self):
        """Test parsing row with partial supplier data."""
        data = {
            "id": "uuid-123",
            "organization_id": "org-uuid",
            "brand": "TEST",
            "supplier_id": "supplier-uuid",
            "is_primary": False,
            "suppliers": {
                "name": "Test Supplier",
                # Missing supplier_code and country
            },
        }

        assignment = _parse_assignment_with_supplier(data)

        assert assignment.supplier_name == "Test Supplier"
        assert assignment.supplier_code is None
        assert assignment.supplier_country is None


class TestFormatBrandSupplierForDisplay:
    """Tests for format_brand_supplier_for_display function."""

    def test_format_with_full_info_primary(self):
        """Test formatting with full info and primary flag."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier-uuid",
            is_primary=True,
            supplier_name="China Manufacturing Ltd",
            supplier_code="CMT",
        )

        result = format_brand_supplier_for_display(assignment)

        assert result == "BOSCH -> CMT - China Manufacturing Ltd [PRIMARY]"

    def test_format_with_full_info_not_primary(self):
        """Test formatting with full info, not primary."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="SIEMENS",
            supplier_id="supplier-uuid",
            is_primary=False,
            supplier_name="Germany GmbH",
            supplier_code="GMG",
        )

        result = format_brand_supplier_for_display(assignment)

        assert result == "SIEMENS -> GMG - Germany GmbH"
        assert "[PRIMARY]" not in result

    def test_format_without_supplier_name(self):
        """Test formatting without supplier name."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="ABB",
            supplier_id="supplier-uuid",
            is_primary=False,
            supplier_code="ABC",
        )

        result = format_brand_supplier_for_display(assignment)

        assert result == "ABB -> ABC"

    def test_format_without_supplier_code(self):
        """Test formatting without supplier code (uses truncated ID)."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="TEST",
            supplier_id="supplier-uuid-1234",
            is_primary=False,
        )

        result = format_brand_supplier_for_display(assignment)

        assert result == "TEST -> supplier"  # First 8 chars of supplier_id

    def test_format_with_supplier_name_no_code(self):
        """Test formatting with supplier name but no code."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="BRAND",
            supplier_id="supplier-uuid-full",
            is_primary=True,
            supplier_name="Some Company",
        )

        result = format_brand_supplier_for_display(assignment)

        # Uses truncated ID (first 8 chars) when no code: "supplier"
        assert "supplier" in result  # First 8 chars of supplier_id
        assert "Some Company" in result
        assert "[PRIMARY]" in result


class TestDataclassEquality:
    """Tests for dataclass comparison."""

    def test_equal_assignments(self):
        """Test that equal assignments compare as equal."""
        assignment1 = BrandSupplierAssignment(
            id="same-id",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier",
            is_primary=True,
        )
        assignment2 = BrandSupplierAssignment(
            id="same-id",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier",
            is_primary=True,
        )

        assert assignment1 == assignment2

    def test_different_assignments(self):
        """Test that different assignments compare as not equal."""
        assignment1 = BrandSupplierAssignment(
            id="id-1",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier",
            is_primary=True,
        )
        assignment2 = BrandSupplierAssignment(
            id="id-2",
            organization_id="org",
            brand="SIEMENS",
            supplier_id="supplier",
            is_primary=False,
        )

        assert assignment1 != assignment2


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_brand_name(self):
        """Test assignment with empty brand name."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="",
            supplier_id="supplier",
            is_primary=False,
        )

        assert assignment.brand == ""

    def test_brand_name_with_special_characters(self):
        """Test brand name with special characters."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="Brand & Co. (TM)",
            supplier_id="supplier",
            is_primary=False,
        )

        assert assignment.brand == "Brand & Co. (TM)"

    def test_unicode_brand_name(self):
        """Test brand name with unicode characters."""
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="Бренд ООО",  # Russian
            supplier_id="supplier",
            is_primary=False,
        )

        assert assignment.brand == "Бренд ООО"

    def test_parse_null_is_primary(self):
        """Test parsing when is_primary is null."""
        data = {
            "id": "uuid",
            "organization_id": "org",
            "brand": "TEST",
            "supplier_id": "supplier",
            "is_primary": None,
        }

        assignment = _parse_assignment(data)

        # Should default to False when None
        assert assignment.is_primary is False

    def test_very_long_notes(self):
        """Test assignment with very long notes."""
        long_notes = "A" * 10000
        assignment = BrandSupplierAssignment(
            id="uuid",
            organization_id="org",
            brand="TEST",
            supplier_id="supplier",
            is_primary=False,
            notes=long_notes,
        )

        assert len(assignment.notes) == 10000


class TestBrandSupplierRelationship:
    """Tests for brand-supplier relationship logic."""

    def test_multiple_suppliers_one_primary(self):
        """Test that model supports multiple suppliers with one primary."""
        # In practice, the database enforces one primary via trigger
        # Here we just test the model can represent both states
        primary = BrandSupplierAssignment(
            id="uuid-1",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier-1",
            is_primary=True,
        )
        secondary = BrandSupplierAssignment(
            id="uuid-2",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier-2",
            is_primary=False,
        )

        assert primary.is_primary is True
        assert secondary.is_primary is False
        assert primary.brand == secondary.brand  # Same brand

    def test_supplier_multiple_brands(self):
        """Test that one supplier can have multiple brands."""
        brand1 = BrandSupplierAssignment(
            id="uuid-1",
            organization_id="org",
            brand="BOSCH",
            supplier_id="supplier-uuid",
            is_primary=True,
        )
        brand2 = BrandSupplierAssignment(
            id="uuid-2",
            organization_id="org",
            brand="SIEMENS",
            supplier_id="supplier-uuid",
            is_primary=True,
        )

        assert brand1.supplier_id == brand2.supplier_id  # Same supplier
        assert brand1.brand != brand2.brand  # Different brands


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
